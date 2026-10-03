# 🌰 ChâtaignFinder

Petite carte web (mobile d'abord) pour trouver où ramasser des châtaignes autour de Grenoble, surtout côté **est / sud-est** : Grésivaudan, balcons de Belledonne, colline du Mûrier, Uriage, Jarrie et Vizille.

**→ https://benoit62.github.io/ChataignFinder/**

## Ce que fait l'app

- **Zones de châtaigniers** (en orange) : peuplements de *châtaigniers purs* de la BD Forêt V2 de l'IGN, qui est la donnée de la carte IGN des forêts. 72 zones, 2 770 ha. À faible zoom, un point marque chaque zone pour ne pas rater les petites.
- **Fonds de carte pour marcher** : Plan IGN (tous les chemins), Topo OSM (sentiers et courbes de niveau) ou vue satellite IGN. On peut y superposer les sentiers balisés (Waymarked Trails), le relief ombré ou toutes les forêts IGN par essence.
- **Points recoupés**, chacun avec un **score de confiance de 1 à 5** :
  - 🌰 coins à châtaignes et 🥾 randos qui en parlent : par où commencer, où se garer, les sources et ce qu'elles citent ;
  - **P** parkings : fusion de quatre sources (parkings cités, OpenStreetMap, IGN BD TOPO, départs de randos Visorando) ;
  - **P?** parkings probables, à vérifier : endroits où un sentier qui traverse une zone de châtaigniers rejoint une route. Chaque fiche a un bouton 👁 Street View et des boutons ✓/✗ pour noter votre vérification ;
  - 🌳 arbres remarquables, **!** vergers privés à éviter, 🧺 où acheter local.
- **Où se garer** : chaque fiche de spot liste les 3 parkings sûrs et les 2 parkings probables les plus proches.
- **Pratique sur le terrain** : bouton de géolocalisation, liste triée par distance, liens « Y aller » (Google Maps ou Waze), copie des coordonnées GPS, et une URL qui garde la vue pour la partager.
- **Mes spots** : le bouton ＋ ajoute vos propres coins. Ils restent sur votre appareil (localStorage) et ne sont envoyés nulle part.
- **Conseils** (bouton ⓘ) : saison, ce que dit la loi, chasse, comment trier, comment ne pas confondre avec le marron d'Inde.

Pas de framework ni de build : un peu de HTML, de CSS et de JS, plus Leaflet. Le site pèse environ 300 ko de données.

## Score de confiance

Calculé par `tools/build_points.py` ; chaque fiche affiche le détail du calcul.

| Indice | Points |
|---|---|
| Base | 1 |
| Une source (forum, blog, fiche rando, office de tourisme) cite des châtaignes | +1 |
| Chaque source indépendante en plus (3 au maximum) | +0,5 |
| Une de ces sources date de moins de 5 ans | +0,5 |
| Seulement un indice OpenStreetMap (toponyme, arbre tagué) | +0,5 |
| Point dans un peuplement IGN de châtaigniers purs / à moins de 500 m / à moins de 1,5 km | +2 / +1 / +0,5 |
| Emplacement approximatif ou zone large | −0,5 |

Le total est arrondi et borné entre 1 et 5.

**Parkings** : le score indique la probabilité que le parking existe vraiment.

| Cas | Score |
|---|---|
| Cité par une source et confirmé par une donnée (OSM, IGN ou Visorando) | 5 |
| Cité par une source / présent dans au moins 2 données | 4 |
| Présent dans une seule donnée (OSM, IGN BD TOPO, ou départ Visorando qui parle de stationnement) | 3 |
| P? : départ de rando sans mention de stationnement, ou départ de sentier balisé (croisement sentier × route avec poteau de randonnée) | 2 |
| P? : simple croisement sentier × route menant aux châtaigniers | 1 |

Les P? ne sont retenus que si le sentier traverse une zone de châtaigniers, s'il n'y a pas déjà un parking connu à moins de 200 m, et s'ils sont espacés d'au moins 400 m.

Vos vérifications ✓/✗ restent sur votre appareil. Le panneau ⓘ permet de les copier : il suffit ensuite de les ajouter à `parkings` dans `tools/spots.json` pour les publier à tout le monde.

Google Maps et Strava ne sont pas utilisés comme sources : leurs conditions d'utilisation interdisent d'extraire leurs données, et la heatmap Strava demande d'être connecté. On s'en sert seulement pour vérifier (liens Street View et satellite).

## Sources recoupées

- **IGN BD Forêt V2**, via le WFS de la Géoplateforme (`code_tfv = FF1-10-10`, « forêt fermée de châtaignier pur »).
- **Forums et blogs** : fil Reddit r/Grenoble « Spot à châtaignes » (2024), Skipass « Des petits coins à châtaignes ? », Qcunbon Grenoble, Mômes à Grenoble, Chloé Clafoutis, Krapo arboricole.
- **Fiches rando** : Visorando (j'ai parcouru environ 640 randos dans 70 communes et gardé celles qui parlent de châtaignes dans leur propre texte), Decathlon Outdoor, Grenoble Tourisme et Alpes Isère.
- **OpenStreetMap** : parkings, sentiers, poteaux de randonnée, arbres `Castanea sativa`, toponymes « Châtaigneraie » ou « Châtaignier ».
- **IGN BD TOPO** : parkings, dont les « parkings touristiques isolés ».

Ce que la recherche montre :
- Les sources les plus solides sont **Haute-Jarrie / Champagnier / la Frange verte**, **Eybens (forêt des Arcelles, tour hertzienne)**, la **colline du Mûrier / les Quatre Seigneurs** et la forêt **sous le chêne de Pressembois (Venon)**. Le fil Reddit les confirme.
- Les gros massifs de **Combeloup** et des balcons de **Saint-Jean-le-Vieux** sont presque absents des forums alors qu'ils sont immenses. Ce sont de bonnes pistes à explorer.
- Sur les balcons de Belledonne (Les Adrets, Hurtières, Theys), les châtaigniers poussent dans des forêts mélangées, que la BD Forêt ne classe pas en « châtaignier pur ». Le calque « Toutes forêts IGN » aide à les repérer.
- Aucune source fiable n'a été trouvée pour les pentes de Chartreuse au-dessus de Meylan.

## Mettre à jour les données

```bash
pip install geopandas shapely
python tools/build_forest.py      # zones IGN → data/chataigniers.geojson
python tools/fetch_sources.py     # parkings OSM + IGN BD TOPO, routes et sentiers OSM → tools/raw/
python tools/visorando_starts.py  # (facultatif, ~15 min) départs des randos → tools/visorando_starts.json
python tools/build_points.py      # spots + scores + parkings → data/points.json
```

Pour ajouter ou corriger un spot, éditez `tools/spots.json` (le format est expliqué dans le champ `_doc`), puis relancez `build_points.py`.

## Lancer en local

```bash
python -m http.server 8000
```

Puis ouvrir http://localhost:8000.

## Déploiement

GitHub Pages, depuis la branche `main`, à la racine du dépôt.

## Rappel

La cueillette est tolérée en forêt publique pour un usage familial. En terrain privé et dans les châtaigneraies entretenues, c'est interdit. Les scores indiquent seulement une probabilité, pas une garantie, et aucun point n'autorise à entrer sur une propriété.

Données : © IGN, © contributeurs OpenStreetMap (ODbL), OpenTopoMap, Waymarked Trails.
