"""Construit data/points.json à partir de tools/spots.json (points recoupés à la main),
de la BD Forêt (data/chataigniers.geojson) et des parkings OpenStreetMap.

Calcule pour chaque point la distance au peuplement de châtaigniers le plus proche
et un score de confiance de 1 à 5 (méthode décrite dans le README).

Usage : python tools/build_points.py [parkings_osm.json]
"""
import datetime, json, math, sys, time, urllib.parse, urllib.request
import geopandas as gpd
from shapely.geometry import Point

ROOT = __file__.replace("\\", "/").rsplit("/tools/", 1)[0]
OVERPASS = "https://overpass-api.de/api/interpreter"
PARK_BBOX = (45.0, 5.6, 45.5, 6.25)  # S, W, N, E
EXPLICIT = {"temoignage", "rando", "officiel"}

src = json.load(open(f"{ROOT}/tools/spots.json", encoding="utf-8"))
forest = gpd.read_file(f"{ROOT}/data/chataigniers.geojson").to_crs(2154)
forest_union = forest.union_all()
to_l93 = lambda lat, lon: gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(2154).iloc[0]


def forest_dist(lat, lon):
    return round(forest_union.distance(to_l93(lat, lon)))


def score(p):
    """Score 1–5 + explication lisible."""
    s, why = 1.0, []
    explicit = [x for x in p["sources"] if x["kind"] in EXPLICIT and not x.get("noChestnut")]
    if explicit:
        s += 1; why.append("1 source cite des châtaignes (+1)")
        extra = min(len(explicit) - 1, 3)
        if extra:
            s += 0.5 * extra; why.append(f"{extra} source(s) indépendante(s) en plus (+{0.5 * extra:g})".replace(".", ","))
        years = [int(x["date"][-4:]) for x in explicit if x.get("date", "")[-4:].isdigit()]
        if years and max(years) >= datetime.date.today().year - 5:
            s += 0.5; why.append("témoignage récent (+0,5)")
    if not explicit and any(x["kind"] == "osm" for x in p["sources"]):
        s += 0.5; why.append("indice OpenStreetMap (+0,5)")
    d = p["bdforet"]
    if d <= 100:
        s += 2; why.append("dans un peuplement IGN de châtaigniers purs (+2)")
    elif d <= 500:
        s += 1; why.append(f"peuplement IGN à {d} m (+1)")
    elif d <= 1500:
        s += 0.5; why.append(f"peuplement IGN à {d / 1000:.1f} km (+0,5)")
    if p.get("precision") == "approx":
        s -= 0.5; why.append("emplacement approximatif (−0,5)")
    elif p.get("precision") == "zone":
        s -= 0.5; why.append("zone large, pas un coin précis (−0,5)")
    return max(1, min(5, int(s + 0.5))), "; ".join(why) or "aucun indice"


def overpass_parkings():
    if len(sys.argv) > 1:
        return json.load(open(sys.argv[1], encoding="utf-8"))["elements"]
    q = '[out:json][timeout:180];nwr["amenity"="parking"](%f,%f,%f,%f);out center tags;' % PARK_BBOX
    req = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({"data": q}).encode(),
                                 headers={"User-Agent": "ChataignFinder"})
    return json.load(urllib.request.urlopen(req, timeout=240))["elements"]


def commune(lat, lon, cache={}):
    k = (round(lat, 3), round(lon, 3))
    if k not in cache:
        u = f"https://geo.api.gouv.fr/communes?lat={lat}&lon={lon}&fields=nom"
        try:
            d = json.load(urllib.request.urlopen(u, timeout=20)); cache[k] = d[0]["nom"] if d else ""
        except Exception:
            cache[k] = ""
        time.sleep(0.1)
    return cache[k]


points = []
for p in src["spots"]:
    p = dict(p)
    p["bdforet"] = forest_dist(p["lat"], p["lon"])
    p["conf"], p["why"] = score(p)
    p["sources"] = [{**{k: v for k, v in s.items() if k in ("url", "date", "quote")},
                     "label": s["label"] + (" (infos d'accès)" if s.get("noChestnut") else "")} for s in p["sources"]]
    p.pop("precision", None)
    points.append(p)

