# 🌰 ChâtaignFinder

Petite carte web (mobile d'abord) pour trouver où ramasser des châtaignes autour de Grenoble, surtout côté **est / sud-est** : Grésivaudan, balcons de Belledonne, colline du Mûrier, Uriage, Jarrie et Vizille.

**→ https://benoit62.github.io/ChataignFinder/**

## Ce que fait l'app

- **Zones de châtaigniers** (en orange) : peuplements de *châtaigniers purs* de la BD Forêt V2 de l'IGN, qui est la donnée de la carte IGN des forêts. 72 zones, 2 770 ha. À faible zoom, un point marque chaque zone pour ne pas rater les petites.
- **Fonds de carte pour marcher** : Plan IGN (tous les chemins), Topo OSM (sentiers et courbes de niveau) ou vue satellite IGN. On peut y superposer les sentiers balisés (Waymarked Trails), le relief ombré ou toutes les forêts IGN par essence.
- **Points recoupés**, chacun avec un **score de confiance de 1 à 5** :
  - 🌰 coins à châtaignes et 🥾 randos qui en parlent : par où commencer, où se garer, les sources et ce qu'elles citent ;
  - **P** parkings : ceux que citent les sources, plus les parkings publics OpenStreetMap à moins de 200 m d'une zone. Chaque fiche liste les 3 parkings les plus proches ;
  - 🌳 arbres remarquables et **!** vergers privés à éviter.
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

Le total est arrondi et borné entre 1 et 5. Les parkings ont leur propre barème : 4 s'ils sont cités par une source, sinon 3 ou 2 selon leur distance à une zone.

## Sources recoupées

- **IGN BD Forêt V2**, via le WFS de la Géoplateforme (`code_tfv = FF1-10-10`, « forêt fermée de châtaignier pur »).
- **Forums et blogs** : Skipass « Des petits coins à châtaignes ? », Qcunbon Grenoble, Mômes à Grenoble, Chloé Clafoutis, Krapo arboricole.
- **Fiches rando** : Visorando (j'ai parcouru environ 640 randos dans 70 communes et gardé celles qui parlent de châtaignes dans leur propre texte), Decathlon Outdoor, Grenoble Tourisme et Alpes Isère.
- **OpenStreetMap** : parkings, arbres `Castanea sativa`, toponymes « Châtaigneraie » ou « Châtaignier ».

Le fil Reddit r/Grenoble n'a pas pu être lu automatiquement (accès bloqué). Ses spots peuvent être ajoutés à la main (voir plus bas).

Ce que la recherche montre :
- Les sources les plus solides sont **Haute-Jarrie / Champagnier**, **Eybens (forêt des Arcelles)** et la **colline du Mûrier**.
- Les gros massifs de **Combeloup** et des balcons de **Saint-Jean-le-Vieux** sont presque absents des forums alors qu'ils sont immenses. Ce sont de bonnes pistes à explorer.
- Sur les balcons de Belledonne (Les Adrets, Hurtières, Theys), les châtaigniers poussent dans des forêts mélangées, que la BD Forêt ne classe pas en « châtaignier pur ». Le calque « Toutes forêts IGN » aide à les repérer.
- Aucune source fiable n'a été trouvée pour les pentes de Chartreuse au-dessus de Meylan.

## Mettre à jour les données

```bash
pip install geopandas shapely
python tools/build_forest.py   # télécharge les zones IGN → data/chataigniers.geojson
python tools/build_points.py   # spots + scores + parkings OSM → data/points.json
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
