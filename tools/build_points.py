"""Construit data/points.json à partir de :
- tools/spots.json : spots recoupés à la main (forums, blogs, randos, OSM) ;
- data/chataigniers.geojson : peuplements IGN BD Forêt ;
- tools/raw/*.json : parkings OSM, parkings IGN BD TOPO, routes et sentiers OSM (python tools/fetch_sources.py) ;
- tools/visorando_starts.json : points de départ des randos Visorando (python tools/visorando_starts.py).

Calcule pour chaque point la distance à la zone de châtaigniers la plus proche
et un score de confiance de 1 à 5 (méthode décrite dans le README).

Usage : python tools/build_points.py
"""
import datetime, json, time, urllib.request
import geopandas as gpd
from shapely.geometry import LineString, Point, shape
from shapely.strtree import STRtree

ROOT = __file__.replace("\\", "/").rsplit("/tools/", 1)[0]
RAW = f"{ROOT}/tools/raw"
EXPLICIT = {"temoignage", "rando", "officiel"}

src = json.load(open(f"{ROOT}/tools/spots.json", encoding="utf-8"))
forest = gpd.read_file(f"{ROOT}/data/chataigniers.geojson").to_crs(2154)
forest_union = forest.union_all()


def l93(lonlats):
    return list(gpd.GeoSeries([Point(x, y) for x, y in lonlats], crs=4326).to_crs(2154))


def to_l93(lat, lon):
    return l93([(lon, lat)])[0]


def forest_dist(lat, lon):
    return round(forest_union.distance(to_l93(lat, lon)))


def score(p):
    """Score 1–5 d'un spot + explication lisible."""
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
        s += 0.5; why.append(f"peuplement IGN à {d / 1000:.1f} km (+0,5)".replace(".", ",", 1))
    if p.get("precision") == "approx":
        s -= 0.5; why.append("emplacement approximatif (−0,5)")
    elif p.get("precision") == "zone":
        s -= 0.5; why.append("zone large, pas un coin précis (−0,5)")
    return max(1, min(5, int(s + 0.5))), "; ".join(why) or "aucun indice"


def commune(lat, lon, cache={}):
    k = (round(lat, 3), round(lon, 3))
    if k not in cache:
        try:
            d = json.load(urllib.request.urlopen(f"https://geo.api.gouv.fr/communes?lat={lat}&lon={lon}&fields=nom", timeout=20))
            cache[k] = d[0]["nom"] if d else ""
        except Exception:
            cache[k] = ""
        time.sleep(0.1)
    return cache[k]


# ---------------------------------------------------------------- Spots
points = []
for p in src["spots"]:
    p = dict(p)
    p["bdforet"] = forest_dist(p["lat"], p["lon"])
    if p["type"] == "achat":
        p["conf"], p["why"] = 3, "information de témoignage (prix et présence à revérifier chaque saison)"
    else:
        p["conf"], p["why"] = score(p)
    p["sources"] = [{**{k: v for k, v in s.items() if k in ("url", "date", "quote")},
                     "label": s["label"] + (" (infos d'accès)" if s.get("noChestnut") else "")} for s in p["sources"]]
    p.pop("precision", None)
    points.append(p)
spots_by_id = {p["id"]: p for p in points}
anchors = gpd.GeoSeries([Point(p["lon"], p["lat"]) for p in points if p["type"] in ("spot", "rando")], crs=4326).to_crs(2154).union_all()

# ---------------------------------------------------------------- Parkings connus (OSM + IGN BD TOPO + départs Visorando)
cands = []  # une entrée = une source qui dit « on peut se garer ici »
for e in json.load(open(f"{RAW}/osm_parkings.json", encoding="utf-8"))["elements"]:
    t = e.get("tags", {})
    if t.get("access") in ("private", "customers", "no", "delivery") or t.get("parking") in ("underground", "multi-storey", "rooftop"):
        continue
    c = e.get("center", e)
    surf = " en terre" if t.get("surface") in ("gravel", "ground", "dirt", "unpaved", "grass", "fine_gravel", "compacted") else ""
    cap = f", {t['capacity']} places" if t.get("capacity", "").isdigit() else ""
    cands.append({"src": "osm", "lat": c["lat"], "lon": c["lon"], "name": t.get("name"),
                  "label": f"OpenStreetMap — parking public{surf}{cap}", "url": f"https://www.openstreetmap.org/{e['type']}/{e['id']}"})
for f in json.load(open(f"{RAW}/bdtopo_parkings.json", encoding="utf-8"))["features"]:
    pr = f["properties"]
    if pr.get("nature_detaillee") in ("Parking souterrain", "Parking couvert"):
        continue
    g = shape(f["geometry"]).representative_point()
    trail = pr.get("nature_detaillee") == "Parking touristique isolé"
    cands.append({"src": "ign", "lat": g.y, "lon": g.x, "name": pr.get("toponyme"), "trail": trail,
                  "label": "IGN BD TOPO — " + ("parking touristique isolé (départ de sentier)" if trail else "parking"),
                  "url": "https://cartes.gouv.fr/rechercher-une-donnee/dataset/IGNF_BD-TOPO"})