# ---- Parkings OSM ----
osm = []
for e in overpass_parkings():
    t = e.get("tags", {})
    if t.get("access") in ("private", "customers", "no", "delivery") or t.get("parking") in ("underground", "multi-storey", "rooftop"):
        continue
    c = e.get("center", e)
    osm.append({"lat": c["lat"], "lon": c["lon"], "tags": t, "osm": f"{e['type']}/{e['id']}"})
osm_gdf = gpd.GeoDataFrame(osm, geometry=[Point(o["lon"], o["lat"]) for o in osm], crs=4326).to_crs(2154)
spots_by_id = {p["id"]: p for p in points}

# Parkings cités par une source : recalés sur le parking OSM le plus proche (< 250 m).
taken = []
for cp in src["parkings"]:
    geom = to_l93(cp["lat"], cp["lon"])
    d = osm_gdf.distance(geom)
    i = d.idxmin()
    lat, lon = cp["lat"], cp["lon"]
    if d[i] < 250:
        lat, lon = round(osm_gdf.loc[i, "lat"], 6), round(osm_gdf.loc[i, "lon"], 6)
        taken.append(i)
    spot = spots_by_id.get(cp["for"])
    points.append({
        "id": cp["id"], "type": "parking", "name": cp["name"], "lat": lat, "lon": lon,
        "commune": spot["commune"] if spot else "", "conf": 3 if cp.get("approx") else 4,
        "bdforet": forest_dist(lat, lon),
        "desc": f"Parking cité comme point de départ pour « {spot['name']} »." if spot else "",
        "sources": [{"label": cp["source"]}] + (spot["sources"][:1] if spot else []),
        "why": "parking cité par une source" + (" (emplacement approximatif)" if cp.get("approx") else ""),
    })

# Parkings OSM publics proches d'une zone IGN ou d'un spot/rando.
anchors = [to_l93(p["lat"], p["lon"]) for p in points if p["type"] in ("spot", "rando")]
kept = []
for i, row in osm_gdf.iterrows():
    if i in taken:
        continue
    df = forest_union.distance(row.geometry)
    da = min(a.distance(row.geometry) for a in anchors)
    if df > 200 and da > 300:
        continue
    if any(row.geometry.distance(k) < 250 for k in kept):
        continue
    kept.append(row.geometry)
    t = row["tags"]
    conf = 3 if df <= 100 else 2
    cap = f" · {t['capacity']} places" if t.get("capacity", "").isdigit() else ""
    why = (f"parking public OSM à {round(df)} m d'un peuplement IGN" if df <= 200
           else f"parking public OSM à {round(da)} m d'un spot/départ de rando")
    points.append({
        "id": "osm-" + row["osm"].replace("/", "-"), "type": "parking",
        "name": t.get("name") or "Parking" + (" (terre)" if t.get("surface") in ("gravel", "ground", "dirt", "unpaved", "grass") else ""),
        "lat": round(row["lat"], 6), "lon": round(row["lon"], 6), "commune": commune(row["lat"], row["lon"]),
        "conf": conf, "bdforet": round(df),
        "desc": f"Parking public repéré dans OpenStreetMap{cap}. Pratique pour démarrer à pied vers les châtaigniers les plus proches.",
        "sources": [{"label": "OpenStreetMap", "url": "https://www.openstreetmap.org/" + row["osm"]}],
        "why": why,
    })

# ---- Sortie ----
labels = {}
for p in points:
    for s in p["sources"]:
        if s.get("url") and "openstreetmap" not in s["url"]:
            labels.setdefault(s["url"], s["label"])
meta = {
    "updated": datetime.date.today().isoformat(),
    "sources": [{"label": "IGN — BD Forêt V2 (peuplements de châtaigniers purs)", "url": "https://cartes.gouv.fr/rechercher-une-donnee/dataset/IGNF_BD-FORET"}]
               + [{"label": l, "url": u} for u, l in labels.items()]
               + [{"label": "OpenStreetMap (parkings, arbres, toponymes)", "url": "https://www.openstreetmap.org"}],
}
json.dump({"meta": meta, "points": points}, open(f"{ROOT}/data/points.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
by = {}
for p in points:
    by[p["type"]] = by.get(p["type"], 0) + 1
print(len(points), "points", by)
for p in points:
    if p["type"] != "parking":
        print(f"  {p['conf']}/5  {p['name']}  (IGN {p['bdforet']} m) — {p['why']}")
