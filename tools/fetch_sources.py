"""Télécharge les sources brutes utilisées pour les parkings dans tools/raw/ (non versionné).

- OSM : parkings publics, poteaux de randonnée, routes et sentiers autour des zones à châtaigniers
- IGN BD TOPO : équipements « Parking » (dont « Parking touristique isolé »)

Usage : python tools/fetch_sources.py
"""
import json, os, time, urllib.parse, urllib.request

ROOT = __file__.replace("\\", "/").rsplit("/tools/", 1)[0]
RAW = f"{ROOT}/tools/raw"
os.makedirs(RAW, exist_ok=True)
BBOX = (45.0, 5.6, 45.5, 6.25)  # S, W, N, E
OVERPASS = "https://overpass-api.de/api/interpreter"


def overpass(q, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({"data": q}).encode(),
                                         headers={"User-Agent": "ChataignFinder"})
            return json.load(urllib.request.urlopen(req, timeout=300))
        except Exception as e:
            print("  Overpass indisponible, nouvel essai…", e)
            time.sleep(20)
    raise SystemExit("Overpass injoignable")


def save(name, data):
    json.dump(data, open(f"{RAW}/{name}", "w", encoding="utf-8"))
    print("→", name)


b = "%f,%f,%f,%f" % BBOX
print("OSM parkings…")
if not os.path.exists(f"{RAW}/osm_parkings.json"): save("osm_parkings.json", overpass(f'[out:json][timeout:240];nwr["amenity"="parking"]({b});out center tags;'))

# Routes + sentiers + poteaux, uniquement autour des zones à châtaigniers et des spots (zones = bboxes élargies).
forest = json.load(open(f"{ROOT}/data/chataigniers.geojson"))
spots = json.load(open(f"{ROOT}/tools/spots.json", encoding="utf-8"))["spots"]
boxes = []
pad = 0.008  # ~700 m
for f in forest["features"]:
    xs, ys = [], []
    def walk(c):
        if isinstance(c[0], (int, float)):
            xs.append(c[0]); ys.append(c[1])
        else:
            for sub in c:
                walk(sub)
    walk(f["geometry"]["coordinates"])
    boxes.append((min(ys) - pad, min(xs) - pad, max(ys) + pad, max(xs) + pad))
for s in spots:
    boxes.append((s["lat"] - pad, s["lon"] - pad, s["lat"] + pad, s["lon"] + pad))
boxes = [bx for bx in boxes if bx[1] >= BBOX[1] - pad]
parts = "".join(
    f'way["highway"~"^(path|track|bridleway|unclassified|tertiary|secondary|residential)$"]({bx[0]:.4f},{bx[1]:.4f},{bx[2]:.4f},{bx[3]:.4f});'
    f'node["information"="guidepost"]({bx[0]:.4f},{bx[1]:.4f},{bx[2]:.4f},{bx[3]:.4f});'
    for bx in boxes)
print("OSM routes et sentiers autour de", len(boxes), "zones…")
save("osm_ways.json", overpass(f"[out:json][timeout:280];({parts});out body;>;out skel qt;"))

print("IGN BD TOPO parkings…")
params = {
    "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature", "TYPENAMES": "BDTOPO_V3:equipement_de_transport",
    "OUTPUTFORMAT": "application/json", "SRSNAME": "EPSG:4326", "COUNT": "10000",
    "CQL_FILTER": "nature='Parking' AND BBOX(geometrie,%f,%f,%f,%f,'urn:ogc:def:crs:EPSG::4326')" % BBOX,
}
save("bdtopo_parkings.json", json.load(urllib.request.urlopen("https://data.geopf.fr/wfs/ows?" + urllib.parse.urlencode(params), timeout=300)))