try:
    vstarts = json.load(open(f"{ROOT}/tools/visorando_starts.json", encoding="utf-8"))
except FileNotFoundError:
    vstarts = []
for v in vstarts:
    cands.append({"src": "vis", "lat": v["lat"], "lon": v["lon"], "name": None, "mention": bool(v.get("parking")),
                  "label": f"Visorando — départ de « {v['name']} »" + (" (stationnement indiqué)" if v.get("parking") else ""),
                  "url": v["url"], "quote": (v.get("parking") or [None])[0]})
for c, g in zip(cands, l93([(c["lon"], c["lat"]) for c in cands])):
    c["g"] = g
cands = [c for c in cands if forest_union.distance(c["g"]) <= (300 if c["src"] == "vis" else 250)
         or anchors.distance(c["g"]) <= (300 if c["src"] == "vis" else 400)]

# Regroupement à 120 m : plusieurs sources au même endroit = un seul parking, plus fiable.
cands.sort(key=lambda c: {"osm": 0, "ign": 1, "vis": 2}[c["src"]])
clusters = []
for c in cands:
    for cl in clusters:
        if cl["g"].distance(c["g"]) < 120:
            cl["items"].append(c); break
    else:
        clusters.append({"g": c["g"], "lat": c["lat"], "lon": c["lon"], "items": [c]})

# Parkings cités par une source (tools/spots.json) : rattachés au groupe le plus proche (< 250 m).
for cp in src["parkings"]:
    g = to_l93(cp["lat"], cp["lon"])
    item = {"src": "cite", "label": cp["source"], "spot": cp["for"], "name": cp["name"], "approx": cp.get("approx")}
    best = min(clusters, key=lambda cl: cl["g"].distance(g)) if clusters else None
    if best and best["g"].distance(g) < 250:
        best["items"].insert(0, item)
    else:
        clusters.append({"g": g, "lat": cp["lat"], "lon": cp["lon"], "items": [item]})


def park_conf(items):
    srcs = {i["src"] for i in items}
    n = len(srcs & {"osm", "ign"}) + any(i.get("mention") for i in items)
    if "cite" in srcs:
        return 5 if n else (3 if all(i.get("approx") for i in items if i["src"] == "cite") else 4)
    return 4 if n >= 2 else 3 if n == 1 else 2  # 2 = départ de rando sans mention de stationnement


LABELS = {"osm": "OpenStreetMap", "ign": "IGN BD TOPO", "vis": "départ de rando Visorando", "cite": "cité par une source"}
parks = []
for cl in clusters:
    items = cl["items"]
    conf = park_conf(items)
    cited = [i for i in items if i["src"] == "cite"]
    spot = spots_by_id.get(cited[0]["spot"]) if cited else None
    name = (cited[0]["name"] if cited else None) or next((i["name"] for i in items if i.get("name")), None)
    if not name:
        name = "Départ de rando (stationnement probable)" if conf == 2 else "Parking"
    df = round(forest_union.distance(cl["g"]))
    desc = []
    if spot:
        desc.append(f"Parking cité comme point de départ pour « {spot['name']} ».")
    if any(i.get("trail") for i in items):
        desc.append("Parking de départ de sentier selon l'IGN.")
    if conf == 2:
        desc.append("Point de départ d'une rando publiée : on s'y gare sans doute, mais aucune source ne le confirme. Vérifiez sur Street View.")
    desc.append(f"Châtaigniers IGN à {df} m." if df > 0 else "Au bord d'une zone de châtaigniers IGN.")
    parks.append({
        "id": f"pk-{cl['lat']:.5f}-{cl['lon']:.5f}", "type": "parking" if conf >= 3 else "pkprob", "name": name,
        "lat": round(cl["lat"], 6), "lon": round(cl["lon"], 6), "commune": spot["commune"] if spot else "",
        "conf": conf, "bdforet": df, "desc": " ".join(desc),
        "sources": [{k: v for k, v in i.items() if k in ("label", "url", "quote") and v} for i in items if i["src"] != "cite"]
                   + ([{"label": cited[0]["label"]}] + spot["sources"][:1] if cited and spot else []),
        "why": "sources : " + ", ".join(dict.fromkeys(LABELS[i["src"]] for i in items)),
        "_g": cl["g"],
    })

