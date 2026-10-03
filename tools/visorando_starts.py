"""Récupère les points de départ des randos Visorando autour de Grenoble est / sud-est
→ tools/visorando_starts.json (nom, url, coordonnées, phrase sur le stationnement).

Lent exprès (une requête à la fois, ~15 min) pour ne pas surcharger le site.
Usage : python tools/visorando_starts.py
"""
import html, json, re, time, urllib.request

ROOT = __file__.replace("\\", "/").rsplit("/tools/", 1)[0]
UA = {"User-Agent": "Mozilla/5.0 (ChataignFinder; low rate)"}
COMMUNES = """grenoble meylan corenc la-tronche biviers saint-ismier saint-nazaire-les-eymes montbonnot-saint-martin crolles
bernin lumbin la-terrasse le-touvet sainte-marie-du-mont barraux chapareillan saint-martin-d-uriage domene gieres
saint-martin-d-heres murianette le-versoud revel saint-jean-le-vieux villard-bonnot saint-mury-monteymond froges la-pierre
tencin theys les-adrets hurtieres laval sainte-agnes goncelin le-cheylas pontcharra allevard crets-en-belledonne
la-chapelle-du-bard herbeys eybens poisat brie-et-angonnes venon vaulnaveys-le-haut vaulnaveys-le-bas vizille jarrie
champagnier notre-dame-de-mesage saint-pierre-de-mesage sechilienne saint-barthelemy-de-sechilienne laffrey
saint-georges-de-commiers vif claix varces-allieres-et-risset le-sappey-en-chartreuse sarcenas quaix-en-chartreuse
saint-egreve seyssinet-pariset saint-pierre-d-allevard le-moutaret la-buissiere""".split()


def get(url):
    try:
        return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read().decode("utf-8", "replace")
    except Exception:
        return ""


urls = set()
for c in COMMUNES:
    urls |= set(re.findall(r'href="(https://www\.visorando\.com/randonnee-[^"]+/)"', get(f"https://www.visorando.com/randonnee-{c}.html")))
    time.sleep(0.4)
print(len(urls), "randos")

out = []
for u in sorted(urls):
    h = get(u)
    time.sleep(0.35)
    ld = None
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', h, re.S):
        try:
            j = json.loads(m.group(1))
            ld = j if j.get("geo") else ld
        except ValueError:
            pass
    if not ld:
        continue
    i = h.find("route_sheet_text_content")
    txt = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h[i:i + 20000] if i > 0 else "")))
    pk = re.findall(r"[^.!?]{0,140}(?:[Pp]arking|[Ss]e garer|[Ss]tationne|garer)[^.!?]{0,160}", txt)
    out.append({"url": u, "name": html.unescape(ld.get("name", "")), "lat": float(ld["geo"]["latitude"]),
                "lon": float(ld["geo"]["longitude"]), "parking": [p.strip() for p in pk[:2]]})
json.dump(out, open(f"{ROOT}/tools/visorando_starts.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(len(out), "départs enregistrés")
