/* ChâtaignFinder — carte légère des coins à châtaignes autour de Grenoble. */
(() => {
  'use strict';

  const TYPES = {
    spot:      { label: 'Coins à châtaignes', one: 'Coin à châtaignes', ico: '🌰', color: '#c2561b' },
    rando:     { label: 'Randos', one: 'Rando avec châtaigniers', ico: '🥾', color: '#5f6b3a' },
    parking:   { label: 'Parkings', one: 'Parking', ico: 'P', color: '#2f6f8f' },
    pkprob:    { label: 'Parkings à vérifier', one: 'Parking probable (à vérifier)', ico: 'P?', color: '#6f93a8' },
    arbre:     { label: 'Arbres remarquables', one: 'Arbre remarquable', ico: '🌳', color: '#8a6a1f' },
    attention: { label: 'Attention / privé', one: 'Attention', ico: '!', color: '#a3261b' },
    achat:     { label: 'Acheter local', one: 'Acheter des châtaignes', ico: '🧺', color: '#8a5a1d' },
    mine:      { label: 'Mes spots', one: 'Mon spot', ico: '⭐', color: '#d99a2b' },
  };
  const CONF = ['', 'Indice faible', 'Plausible', 'Probable', 'Fiable', 'Très fiable'];
  const HOME = [45.19, 5.80, 12]; // entre Meylan, le Mûrier et Belledonne

  const state = {
    points: [], mine: loadMine(), verif: loadVerif(), me: null,
    types: new Set(Object.keys(TYPES)), minConf: 1,
    view: 'home', selected: null, adding: false,
  };

  // ---------- Carte & fonds ----------
  const ign = (layer, fmt = 'image/png', style = 'normal') =>
    `https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=${layer}&STYLE=${style}` +
    `&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&FORMAT=${fmt}`;
  const IGN_ATTR = '&copy; <a href="https://www.ign.fr/">IGN</a>';
  const OSM_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';

  const bases = {
    plan: { name: 'Plan IGN (chemins détaillés)', layer: L.tileLayer(ign('GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2'), { maxZoom: 19, attribution: IGN_ATTR }) },
    topo: { name: 'Topo OSM (sentiers + relief)', layer: L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', { maxZoom: 19, maxNativeZoom: 17, subdomains: 'abc', attribution: OSM_ATTR + ', <a href="https://opentopomap.org">OpenTopoMap</a>' }) },
    ortho: { name: 'Vue satellite IGN', layer: L.tileLayer(ign('ORTHOIMAGERY.ORTHOPHOTOS', 'image/jpeg'), { maxZoom: 19, attribution: IGN_ATTR }) },
  };

  const forestLayer = L.geoJSON(null, {
    style: { color: '#7a3e1d', weight: 1.5, fillColor: '#c2561b', fillOpacity: 0.42 },
    onEachFeature: (f, l) => l.bindPopup(
      `<b>🌰 Châtaigniers purs</b><br>${f.properties.ha} ha · IGN BD Forêt V2<br>` +
      `<span style="color:#8a6a52">Forêt dominée par le châtaignier. Vérifiez sur place qu'il ne s'agit pas d'un terrain privé ou d'un verger.</span>`),
  });
  const forestDots = L.layerGroup();
  const forestGroup = L.layerGroup([forestLayer]);

  const overlays = {
    forest: { name: 'Zones de châtaigniers (IGN)', layer: forestGroup, on: true },
    marked: { name: 'Sentiers balisés (Waymarked Trails)', layer: L.tileLayer('https://tile.waymarkedtrails.org/hiking/{z}/{x}/{y}.png', { maxZoom: 19, opacity: 0.6, attribution: '<a href="https://hiking.waymarkedtrails.org">Waymarked Trails</a>' }), on: true },
    shade: { name: 'Relief ombré', layer: L.tileLayer(ign('ELEVATION.ELEVATIONGRIDCOVERAGE.SHADOW', 'image/png', 'estompage_grayscale'), { maxZoom: 19, maxNativeZoom: 15, opacity: 0.3, attribution: IGN_ATTR }), on: false },
    allforest: { name: 'Toutes forêts IGN (par essence)', layer: L.tileLayer(ign('LANDCOVER.FORESTINVENTORY.V2'), { maxZoom: 19, maxNativeZoom: 16, minZoom: 6, opacity: 0.5, attribution: IGN_ATTR }), on: false },
  };

  const map = L.map('map', { zoomControl: false, attributionControl: true }).setView(HOME.slice(0, 2), HOME[2]);
  L.control.scale({ imperial: false, position: 'bottomleft' }).addTo(map);
  readHash();
  let currentBase = 'plan';
  bases[currentBase].layer.addTo(map);
  Object.values(overlays).forEach(o => o.on && o.layer.addTo(map));
  const markers = L.layerGroup().addTo(map);
  let meMarker = null;

  // ---------- Données ----------
  Promise.all([
    fetch('data/chataigniers.geojson').then(r => r.json()),
    fetch('data/points.json').then(r => r.json()),
  ]).then(([forest, pts]) => {
    forestLayer.addData(forest);
    forestLayer.eachLayer(l => {
      const c = l.getBounds().getCenter();
      L.marker(c, { icon: L.divIcon({ className: '', html: '<div class="cluster-dot"></div>', iconSize: [8, 8] }), interactive: false }).addTo(forestDots);
    });
    state.points = pts.points;
    state.meta = pts.meta;
    updateForestDots();
    renderMarkers();
    render();
  }).catch(err => {
    body.innerHTML = `<p class="box warn">Impossible de charger les données (${esc(err.message)}).</p>`;
  });

  function updateForestDots() {
    // Les petits peuplements disparaissent à faible zoom : on les signale par un point.
    if (map.getZoom() < 13 && map.hasLayer(forestGroup)) forestGroup.addLayer(forestDots);
    else forestGroup.removeLayer(forestDots);
  }

  // ---------- Marqueurs ----------
  function allPoints() {
    const pts = [];
    for (const p of state.points) {
      const v = state.verif[p.id];
      if (v && v.v === 'ko') continue;
      pts.push(v && v.v === 'ok'
        ? { ...p, type: 'parking', verified: true, conf: Math.max(p.conf, 4), name: p.name.replace(' (parking à vérifier)', ' (vérifié)'), why: 'vérifié par vous' }
        : p);
    }
    return pts.concat(state.mine.map(m => ({ ...m, type: 'mine', conf: 5 })));
  }
  const isPark = t => t === 'parking' || t === 'pkprob';
  function visiblePoints() {
    return allPoints().filter(p => state.types.has(p.type) && (p.type === 'mine' || p.conf >= state.minConf));
  }
  function icon(p, sel) {
    const t = TYPES[p.type];
    if (isPark(p.type)) {
      const cls = p.type === 'pkprob' ? ' prob' : (p.verified ? ' ok' : '');
      return L.divIcon({ className: '', iconSize: [22, 22], iconAnchor: [11, 11],
        html: `<div class="pk${cls}${sel ? ' sel' : ''}">${p.type === 'pkprob' ? 'P?' : 'P'}</div>` });
    }
    const txt = t.ico.length === 1 && /[A-Z!]/.test(t.ico) ? `<b style="color:#fff;font-size:15px">${t.ico}</b>` : t.ico;
    return L.divIcon({
      className: '', iconSize: [32, 32], iconAnchor: [4, 32],
      html: `<div class="pin${p.conf <= 2 ? ' low' : ''}${sel ? ' sel' : ''}" style="background:${t.color}"><span>${txt}</span></div>`,
    });
  }
  function renderMarkers() {
    markers.clearLayers();
    const z = map.getZoom();
    for (const p of visiblePoints()) {
      const sel = state.selected && state.selected.id === p.id;
      if (!sel && ((p.type === 'parking' && z < 13) || (p.type === 'pkprob' && z < 14))) continue;
      L.marker([p.lat, p.lon], { icon: icon(p, state.selected && state.selected.id === p.id), title: p.name, riseOnHover: true })
        .on('click', () => { openDetail(p); focus(p, map.getZoom()); })
        .addTo(markers);
    }
  }

  // ---------- Panneau ----------
  const sheet = document.getElementById('sheet');
  const body = document.getElementById('sheet-body');
  document.getElementById('sheet-grip').onclick = e => { e.stopPropagation(); sheet.classList.toggle('open'); };
  sheet.addEventListener('click', () => sheet.classList.add('open'));

  function render() {
    if (state.view === 'detail' && state.selected) return renderDetail(state.selected);
    if (state.view === 'about') return renderAbout();
    renderHome();
  }

  function renderHome() {
    const ref = state.me || map.getCenter();
    // Les parkings sont proposés dans la fiche de chaque spot, pas dans la liste.
    const pts = visiblePoints().filter(p => !isPark(p.type))
      .map(p => ({ p, d: dist(ref, p) })).sort((a, b) => a.d - b.d).slice(0, 40);
    const counts = {};
    allPoints().forEach(p => counts[p.type] = (counts[p.type] || 0) + 1);
    body.innerHTML = `
      <h2>Châtaignes autour de Grenoble</h2>
      <p class="lede"><span class="legend-swatch"></span> zones de châtaigniers purs (IGN). Les points recoupent forums, blogs, randos et OpenStreetMap, avec un <b>score de confiance</b>.</p>
      <div class="chips">${Object.entries(TYPES).filter(([k]) => counts[k]).map(([k, t]) =>
        `<button class="chip" data-type="${k}" aria-pressed="${state.types.has(k)}"><span class="dot" style="background:${t.color}"></span>${t.label} <small>${counts[k]}</small></button>`).join('')}
      </div>
      <div class="section-title">Confiance minimale</div>
      <div class="seg">${[1, 2, 3, 4].map(c =>
        `<button data-conf="${c}" aria-pressed="${state.minConf === c}">${c === 1 ? 'Tout' : c + '+ ●'}</button>`).join('')}
      </div>
      <div class="section-title">${state.me ? 'Les plus proches de vous' : 'Les plus proches du centre de la carte'}</div>
      <ul class="list">${pts.map(({ p, d }) => `
        <li><button data-id="${p.id}">
          <span class="ico">${listIco(p.type)}</span>
          <span class="grow"><span class="t">${esc(p.name)}</span><br>
            <span class="s">${p.type === 'mine' ? 'Mon spot' : confDots(p.conf)} ${esc(p.commune || '')}</span></span>
          <span class="km">${fmtKm(d)}</span>
        </button></li>`).join('') || '<li class="lede">Aucun point avec ces filtres.</li>'}
      </ul>
      <p class="lede">🅿️ Les parkings apparaissent en zoomant (les « P? » à vérifier à partir du zoom 14), et dans la fiche de chaque spot.</p>
      <p class="lede">💡 Touchez <b>＋</b> pour noter vos propres coins (gardés sur cet appareil).</p>`;
    body.querySelectorAll('[data-type]').forEach(b => b.onclick = () => {
      const k = b.dataset.type;
      state.types.has(k) ? state.types.delete(k) : state.types.add(k);
      renderMarkers(); renderHome();
    });
    body.querySelectorAll('[data-conf]').forEach(b => b.onclick = () => {
      state.minConf = +b.dataset.conf; renderMarkers(); renderHome();
    });
    body.querySelectorAll('[data-id]').forEach(b => b.onclick = () => {
      const p = allPoints().find(x => x.id === b.dataset.id);
      if (p) { openDetail(p); focus(p, Math.max(map.getZoom(), 15)); }
    });
  }

  function openDetail(p) {
    state.selected = p; state.view = 'detail';
    renderMarkers(); renderDetail(p);
    sheet.classList.add('open');
    body.scrollTop = 0;
  }

  function renderDetail(p) {
    const t = TYPES[p.type];
    const facts = [];
    if (state.me) facts.push(`📍 ${fmtKm(dist(state.me, p))} de vous`);
    if (p.alt) facts.push(`⛰️ ${p.alt} m`);
    if (p.rando) {
      if (p.rando.km) facts.push(`🥾 ${p.rando.km} km`);
      if (p.rando.dplus) facts.push(`↗ ${p.rando.dplus} m D+`);
      if (p.rando.duree) facts.push(`⏱ ${p.rando.duree}`);
    }
    if (p.bdforet != null) facts.push(p.bdforet === 0 ? '🌰 dans une zone IGN' : `🌰 zone IGN à ${fmtKm(p.bdforet / 1000)}`);
    const ll = `${p.lat.toFixed(5)},${p.lon.toFixed(5)}`;
    body.innerHTML = `
      <button class="back" id="back">← Retour</button>
      <div class="detail-head">
        <span class="ico">${listIco(p.type)}</span>
        <div><div class="kind">${t.one}${p.commune ? ' · ' + esc(p.commune) : ''}</div>
          <h2>${esc(p.name)}</h2>
          ${p.type === 'mine' ? '' : `${confDots(p.conf)}<span class="conf-label">${CONF[p.conf]} (${p.conf}/5)</span>`}
        </div>
      </div>
      ${facts.length ? `<div class="facts">${facts.map(f => `<span class="fact">${f}</span>`).join('')}</div>` : ''}
      ${p.desc ? `<div class="box">${paras(p.desc)}</div>` : ''}
      ${p.acces ? `<div class="box tip"><p><b>Se garer / par où commencer</b></p>${paras(p.acces)}</div>` : ''}
      ${p.warn ? `<div class="box warn">${paras(p.warn)}</div>` : ''}
      <div class="actions">
        <a class="btn primary" target="_blank" rel="noopener" href="https://www.google.com/maps/dir/?api=1&destination=${ll}">🚗 Y aller</a>
        <a class="btn" target="_blank" rel="noopener" href="https://waze.com/ul?ll=${ll}&navigate=yes">Waze</a>
        <button class="btn" id="copy">📋 ${ll}</button>
        <button class="btn" id="zoom">🔍 Zoomer</button>
      </div>
      ${isPark(p.type) ? parkingTools(p, ll) : ''}
      ${nearParkings(p)}
      ${p.sources && p.sources.length ? `<div class="section-title">Sources (${p.sources.length})</div>
        <ul class="sources">${p.sources.map(s => `<li>${s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.label)}</a>` : esc(s.label)}${s.date ? ` <span class="d">· ${esc(s.date)}</span>` : ''}${s.quote ? `<br><i>« ${esc(s.quote)} »</i>` : ''}</li>`).join('')}</ul>` : ''}
      ${p.why ? `<p class="why"><b>Pourquoi ce score :</b> ${esc(p.why)}</p>` : ''}
      ${p.type === 'mine' ? `<p class="lede">${p.note ? esc(p.note) + '<br>' : ''}Ajouté le ${new Date(p.date).toLocaleDateString('fr-FR')}</p>
        <div class="actions"><button class="btn" id="rename">✏️ Renommer</button><button class="btn danger" id="del">🗑 Supprimer</button></div>` : ''}`;
    document.getElementById('back').onclick = goHome;
    body.querySelectorAll('[data-pk]').forEach(b => b.onclick = () => {
      const pk = allPoints().find(x => x.id === b.dataset.pk);
      openDetail(pk); focus(pk, Math.max(map.getZoom(), 15));
    });
    document.getElementById('zoom').onclick = () => focus(p, 16);
    body.querySelectorAll('[data-verif]').forEach(b => b.onclick = () => {
      const v = b.dataset.verif;
      if (v === 'reset') delete state.verif[p.id];
      else state.verif[p.id] = { v, lat: p.lat, lon: p.lon, name: p.name, date: new Date().toISOString().slice(0, 10) };
      saveVerif();
      if (v === 'ko') return goHome();
      const fresh = allPoints().find(x => x.id === p.id);
      openDetail(fresh || p);
    });
    document.getElementById('copy').onclick = e => {
      navigator.clipboard && navigator.clipboard.writeText(ll).then(() => { e.target.textContent = '✓ Copié'; });
    };
    if (p.type === 'mine') {
      document.getElementById('del').onclick = () => {
        if (!confirm('Supprimer ce spot ?')) return;
        state.mine = state.mine.filter(m => m.id !== p.id); saveMine(); goHome();
      };
      document.getElementById('rename').onclick = () => {
        const n = prompt('Nouveau nom', p.name); if (!n) return;
        const m = state.mine.find(x => x.id === p.id); m.name = n; saveMine(); openDetail({ ...m, type: 'mine', conf: 5 });
      };
    }
  }

  function parkingTools(p, ll) {
    const v = state.verif[p.id];
    return `
      <div class="actions">
        <a class="btn" target="_blank" rel="noopener" href="https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${ll}">👁 Street View</a>
        <a class="btn" target="_blank" rel="noopener" href="https://www.google.com/maps/@?api=1&map_action=map&center=${ll}&zoom=19&basemap=satellite">🛰 Satellite</a>
      </div>
      <div class="box verif">
        ${v ? `<p>${v.v === 'ok' ? '✓ Vous avez confirmé ce parking' : '✗ Marqué sans place'} le ${esc(v.date)}.</p>
          <button class="btn" data-verif="reset">Annuler ma vérification</button>`
        : `<p><b>Vous avez vérifié (Street View ou sur place) ?</b></p>
          <div class="actions"><button class="btn ok" data-verif="ok">✓ On peut se garer</button><button class="btn danger" data-verif="ko">✗ Pas de place</button></div>
          <p class="why">Gardé sur cet appareil. Les parkings refusés disparaissent de la carte ; vous pouvez m'envoyer vos vérifications depuis le panneau ⓘ.</p>`}
      </div>`;
  }

  function nearParkings(p) {
    if (isPark(p.type)) return '';
    const near = allPoints().filter(x => isPark(x.type)).map(x => ({ x, d: dist(p, x) })).filter(o => o.d < 3);
    const sure = near.filter(o => o.x.type === 'parking').sort((a, b) => a.d - b.d).slice(0, 3);
    const prob = near.filter(o => o.x.type === 'pkprob').sort((a, b) => a.d - b.d).slice(0, 2);
    const pk = sure.concat(prob);
    if (!pk.length) return '';
    return `<div class="section-title">Où se garer à proximité</div><ul class="list">${pk.map(({ x, d }) => `
      <li><button data-pk="${x.id}"><span class="ico">${listIco(x.type, x.verified)}</span>
        <span class="grow"><span class="t">${esc(x.name)}</span><br><span class="s">${confDots(x.conf)} ${esc(x.verified ? 'vérifié par vous' : x.why)}</span></span>
        <span class="km">${fmtKm(d)}</span></button></li>`).join('')}</ul>`;
  }

  // Centre le point dans la partie de carte visible (au-dessus du panneau sur mobile).
  function focus(p, z) {
    const mobile = window.innerWidth < 860;
    const pt = map.project([p.lat, p.lon], z);
    if (mobile) pt.y += map.getSize().y * 0.34;
    else pt.x -= 190;
    map.setView(map.unproject(pt, z), z);
  }

  function goHome() {
    state.view = 'home'; state.selected = null; renderMarkers(); renderHome(); body.scrollTop = 0;
  }

  function renderAbout() {
    const m = state.meta || {};
    body.innerHTML = `
      <button class="back" id="back">← Retour</button>
      <h2>Bien ramasser 🍂</h2>
      <ul class="small">
        <li><b>Saison :</b> fin septembre → début novembre, pic vers mi-octobre. Les châtaigniers poussent surtout entre 250 et 900 m, sur les sols acides (pied de Belledonne, colline du Mûrier, plateau de Jarrie). Plus haut = plus tard.</li>
        <li><b>Ce qui est permis :</b> en forêt publique (domaniale, communale), la cueillette est tolérée pour un usage familial, en quantité raisonnable (au-delà de 10 L, c'est une contravention). Ramassez au sol, ne secouez pas les arbres.</li>
        <li><b>Ce qui ne l'est pas :</b> une châtaigneraie entretenue (sol fauché, filets, arbres greffés alignés) ou un terrain privé, même sans clôture : c'est la récolte de quelqu'un.</li>
        <li><b>Chasse :</b> les battues sont fréquentes en automne, souvent le mercredi et le week-end. Restez sur les chemins, portez une couleur vive, respectez les panneaux « chasse en cours ».</li>
        <li><b>Tri :</b> gants épais ou petite pince pour les bogues. À la maison, plongez-les dans l'eau : celles qui flottent sont souvent véreuses.</li>
        <li><b>Châtaigne ≠ marron d'Inde :</b> la bogue de la châtaigne pique comme un hérisson et contient 2–3 fruits aplatis à pointe ; le marron d'Inde (toxique) a une coque à piquants espacés et un seul fruit rond.</li>
      </ul>
      <div class="section-title">Lire la carte</div>
      <ul class="small">
        <li><span class="legend-swatch"></span> <b>Zones orange</b> : peuplements de <i>châtaigniers purs</i> ≥ 2,25 ha (IGN BD Forêt V2, code FF1-10-10). Les châtaigniers existent aussi dans les forêts « feuillus mélangés » (Belledonne, Chartreuse) : activez le calque <i>Toutes forêts IGN</i> pour les voir.</li>
        <li><b>Score de confiance (1 à 5)</b> : part du type de source (témoignage, fiche rando, donnée officielle), +1 par source indépendante qui confirme, + bonus si le point est dans ou près d'une zone IGN, − malus si la source est vague ou ancienne. Le détail est donné sous chaque point.</li>
        <li><b>Parkings P</b> : OpenStreetMap, IGN BD TOPO (dont les « parkings touristiques isolés » des départs de sentier), points de départ des randos Visorando et parkings cités par les sources. Plus il y a de sources au même endroit, plus le score est haut.</li>
        <li><b>Parkings P?</b> (à vérifier) : endroits où un sentier ou une piste qui traverse une zone de châtaigniers rejoint une route, ou départs de rando sans parking mentionné. Il y a souvent un bas-côté ou une petite aire. Vérifiez avec 👁 Street View puis marquez ✓ ou ✗.</li>
      </ul>
      ${verifSummary()}
      <div class="section-title">Sources principales</div>
      <ul class="sources">${(m.sources || []).map(s => `<li><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.label)}</a></li>`).join('')}</ul>
      <p class="lede">Données : IGN (BD Forêt V2, Plan IGN, ortho), © contributeurs OpenStreetMap, OpenTopoMap, Waymarked Trails. Mise à jour : ${esc(m.updated || '')}.</p>
      <p class="lede">Une erreur, un coin à ajouter ? <a href="https://github.com/Benoit62/ChataignFinder/issues" target="_blank" rel="noopener">Ouvrez une issue</a>.</p>`;
    document.getElementById('back').onclick = goHome;
    const cp = document.getElementById('verif-copy');
    if (cp) cp.onclick = () => {
      const txt = Object.values(state.verif).map(v => `${v.v === 'ok' ? 'OK' : 'NON'} ${v.lat.toFixed(5)},${v.lon.toFixed(5)} ${v.name} (${v.date})`).join('\n');
      navigator.clipboard && navigator.clipboard.writeText(txt).then(() => { cp.textContent = '✓ Copié'; });
    };
    const clr = document.getElementById('verif-clear');
    if (clr) clr.onclick = () => { if (confirm('Effacer toutes vos vérifications ?')) { state.verif = {}; saveVerif(); renderAbout(); } };
  }

  function verifSummary() {
    const vs = Object.values(state.verif);
    if (!vs.length) return '';
    const ok = vs.filter(v => v.v === 'ok').length;
    return `<div class="section-title">Mes vérifications de parkings</div>
      <p class="small">${ok} confirmé(s) ✓ · ${vs.length - ok} refusé(s) ✗. Copiez-les pour me les envoyer : je les intégrerai aux données pour tout le monde.</p>
      <div class="actions"><button class="btn" id="verif-copy">📋 Copier la liste</button><button class="btn danger" id="verif-clear">Tout effacer</button></div>`;
  }

  // ---------- Boutons ----------
  const btnLayers = document.getElementById('btn-layers');
  const layersPanel = document.getElementById('layers-panel');
  btnLayers.onclick = () => { layersPanel.hidden = !layersPanel.hidden; btnLayers.classList.toggle('active', !layersPanel.hidden); };
  document.getElementById('base-list').innerHTML = Object.entries(bases).map(([k, b]) =>
    `<label><input type="radio" name="base" value="${k}" ${k === currentBase ? 'checked' : ''}> ${b.name}</label>`).join('');
  document.getElementById('overlay-list').innerHTML = Object.entries(overlays).map(([k, o]) =>
    `<label><input type="checkbox" value="${k}" ${o.on ? 'checked' : ''}> ${o.name}</label>`).join('');
  layersPanel.addEventListener('change', e => {
    const el = e.target;
    if (el.name === 'base') {
      map.removeLayer(bases[currentBase].layer); currentBase = el.value;
      bases[currentBase].layer.addTo(map); bases[currentBase].layer.bringToBack();
    } else {
      const o = overlays[el.value];
      el.checked ? o.layer.addTo(map) : map.removeLayer(o.layer);
      updateForestDots();
    }
  });
  map.on('click', () => { if (!state.adding) sheet.classList.remove('open'); if (!layersPanel.hidden) { layersPanel.hidden = true; btnLayers.classList.remove('active'); } });

  document.getElementById('btn-info').onclick = () => { state.view = 'about'; renderAbout(); sheet.classList.add('open'); body.scrollTop = 0; };

  const btnLocate = document.getElementById('btn-locate');
  btnLocate.onclick = () => { btnLocate.classList.add('active'); map.locate({ enableHighAccuracy: true, maximumAge: 30000 }); };
  map.on('locationfound', e => {
    btnLocate.classList.remove('active');
    state.me = e.latlng;
    if (!meMarker) meMarker = L.marker(e.latlng, { icon: L.divIcon({ className: '', html: '<div class="me-dot"></div>', iconSize: [16, 16] }), zIndexOffset: 1000 }).addTo(map);
    else meMarker.setLatLng(e.latlng);
    map.setView(e.latlng, Math.max(map.getZoom(), 14));
    render();
  });
  map.on('locationerror', e => { btnLocate.classList.remove('active'); alert('Localisation impossible : ' + e.message); });

  const hint = document.getElementById('add-hint');
  const btnAdd = document.getElementById('btn-add');
  const setAdding = on => {
    state.adding = on; hint.hidden = !on; btnAdd.classList.toggle('active', on);
    map.getContainer().style.cursor = on ? 'crosshair' : '';
  };
  btnAdd.onclick = () => setAdding(!state.adding);
  document.getElementById('add-cancel').onclick = () => setAdding(false);
  map.on('click', e => {
    if (!state.adding) return;
    setAdding(false);
    const name = prompt('Nom de ce spot ?', 'Mon coin à châtaignes');
    if (!name) return;
    const note = prompt('Une note ? (facultatif)', '') || '';
    const m = { id: 'mine-' + Date.now(), name, note, lat: e.latlng.lat, lon: e.latlng.lng, date: Date.now() };
    state.mine.push(m); saveMine();
    openDetail({ ...m, type: 'mine', conf: 5 });
  });

  let moveTimer;
  map.on('moveend', () => {
    writeHash();
    clearTimeout(moveTimer);
    moveTimer = setTimeout(() => { if (state.view === 'home' && !state.me) renderHome(); }, 250);
  });
  map.on('zoomend', () => { updateForestDots(); renderMarkers(); });

  // ---------- Saison ----------
  (() => {
    const d = new Date(), m = d.getMonth() + 1, day = d.getDate();
    let txt = 'Hors saison · revenez fin septembre';
    if (m === 9 && day >= 15) txt = '🍂 Début de saison';
    else if (m === 10) txt = day <= 25 ? '🍂 Pleine saison' : '🍂 Saison bien avancée';
    else if (m === 11 && day <= 15) txt = '🍂 Fin de saison (plutôt en basse altitude)';
    document.getElementById('season').textContent = txt;
  })();

  // ---------- Utilitaires ----------
  function dist(a, b) {
    const R = 6371, toR = Math.PI / 180;
    const lat1 = (a.lat) * toR, lat2 = b.lat * toR;
    const dLat = lat2 - lat1, dLon = ((b.lon ?? b.lng) - (a.lng ?? a.lon)) * toR;
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(h));
  }
  function fmtKm(km) { return km < 1 ? Math.round(km * 1000 / 10) * 10 + ' m' : (km < 10 ? km.toFixed(1) : Math.round(km)) + ' km'; }
  function listIco(type, verified) {
    if (type === 'parking') return `<span class="pk${verified ? ' ok' : ''}">P</span>`;
    if (type === 'pkprob') return '<span class="pk prob">P?</span>';
    if (type === 'attention') return '<span class="pk warn">!</span>';
    return TYPES[type].ico;
  }
  function confDots(c) { return `<span class="conf" title="Confiance ${c}/5">${[1, 2, 3, 4, 5].map(i => `<i class="${i <= c ? 'on' : ''}"></i>`).join('')}</span>`; }
  function esc(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
  function paras(s) { return String(s).split('\n').map(x => `<p>${esc(x)}</p>`).join(''); }
  function loadMine() { try { return JSON.parse(localStorage.getItem('cf-mine')) || []; } catch { return []; } }
  function loadVerif() { try { return JSON.parse(localStorage.getItem('cf-verif')) || {}; } catch { return {}; } }
  function saveVerif() { try { localStorage.setItem('cf-verif', JSON.stringify(state.verif)); } catch { /* stockage indisponible */ } renderMarkers(); }
  function saveMine() { try { localStorage.setItem('cf-mine', JSON.stringify(state.mine)); } catch { /* stockage indisponible */ } renderMarkers(); }
  function readHash() {
    const m = location.hash.match(/^#(\d+(?:\.\d+)?)\/(-?\d+\.\d+)\/(-?\d+\.\d+)/);
    if (m) map.setView([+m[2], +m[3]], +m[1]);
  }
  function writeHash() {
    const c = map.getCenter();
    history.replaceState(null, '', `#${map.getZoom()}/${c.lat.toFixed(4)}/${c.lng.toFixed(4)}`);
  }
})();