# ---------------------------------------------------------------- Parkings probables
# Un sentier ou une piste qui traverse une zone de châtaigniers rejoint une route carrossable :
# il y a souvent un bas-côté ou une petite aire. À confirmer sur Street View.
TRAILS, ROADS = {"path", "track", "bridleway"}, {"unclassified", "tertiary", "secondary", "residential"}
ow = json.load(open(f"{RAW}/osm_ways.json", encoding="utf-8"))["elements"]
nodes = {e["id"]: (e["lon"], e["lat"]) for e in ow if e["type"] == "node"}
guideposts = l93([(e["lon"], e["lat"]) for e in ow if e["type"] == "node" and e.get("tags", {}).get("information") == "guidepost"])
gp_tree = STRtree(guideposts)
ways, trail_nodes, road_name = {}, {}, {}
for e in ow:
    if e["type"] != "way":
        continue
    hw = e.get("tags", {}).get("highway")
    if hw in TRAILS:
        ways[e["id"]] = e
        for n in e["nodes"]:
            trail_nodes.setdefault(n, []).append(e["id"])
    elif hw in ROADS:
        for n in e["nodes"]:
            road_name.setdefault(n, e.get("tags", {}).get("name") or "")
forest_buf = forest_union.buffer(30)
enters = {}


def trail_enters(wid):
    """Le sentier traverse-t-il une zone de châtaigniers ?"""
    if wid not in enters:
        pts = [nodes[n] for n in ways[wid]["nodes"] if n in nodes]
        enters[wid] = len(pts) > 1 and gpd.GeoSeries([LineString(pts)], crs=4326).to_crs(2154).iloc[0].intersects(forest_buf)
    return enters[wid]


known = STRtree([p["_g"] for p in parks])
junctions = [n for n in trail_nodes if n in road_name and n in nodes]
jg = dict(zip(junctions, l93([nodes[n] for n in junctions])))
prob = []
for n, g in jg.items():
    df = forest_union.distance(g)
    if df > 600 or not any(trail_enters(w) for w in trail_nodes[n]) or len(known.query(g.buffer(200))):
        continue
    prob.append({"g": g, "lon": nodes[n][0], "lat": nodes[n][1], "df": df, "road": road_name[n],
                 "gp": len(gp_tree.query(g.buffer(40))) > 0,
                 "track": any(ways[w]["tags"].get("highway") == "track" for w in trail_nodes[n])})
prob.sort(key=lambda c: (not c["gp"], c["df"]))
kept = []
for c in prob:
    if all(c["g"].distance(k["g"]) >= 400 for k in kept):
        kept.append(c)
for c in kept:
    parks.append({
        "id": f"pp-{c['lat']:.5f}-{c['lon']:.5f}", "type": "pkprob",
        "name": ("Départ de sentier balisé" if c["gp"] else "Entrée de " + ("piste" if c["track"] else "sentier")) + " (parking à vérifier)",
        "lat": round(c["lat"], 6), "lon": round(c["lon"], 6), "commune": "",
        "conf": 2 if c["gp"] else 1, "bdforet": round(c["df"]),
        "desc": f"Ici, {'une piste' if c['track'] else 'un sentier'} qui traverse une zone de châtaigniers rejoint "
                + (f"la route ({c['road']})" if c["road"] else "la route")
                + (", avec un poteau de randonnée" if c["gp"] else "")
                + ". Il y a souvent un bas-côté ou une petite aire pour 2–3 voitures, mais rien ne le garantit : vérifiez sur Street View.",
        "sources": [{"label": "Déduit d'OpenStreetMap (croisement sentier × route)"}],
        "why": "croisement sentier/route menant aux châtaigniers" + (" + poteau de randonnée" if c["gp"] else ""),
        "_g": c["g"],
    })

for p in parks:
    p.pop("_g")
    p["commune"] = p["commune"] or commune(p["lat"], p["lon"])
points.extend(parks)

# ---------------------------------------------------------------- Sortie
labels = {}
for p in points:
    for s in p["sources"]:
        u = s.get("url", "")
        if u and "openstreetmap" not in u and "visorando" not in u and "cartes.gouv" not in u:
            labels.setdefault(u, s["label"])
meta = {
    "updated": datetime.date.today().isoformat(),
    "sources": [{"label": "IGN — BD Forêt V2 (peuplements de châtaigniers purs)", "url": "https://cartes.gouv.fr/rechercher-une-donnee/dataset/IGNF_BD-FORET"},
                {"label": "IGN — BD TOPO (parkings)", "url": "https://cartes.gouv.fr/rechercher-une-donnee/dataset/IGNF_BD-TOPO"},
                {"label": "Visorando (fiches et points de départ des randos)", "url": "https://www.visorando.com"}]
               + [{"label": l, "url": u} for u, l in labels.items()]
               + [{"label": "OpenStreetMap (parkings, sentiers, arbres, toponymes)", "url": "https://www.openstreetmap.org"}],
}
json.dump({"meta": meta, "points": points}, open(f"{ROOT}/data/points.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
by = {}
for p in points:
    by[f"{p['type']} {p['conf']}"] = by.get(f"{p['type']} {p['conf']}", 0) + 1
print(len(points), "points", dict(sorted(by.items())))
for p in points:
    if p["type"] not in ("parking", "pkprob"):
        print(f"  {p['conf']}/5  {p['name']}  (IGN {p['bdforet']} m) — {p['why']}")
