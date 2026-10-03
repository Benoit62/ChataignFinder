"""Télécharge les peuplements de châtaigniers purs (BD Forêt V2, IGN) autour de Grenoble
et produit data/chataigniers.geojson (simplifié, léger).

Usage : python tools/build_forest.py
Dépendances : geopandas, shapely
"""
import json, urllib.parse, urllib.request
import geopandas as gpd
from shapely.geometry import box

# Grenoble + Grésivaudan + Belledonne + piémont Chartreuse + Vizille/Jarrie (lon_min, lat_min, lon_max, lat_max)
BBOX = (5.55, 44.95, 6.25, 45.50)
WFS = "https://data.geopf.fr/wfs/ows"
params = {
    "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
    "TYPENAMES": "LANDCOVER.FORESTINVENTORY.V2:formation_vegetale",
    "OUTPUTFORMAT": "application/json", "SRSNAME": "EPSG:4326", "COUNT": "10000",
    # FF1-10-10 = « Forêt fermée de châtaignier pur »
    "CQL_FILTER": "code_tfv='FF1-10-10' AND BBOX(geom,%f,%f,%f,%f,'urn:ogc:def:crs:EPSG::4326')"
                  % (BBOX[1], BBOX[0], BBOX[3], BBOX[2]),
}
url = WFS + "?" + urllib.parse.urlencode(params)
print("Téléchargement BD Forêt…")
raw = json.load(urllib.request.urlopen(url, timeout=300))
g = gpd.GeoDataFrame.from_features(raw["features"], crs=4326)
g = g[g.intersects(box(*BBOX))].to_crs(2154)
g["ha"] = (g.area / 1e4).round(1)
g["geometry"] = g.simplify(6, preserve_topology=True)
g = g.to_crs(4326)[["ha", "geometry"]].reset_index(drop=True)
g["id"] = g.index.astype(str)
out = json.loads(g.to_json(drop_id=True))
def rnd(c):
    return [rnd(x) for x in c] if isinstance(c[0], list) else [round(c[0], 5), round(c[1], 5)]
for f in out["features"]:
    f["geometry"]["coordinates"] = rnd(f["geometry"]["coordinates"])
json.dump(out, open("data/chataigniers.geojson", "w"), separators=(",", ":"))
print(len(g), "peuplements,", round(g.ha.sum()), "ha")
