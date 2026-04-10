(function () {
  var path = (window.location && window.location.pathname) || '';
  var root = document.documentElement;
  if (path.indexOf('/delhi-metro/') === 0) {
    root.setAttribute('data-system', 'delhi-metro');
  } else if (path.indexOf('/bengaluru-metro/') === 0) {
    root.setAttribute('data-system', 'bengaluru-metro');
  } else if (path.indexOf('/namo-bharat/') === 0) {
    root.setAttribute('data-system', 'namo-bharat');
  } else if (path.indexOf('/meerut-metro/') === 0) {
    root.setAttribute('data-system', 'meerut-metro');
  }

  window.dataLayer = window.dataLayer || [];
  window.gtag = window.gtag || function gtag() { window.dataLayer.push(arguments); };
  window.gtag('js', new Date());

  var isStationDetail = /\/(delhi-metro|bengaluru-metro|namo-bharat|meerut-metro)\/stations\/[^/]+\.html$/i.test(path);
  if (isStationDetail) {
    window.gtag('config', 'G-SV6378N2ZW', { 'content_group': 'Station Pages' });
  } else {
    window.gtag('config', 'G-SV6378N2ZW');
  }
})();

(function () {
  var p = (window.location && window.location.pathname) || '';
  var normalized = p.replace(/\/index\.html$/i, '/');
  if (normalized !== '/delhi-metro/') return;
  window.addEventListener('load', function () {
let DATA = null, GRAPH = null;
const TIMINGS = [
  { title: 'Blue Line', dot: 'var(--red)', rows: [['First Train', '06:00 AM'], ['Last Train', '11:00 PM'], ['Frequency', '~4-6 min']] },
  { title: 'Yellow Line', dot: 'var(--green)', rows: [['First Train', '05:45 AM'], ['Last Train', '11:00 PM'], ['Frequency', '~4-8 min']] },
];
const JOURNEYS = [
  { group: 'Daily Commutes', color: '#cf1f2f', icon: '🚇', routes: [
    { from: 'rajiv_chowk_blue_line', to: 'millennium_city_centre_gurugram_yellow_line', fromName: 'Rajiv Chowk', toName: 'Huda City Centre' },
    { from: 'kashmere_gate_red_line', to: 'm_g_road_yellow_line', fromName: 'Kashmere Gate', toName: 'M G Road' }
  ]},
  { group: 'Interchange Trips', color: '#1f4fa3', icon: '🔄', routes: [
    { from: 'dwarka_sector_21_blue_line', to: 'new_delhi_yellow_line', fromName: 'Dwarka Sector 21', toName: 'New Delhi' },
    { from: 'botanical_garden_blue_line', to: 'hauz_khas_yellow_line', fromName: 'Botanical Garden', toName: 'Hauz Khas' }
  ]},
  { group: 'Popular Journeys', color: '#1f4fa3', icon: '📍', routes: [
    { fromName: 'Millennium City Centre', toName: 'Samaypur Badli', href: '/delhi-metro/routes/millennium-city-centre-to-samaypur-badli.html', meta: '50.4 km · ₹60' },
    { fromName: 'Dwarka Sector 21', toName: 'Noida Electronic City', href: '/delhi-metro/routes/dwarka-sector-21-to-noida-electronic-city.html', meta: '68.6 km · ₹60' },
    { fromName: 'Dwarka Sector 21', toName: 'Vaishali', href: '/delhi-metro/routes/dwarka-sector-21-to-vaishali.html', meta: '56.0 km · ₹60' },
    { fromName: 'Jahangirpuri', toName: 'Central Secretariat', href: '/delhi-metro/routes/jahangirpuri-to-central-secretariat.html', meta: '19.6 km · ₹40' },
    { fromName: 'Rajiv Chowk', toName: 'New Delhi', href: '/delhi-metro/routes/rajiv-chowk-to-new-delhi.html', meta: '1.4 km · ₹10' },
    { fromName: 'Rajiv Chowk', toName: 'Kashmere Gate', href: '/delhi-metro/routes/rajiv-chowk-to-kashmere-gate.html', meta: '5.6 km · ₹30' },
    { fromName: 'Central Secretariat', toName: 'Kashmere Gate', href: '/delhi-metro/routes/central-secretariat-to-kashmere-gate.html', meta: '8.4 km · ₹30' },
    { fromName: 'Chandni Chowk', toName: 'New Delhi', href: '/delhi-metro/routes/chandni-chowk-to-new-delhi.html', meta: '2.8 km · ₹20' },
    { fromName: 'Rajiv Chowk', toName: 'Millennium City Centre', href: '/delhi-metro/routes/rajiv-chowk-to-millennium-city-centre.html', meta: '29.4 km · ₹50' },
    { fromName: 'Dwarka Sector 21', toName: 'Rajiv Chowk', href: '/delhi-metro/routes/dwarka-sector-21-to-rajiv-chowk.html', meta: '39.2 km · ₹60' },
    { fromName: 'Noida Electronic City', toName: 'Rajiv Chowk', href: '/delhi-metro/routes/noida-electronic-city-to-rajiv-chowk.html', meta: '29.4 km · ₹50' },
    { fromName: 'Botanical Garden', toName: 'Rajiv Chowk', href: '/delhi-metro/routes/botanical-garden-to-rajiv-chowk.html', meta: '18.2 km · ₹40' },
    { fromName: 'Kashmere Gate', toName: 'Rajiv Chowk', href: '/delhi-metro/routes/kashmere-gate-to-rajiv-chowk.html', meta: '5.6 km · ₹30' },
    { fromName: 'New Delhi', toName: 'Millennium City Centre', href: '/delhi-metro/routes/new-delhi-to-millennium-city-centre.html', meta: '30.8 km · ₹50' },
    { fromName: 'Noida Sector 18', toName: 'Rajiv Chowk', href: '/delhi-metro/routes/noida-sector-18-to-rajiv-chowk.html', meta: '16.8 km · ₹40' },
  ]},
];

(async () => {
  try {
    DATA = await DataLoader.loadAll();
    GRAPH = GraphBuilder.build(DATA.connections);
    buildDropdowns();
    buildSystemCards();
    buildTimings();
    buildTopJourneys();
    initTabs();
    buildStations('all');
    bindUI();
  } catch (err) {
    console.error(err);
  }
})();

function uniqueStations(stations) {
  const seen = new Set();
  return stations.filter(s => {
    const k = `${s.station_name}||${s.system_id}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}

function setupAutocomplete(searchId, hiddenId, listId, stationList) {
  const searchEl = document.getElementById(searchId);
  const hiddenEl = document.getElementById(hiddenId);
  const listEl = document.getElementById(listId);
  let activeIdx = -1;

  function render(q) {
    const text = (q || '').toLowerCase().trim();
    const filtered = text ? stationList.filter(s => s.name.toLowerCase().includes(text) || s.line.toLowerCase().includes(text)) : stationList;
    if (!filtered.length) { listEl.hidden = true; return; }
    listEl.innerHTML = filtered.map(s => `<li data-id="${s.id}" data-name="${s.name}"><span class="ac-name">${s.name}</span><span class="ac-city">${s.line}</span></li>`).join('');
    listEl.hidden = false;
    activeIdx = -1;
  }

  function pick(li) {
    hiddenEl.value = li.dataset.id;
    searchEl.value = li.dataset.name;
    listEl.hidden = true;
  }

  searchEl.addEventListener('input', () => render(searchEl.value));
  searchEl.addEventListener('focus', () => render(searchEl.value));
  searchEl.addEventListener('keydown', e => {
    const items = listEl.querySelectorAll('li');
    if (!items.length || listEl.hidden) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      activeIdx = Math.min(activeIdx + 1, items.length - 1);
      items.forEach((el, i) => el.classList.toggle('ac-active', i === activeIdx));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      activeIdx = Math.max(activeIdx - 1, 0);
      items.forEach((el, i) => el.classList.toggle('ac-active', i === activeIdx));
    } else if (e.key === 'Enter' && activeIdx >= 0) {
      e.preventDefault();
      pick(items[activeIdx]);
    }
  });
  searchEl.addEventListener('blur', () => setTimeout(() => { listEl.hidden = true; }, 180));
  listEl.addEventListener('mousedown', e => {
    const li = e.target.closest('li[data-id]');
    if (li) pick(li);
  });
}

function buildDropdowns() {
  const stations = uniqueStations(DATA.stations).map(s => ({ id: s.station_id, name: s.station_name, line: DATA.lines.find(l => l.line_id === s.line_id)?.line_name || 'Line' }));
  setupAutocomplete('src-search', 'src', 'src-list', stations);
  setupAutocomplete('dst-search', 'dst', 'dst-list', stations);
}

function buildSystemCards() {
  const lineTheme = (lineName, index) => {
    const name = (lineName || '').toLowerCase();
    if (name.includes('blue')) return { color: '#1e5ad8', icon: '🔵' };
    if (name.includes('yellow')) return { color: '#c59b12', icon: '🟡' };
    if (name.includes('red')) return { color: '#cf1f2f', icon: '🔴' };
    if (name.includes('green')) return { color: '#1f8f4f', icon: '🟢' };
    if (name.includes('magenta')) return { color: '#b92f9f', icon: '🟣' };
    if (name.includes('violet')) return { color: '#7f3fbf', icon: '🟣' };
    if (name.includes('pink')) return { color: '#d65f8f', icon: '🩷' };
    if (name.includes('orange')) return { color: '#e07b24', icon: '🟠' };
    if (name.includes('grey') || name.includes('gray')) return { color: '#5f6b7a', icon: '⚪' };
    if (name.includes('airport')) return { color: '#0f5f66', icon: '✈️' };
    return { color: index % 2 === 0 ? '#cf1f2f' : '#1f4fa3', icon: '🚇' };
  };

  const networkCard = `<div class="sys-card" style="--sys-accent:#cf1f2f">
      <div class="sys-icon">📊</div>
      <div class="sys-name">Delhi Metro Network Scale</div>
      <div class="sys-op">Delhi Metro · DMRC</div>
      <div class="sys-stats">
        <div><div class="sv">392</div><div class="sl">km</div></div>
        <div><div class="sv">286</div><div class="sl">Stations</div></div>
        <div><div class="sv">April 2026</div><div class="sl">Last Updated</div></div>
      </div>
    </div>`;

  const lineCards = DATA.lines.map((line, i) => {
    const theme = lineTheme(line.line_name, i);
    const stations = DATA.stations.filter(s => s.line_id === line.line_id).length;
    const distance = DATA.connections.filter(c => c.line_id === line.line_id).reduce((sum, c) => sum + Number(c.distance_km || 0), 0).toFixed(1);
    const interchanges = DATA.interchanges.filter(x => x.from_line === line.line_id || x.to_line === line.line_id).length;
    return `<div class="sys-card" style="--sys-accent:${theme.color}">
      <div class="sys-icon">${theme.icon}</div>
      <div class="sys-name">${line.line_name}</div>
      <div class="sys-op">Delhi Metro · DMRC</div>
      <div class="sys-stats">
        <div><div class="sv">${distance}</div><div class="sl">km</div></div>
        <div><div class="sv">${stations}</div><div class="sl">Stations</div></div>
        <div><div class="sv">${interchanges}</div><div class="sl">Interchanges</div></div>
      </div>
    </div>`;
  }).join('');
  document.getElementById('sys-grid').innerHTML = networkCard + lineCards;
}

function buildTimings() {
  document.getElementById('timings-grid').innerHTML = TIMINGS.map(card => `
    <div class="timing-card">
      <div class="timing-card-title"><span style="width:10px;height:10px;border-radius:50%;background:${card.dot};display:inline-block"></span><span>${card.title}</span></div>
      ${card.rows.map(row => `<div class="timing-row"><span class="timing-label">${row[0]}</span><span class="timing-val">${row[1]}</span></div>`).join('')}
    </div>
  `).join('');
}

function buildTopJourneys() {
  const container = document.getElementById('top-journeys');
  container.innerHTML = JOURNEYS.map(group => `
    <div class="pr-group">
      <div class="pr-group-header" style="--gc:${group.color}"><span class="pr-group-icon">${group.icon}</span><span class="pr-group-label">${group.group}</span></div>
      <div class="pr-grid">
        ${group.routes.map(r => {
          const href = r.href ? (r.href.startsWith('/') ? r.href : `/${r.href.replace(/^\/+/, '')}`) : '#';
          const metaLeft = r.href ? (r.meta || 'View Route') : 'Auto-fill';
          const metaRight = r.href ? 'Full Guide' : 'Find route';
          const dataAttrs = r.from ? `data-from="${r.from}" data-to="${r.to}"` : '';
          return `<a href="${href}" class="pr-card" style="--gc:${group.color}" ${dataAttrs}>
            <div class="pr-card-route"><span class="pr-card-from">${r.fromName}</span><span class="pr-card-arrow">→</span><span class="pr-card-to">${r.toName}</span></div>
            <div class="pr-card-meta"><span>${metaLeft}</span><span>${metaRight}</span></div>
          </a>`;
        }).join('')}
      </div>
    </div>
  `).join('');

  container.querySelectorAll('a[data-from][data-to]').forEach(link => {
    link.addEventListener('click', e => {
      if (link.getAttribute('href') !== '#') return;
      e.preventDefault();
      setStation('src', link.dataset.from);
      setStation('dst', link.dataset.to);
      onFind();
    });
  });
}

function setStation(which, stationId) {
  const hidden = document.getElementById(which);
  const search = document.getElementById(`${which}-search`);
  hidden.value = stationId;
  const st = DATA.stations.find(s => s.station_id === stationId);
  search.value = st ? st.station_name : '';
}

function initTabs() {
  const tabs = document.getElementById('tabs');
  const lineTabs = DATA.lines.map(line => `<button class="tab" data-line="${line.line_id}">${line.line_name}</button>`).join('');
  tabs.innerHTML = `<button class="tab on" data-line="all">All</button>${lineTabs}`;
  tabs.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.querySelectorAll('.tab').forEach(t => t.classList.remove('on'));
      tab.classList.add('on');
      buildStations(tab.dataset.line);
    });
  });
}

function buildStations(lineId) {
  const stations = uniqueStations(DATA.stations).filter(s => lineId === 'all' || s.line_id === lineId);
  const rows = stations.map(s => {
    const line = DATA.lines.find(l => l.line_id === s.line_id);
    return `<tr>
      <td style="padding:10px 8px;border-bottom:1px solid var(--border)"><button type="button" style="all:unset;cursor:pointer;color:var(--text)" data-pick="${s.station_id}">${s.station_name}</button></td>
      <td style="padding:10px 8px;border-bottom:1px solid var(--border);color:var(--muted)">${line ? line.line_name : '-'}</td>
      <td style="padding:10px 8px;border-bottom:1px solid var(--border);color:var(--muted)">${s.city}</td>
    </tr>`;
  }).join('');

  document.getElementById('stations-list').innerHTML = `
    <div class="timing-card">
      <table style="width:100%;border-collapse:collapse;font-size:.86rem">
        <thead><tr><th style="text-align:left;padding:0 8px 10px">Station</th><th style="text-align:left;padding:0 8px 10px">Line</th><th style="text-align:left;padding:0 8px 10px">City</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;

  document.querySelectorAll('[data-pick]').forEach(btn => {
    btn.addEventListener('click', () => quickFill(btn.dataset.pick));
  });
}

function quickFill(id) {
  const src = document.getElementById('src');
  const dst = document.getElementById('dst');
  if (!src.value) setStation('src', id);
  else if (!dst.value) setStation('dst', id);
  else setStation('dst', id);
  document.getElementById('search-section').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function bindUI() {
  document.getElementById('swap-btn').addEventListener('click', () => {
    const src = document.getElementById('src');
    const dst = document.getElementById('dst');
    const srcSearch = document.getElementById('src-search');
    const dstSearch = document.getElementById('dst-search');
    const tmpId = src.value; const tmpName = srcSearch.value;
    src.value = dst.value; srcSearch.value = dstSearch.value;
    dst.value = tmpId; dstSearch.value = tmpName;
  });
  document.getElementById('find-btn').addEventListener('click', onFind);
  const upBtn = document.getElementById('up-btn');
  window.addEventListener('scroll', () => upBtn.classList.toggle('show', scrollY > 380), { passive: true });
  upBtn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
}

function onFind() {
  const src = document.getElementById('src').value;
  const dst = document.getElementById('dst').value;
  if (!src || !dst || src === dst) return;

  const path = RouteFinder.findRoute(GRAPH, src, dst);
  if (!path || !path.length) return;
  const dist = RouteFinder.calcDistance(path, GRAPH);
  const fare = RouteFinder.calcFare(path, { cityKey: DATA?.cityKey, distance: dist });
  const nX = path.filter(p => p.line_id === 'interchange').length;
  const time = RouteFinder.calcTime(dist, nX);
  RouteUI.renderRoute('route-result', path, DATA.stations, DATA.interchanges, dist, fare, time, DATA.lines, DATA.cityKey);
  document.getElementById('route-result').style.display = 'block';
  setTimeout(() => document.getElementById('route-result').scrollIntoView({ behavior: 'smooth', block: 'start' }), 80);
}
  }, { once: true });
})();

(function () {
  var p = (window.location && window.location.pathname) || '';
  var normalized = p.replace(/\/index\.html$/i, '/');
  if (normalized !== '/bengaluru-metro/') return;
  window.addEventListener('load', function () {
let DATA = null, GRAPH = null;
const TIMINGS = [
  { title: 'Purple Line', dot: 'var(--red)', rows: [['First Train', '05:00 AM'], ['Last Train', '11:00 PM'], ['Frequency', '~5-8 min']] },
  { title: 'Green Line', dot: 'var(--green)', rows: [['First Train', '05:00 AM'], ['Last Train', '11:00 PM'], ['Frequency', '~6-10 min']] },
];
const JOURNEYS = [
  { group: 'Daily Commutes', color: '#6c2e9d', icon: '🚇', routes: [
    { from: 'nadaprabhu_kempegowda_station_majestic_purple_line', to: 'whitefield_purple_line', fromName: 'Majestic', toName: 'Whitefield' },
    { from: 'indiranagar_purple_line', to: 'jayanagar_green_line', fromName: 'Indiranagar', toName: 'Jayanagar' }
  ]},
  { group: 'Interchange Trips', color: '#1b8f3b', icon: '🔄', routes: [
    { from: 'kengeri_purple_line', to: 'nagawara_green_line', fromName: 'Kengeri', toName: 'Nagawara' },
    { from: 'silk_institute_green_line', to: 'indiranagar_purple_line', fromName: 'Silk Institute', toName: 'Indiranagar' }
  ]},
  { group: 'Popular Journeys', color: '#6c2e9d', icon: '📍', routes: [
    { fromName: 'Challaghatta', toName: 'Whitefield', href: '/bengaluru-metro/routes/challaghatta-to-whitefield.html', meta: '37.2 km · ₹50' },
    { fromName: 'Nagasandra', toName: 'Silk Institute', href: '/bengaluru-metro/routes/nagasandra-to-silk-institute.html', meta: '42.0 km · ₹50' },
    { fromName: 'R.V. Road', toName: 'Bommasandra', href: '/bengaluru-metro/routes/rv-road-to-bommasandra.html', meta: '6.0 km · ₹20' },
    { fromName: 'Majestic', toName: 'Whitefield', href: '/bengaluru-metro/routes/majestic-to-whitefield.html', meta: '21.6 km · ₹35' },
    { fromName: 'Majestic', toName: 'Silk Institute', href: '/bengaluru-metro/routes/majestic-to-silk-institute.html', meta: '19.2 km · ₹35' },
    { fromName: 'Majestic', toName: 'R.V. Road', href: '/bengaluru-metro/routes/majestic-to-rv-road.html', meta: '22.8 km · ₹35' },
    { fromName: 'Whitefield', toName: 'Indiranagar', href: '/bengaluru-metro/routes/whitefield-to-indiranagar.html', meta: '16.8 km · ₹30' },
    { fromName: 'Whitefield', toName: 'Majestic', href: '/bengaluru-metro/routes/whitefield-to-majestic.html', meta: '21.6 km · ₹35' },
    { fromName: 'Silk Institute', toName: 'Majestic', href: '/bengaluru-metro/routes/silk-institute-to-majestic.html', meta: '19.2 km · ₹35' },
    { fromName: 'Silk Institute', toName: 'Nagasandra', href: '/bengaluru-metro/routes/silk-institute-to-nagasandra.html', meta: '42.0 km · ₹50' },
    { fromName: 'Bommasandra', toName: 'R.V. Road', href: '/bengaluru-metro/routes/bommasandra-to-rv-road.html', meta: '6.0 km · ₹20' },
    { fromName: 'Bommasandra', toName: 'Majestic', href: '/bengaluru-metro/routes/bommasandra-to-majestic.html', meta: '25.2 km · ₹40' },
    { fromName: 'Yeshwanthpur', toName: 'Majestic', href: '/bengaluru-metro/routes/yeshwanthpur-to-majestic.html', meta: '8.4 km · ₹25' },
    { fromName: 'Majestic', toName: 'M.G. Road', href: '/bengaluru-metro/routes/majestic-to-mg-road.html', meta: '2.4 km · ₹10' },
    { fromName: 'Sandal Soap Factory', toName: 'Majestic', href: '/bengaluru-metro/routes/sandal-soap-factory-to-majestic.html', meta: '4.8 km · ₹20' },
  ]},
];

(async () => {
  try {
    DATA = await DataLoader.loadAll();
    GRAPH = GraphBuilder.build(DATA.connections);
    buildDropdowns();
    buildSystemCards();
    buildTimings();
    buildTopJourneys();
    initTabs();
    buildStations('all');
    bindUI();
  } catch (err) {
    console.error(err);
  }
})();

function uniqueStations(stations) {
  const seen = new Set();
  return stations.filter(s => {
    const k = `${s.station_name}||${s.system_id}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}

function setupAutocomplete(searchId, hiddenId, listId, stationList) {
  const searchEl = document.getElementById(searchId);
  const hiddenEl = document.getElementById(hiddenId);
  const listEl = document.getElementById(listId);
  let activeIdx = -1;

  function render(q) {
    const text = (q || '').toLowerCase().trim();
    const filtered = text ? stationList.filter(s => s.name.toLowerCase().includes(text) || s.line.toLowerCase().includes(text)) : stationList;
    if (!filtered.length) { listEl.hidden = true; return; }
    listEl.innerHTML = filtered.map(s => `<li data-id="${s.id}" data-name="${s.name}"><span class="ac-name">${s.name}</span><span class="ac-city">${s.line}</span></li>`).join('');
    listEl.hidden = false;
    activeIdx = -1;
  }

  function pick(li) {
    hiddenEl.value = li.dataset.id;
    searchEl.value = li.dataset.name;
    listEl.hidden = true;
  }

  searchEl.addEventListener('input', () => render(searchEl.value));
  searchEl.addEventListener('focus', () => render(searchEl.value));
  searchEl.addEventListener('keydown', e => {
    const items = listEl.querySelectorAll('li');
    if (!items.length || listEl.hidden) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      activeIdx = Math.min(activeIdx + 1, items.length - 1);
      items.forEach((el, i) => el.classList.toggle('ac-active', i === activeIdx));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      activeIdx = Math.max(activeIdx - 1, 0);
      items.forEach((el, i) => el.classList.toggle('ac-active', i === activeIdx));
    } else if (e.key === 'Enter' && activeIdx >= 0) {
      e.preventDefault();
      pick(items[activeIdx]);
    }
  });
  searchEl.addEventListener('blur', () => setTimeout(() => { listEl.hidden = true; }, 180));
  listEl.addEventListener('mousedown', e => {
    const li = e.target.closest('li[data-id]');
    if (li) pick(li);
  });
}

function buildDropdowns() {
  const stations = uniqueStations(DATA.stations).map(s => ({ id: s.station_id, name: s.station_name, line: DATA.lines.find(l => l.line_id === s.line_id)?.line_name || 'Line' }));
  setupAutocomplete('src-search', 'src', 'src-list', stations);
  setupAutocomplete('dst-search', 'dst', 'dst-list', stations);
}

function buildSystemCards() {
  const lineTheme = (lineName, index) => {
    const name = (lineName || '').toLowerCase();
    if (name.includes('purple')) return { color: '#6c2e9d', icon: '🟣' };
    if (name.includes('green')) return { color: '#1b8f3b', icon: '🟢' };
    if (name.includes('yellow')) return { color: '#c59b12', icon: '🟡' };
    if (name.includes('pink')) return { color: '#d65f8f', icon: '🩷' };
    if (name.includes('blue')) return { color: '#1e5ad8', icon: '🔵' };
    return { color: index % 2 === 0 ? '#6c2e9d' : '#1b8f3b', icon: '🚇' };
  };

  const networkCard = `<div class="sys-card" style="--sys-accent:#6c2e9d">
      <div class="sys-icon">📊</div>
      <div class="sys-name">Bengaluru Metro Network Scale</div>
      <div class="sys-op">Namma Metro · BMRCL</div>
      <div class="sys-stats">
        <div><div class="sv">73</div><div class="sl">km</div></div>
        <div><div class="sv">66</div><div class="sl">Stations</div></div>
        <div><div class="sv">April 2026</div><div class="sl">Last Updated</div></div>
      </div>
    </div>`;

  const lineCards = DATA.lines.map((line, i) => {
    const theme = lineTheme(line.line_name, i);
    const stations = DATA.stations.filter(s => s.line_id === line.line_id).length;
    const distance = DATA.connections.filter(c => c.line_id === line.line_id).reduce((sum, c) => sum + Number(c.distance_km || 0), 0).toFixed(1);
    const interchanges = DATA.interchanges.filter(x => x.from_line === line.line_id || x.to_line === line.line_id).length;
    return `<div class="sys-card" style="--sys-accent:${theme.color}">
      <div class="sys-icon">${theme.icon}</div>
      <div class="sys-name">${line.line_name}</div>
      <div class="sys-op">Namma Metro · BMRCL</div>
      <div class="sys-stats">
        <div><div class="sv">${distance}</div><div class="sl">km</div></div>
        <div><div class="sv">${stations}</div><div class="sl">Stations</div></div>
        <div><div class="sv">${interchanges}</div><div class="sl">Interchanges</div></div>
      </div>
    </div>`;
  }).join('');
  document.getElementById('sys-grid').innerHTML = networkCard + lineCards;
}

function buildTimings() {
  document.getElementById('timings-grid').innerHTML = TIMINGS.map(card => `
    <div class="timing-card">
      <div class="timing-card-title"><span style="width:10px;height:10px;border-radius:50%;background:${card.dot};display:inline-block"></span><span>${card.title}</span></div>
      ${card.rows.map(row => `<div class="timing-row"><span class="timing-label">${row[0]}</span><span class="timing-val">${row[1]}</span></div>`).join('')}
    </div>
  `).join('');
}

function buildTopJourneys() {
  const container = document.getElementById('top-journeys');
  container.innerHTML = JOURNEYS.map(group => `
    <div class="pr-group">
      <div class="pr-group-header" style="--gc:${group.color}"><span class="pr-group-icon">${group.icon}</span><span class="pr-group-label">${group.group}</span></div>
      <div class="pr-grid">
        ${group.routes.map(r => {
          const href = r.href ? (r.href.startsWith('/') ? r.href : `/${r.href.replace(/^\/+/, '')}`) : '#';
          const metaLeft = r.href ? (r.meta || 'View Route') : 'Auto-fill';
          const metaRight = r.href ? 'Full Guide' : 'Find route';
          const dataAttrs = r.from ? `data-from="${r.from}" data-to="${r.to}"` : '';
          return `<a href="${href}" class="pr-card" style="--gc:${group.color}" ${dataAttrs}>
            <div class="pr-card-route"><span class="pr-card-from">${r.fromName}</span><span class="pr-card-arrow">→</span><span class="pr-card-to">${r.toName}</span></div>
            <div class="pr-card-meta"><span>${metaLeft}</span><span>${metaRight}</span></div>
          </a>`;
        }).join('')}
      </div>
    </div>
  `).join('');

  container.querySelectorAll('a[data-from][data-to]').forEach(link => {
    link.addEventListener('click', e => {
      if (link.getAttribute('href') !== '#') return;
      e.preventDefault();
      setStation('src', link.dataset.from);
      setStation('dst', link.dataset.to);
      onFind();
    });
  });
}

function setStation(which, stationId) {
  const hidden = document.getElementById(which);
  const search = document.getElementById(`${which}-search`);
  hidden.value = stationId;
  const st = DATA.stations.find(s => s.station_id === stationId);
  search.value = st ? st.station_name : '';
}

function initTabs() {
  const tabs = document.getElementById('tabs');
  const lineTabs = DATA.lines.map(line => `<button class="tab" data-line="${line.line_id}">${line.line_name}</button>`).join('');
  tabs.innerHTML = `<button class="tab on" data-line="all">All</button>${lineTabs}`;
  tabs.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.querySelectorAll('.tab').forEach(t => t.classList.remove('on'));
      tab.classList.add('on');
      buildStations(tab.dataset.line);
    });
  });
}

function buildStations(lineId) {
  const stations = uniqueStations(DATA.stations).filter(s => lineId === 'all' || s.line_id === lineId);
  const rows = stations.map(s => {
    const line = DATA.lines.find(l => l.line_id === s.line_id);
    return `<tr>
      <td style="padding:10px 8px;border-bottom:1px solid var(--border)"><button type="button" style="all:unset;cursor:pointer;color:var(--text)" data-pick="${s.station_id}">${s.station_name}</button></td>
      <td style="padding:10px 8px;border-bottom:1px solid var(--border);color:var(--muted)">${line ? line.line_name : '-'}</td>
      <td style="padding:10px 8px;border-bottom:1px solid var(--border);color:var(--muted)">${s.city}</td>
    </tr>`;
  }).join('');

  document.getElementById('stations-list').innerHTML = `
    <div class="timing-card">
      <table style="width:100%;border-collapse:collapse;font-size:.86rem">
        <thead><tr><th style="text-align:left;padding:0 8px 10px">Station</th><th style="text-align:left;padding:0 8px 10px">Line</th><th style="text-align:left;padding:0 8px 10px">City</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;

  document.querySelectorAll('[data-pick]').forEach(btn => {
    btn.addEventListener('click', () => quickFill(btn.dataset.pick));
  });
}

function quickFill(id) {
  const src = document.getElementById('src');
  const dst = document.getElementById('dst');
  if (!src.value) setStation('src', id);
  else if (!dst.value) setStation('dst', id);
  else setStation('dst', id);
  document.getElementById('search-section').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function bindUI() {
  document.getElementById('swap-btn').addEventListener('click', () => {
    const src = document.getElementById('src');
    const dst = document.getElementById('dst');
    const srcSearch = document.getElementById('src-search');
    const dstSearch = document.getElementById('dst-search');
    const tmpId = src.value; const tmpName = srcSearch.value;
    src.value = dst.value; srcSearch.value = dstSearch.value;
    dst.value = tmpId; dstSearch.value = tmpName;
  });
  document.getElementById('find-btn').addEventListener('click', onFind);
  const upBtn = document.getElementById('up-btn');
  window.addEventListener('scroll', () => upBtn.classList.toggle('show', scrollY > 380), { passive: true });
  upBtn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
}

function onFind() {
  const src = document.getElementById('src').value;
  const dst = document.getElementById('dst').value;
  if (!src || !dst || src === dst) return;

  const path = RouteFinder.findRoute(GRAPH, src, dst);
  if (!path || !path.length) return;
  const dist = RouteFinder.calcDistance(path, GRAPH);
  const fare = RouteFinder.calcFare(path, { cityKey: DATA?.cityKey, distance: dist });
  const nX = path.filter(p => p.line_id === 'interchange').length;
  const time = RouteFinder.calcTime(dist, nX);
  RouteUI.renderRoute('route-result', path, DATA.stations, DATA.interchanges, dist, fare, time, DATA.lines, DATA.cityKey);
  document.getElementById('route-result').style.display = 'block';
  setTimeout(() => document.getElementById('route-result').scrollIntoView({ behavior: 'smooth', block: 'start' }), 80);
}
  }, { once: true });
})();

(function () {
  var p = (window.location && window.location.pathname) || '';
  var normalized = p.replace(/\/index\.html$/i, '/');
  if (normalized !== '/namo-bharat/') return;
  window.addEventListener('load', function () {
/* ═══════════════════════════════════════════════════════════
   App — index.html  v3
   Dynamic data loading, BFS routing, full Hindi support
═══════════════════════════════════════════════════════════ */

let DATA = null, GRAPH = null;
let currentLang = 'en';

/* ── Boot ───────────────────────────────────────────────── */
(async () => {
  initTicker(); // show ticker immediately with static items
  try {
    DATA  = await DataLoader.loadAll();
    GRAPH = GraphBuilder.build(DATA.connections);
    buildDropdowns();
    buildSysCards();
    buildStations('all');
    buildBlog();
    initTabListeners();
    restoreFromURL();
    PopularRoutes.render('popular-routes');
  } catch (err) {
    console.error(err);
    document.getElementById('route-result').innerHTML =
      `<div class="rc-error"><span>⚠️</span><p>${err.message}</p></div>`;
    document.getElementById('route-result').style.display = 'block';
  }
})();

/* ── Ticker announcements ───────────────────────────────── */
function initTicker() {
  const items = [
    { en: '🚄 Namo Bharat fully operational from Sarai Kale Khan to Modipuram — 22 Feb 2026', hi: '🚄 नमो भारत अब सराय काले खां से मोदीपुरम तक पूरी तरह चालू — 22 फ़रवरी 2026' },
    { en: '🟢 Meerut Metro inaugurated alongside Namo Bharat on 22 Feb 2026', hi: '🟢 मेरठ मेट्रो का उद्घाटन 22 फ़रवरी 2026 को नमो भारत के साथ हुआ' },
    { en: '⏱ Trains run every 10 minutes — Standard & Premium coaches available', hi: '⏱ ट्रेनें हर 10 मिनट में — मानक और प्रीमियम कोच उपलब्ध' },
    { en: '💳 Smart Card / NCMC accepted at all RRTS & Meerut Metro stations', hi: '💳 सभी RRTS और मेरठ मेट्रो स्टेशनों पर स्मार्ट कार्ड / NCMC स्वीकार' },
    { en: '🔄 Interchange available at Meerut South, Shatabdi Nagar, Begumpul, Modipuram', hi: '🔄 मेरठ साउथ, शताब्दी नगर, बेगमपुल और मोदीपुरम पर इंटरचेंज उपलब्ध' },
    { en: '✅ Children under 90 cm travel free on Namo Bharat RRTS', hi: '✅ 90 सेमी से कम ऊंचाई वाले बच्चे नमो भारत पर मुफ़्त यात्रा करें' },
  ];
  const ti = document.getElementById('ticker-inner');
  // Duplicate for seamless loop
  const html = [...items, ...items].map(item => `
    <span class="ticker-item">
      <span class="ticker-dot"></span>
      <span data-en>${item.en}</span>
      <span data-hi>${item.hi}</span>
    </span>`).join('');
  ti.innerHTML = html;
}

/* ── Autocomplete setup ─────────────────────────────────── */
function setupAutocomplete(searchId, hiddenId, listId, stationList) {
  const searchEl = document.getElementById(searchId);
  const hiddenEl = document.getElementById(hiddenId);
  const listEl   = document.getElementById(listId);
  let activeIdx  = -1;

  function renderList(q) {
    const lower = (q || '').toLowerCase().trim();
    const filtered = lower
      ? stationList.filter(s =>
          s.name.toLowerCase().includes(lower) ||
          s.city.toLowerCase().includes(lower) ||
          s.system.toLowerCase().includes(lower)
        )
      : stationList;
    activeIdx = -1;
    if (!filtered.length) { listEl.hidden = true; return; }
    listEl.innerHTML = filtered.map(s => {
      const isR = s.system === 'rrts';
      return `<li data-id="${s.id}" data-name="${s.name}">` +
        `<span class="ac-sys-badge ${isR ? 'ac-sys-rrts' : 'ac-sys-metro'}">${isR ? 'RRTS' : 'Metro'}</span>` +
        `<span class="ac-name">${s.name}</span>` +
        `<span class="ac-city">${s.city}</span></li>`;
    }).join('');
    listEl.hidden = false;
  }

  function selectItem(li) {
    hiddenEl.value = li.dataset.id;
    searchEl.value = li.dataset.name;
    listEl.hidden  = true;
    activeIdx = -1;
  }

  searchEl.addEventListener('input', () => renderList(searchEl.value));
  searchEl.addEventListener('focus', () => renderList(searchEl.value));
  searchEl.addEventListener('keydown', e => {
    const items = listEl.querySelectorAll('li');
    if (!items.length || listEl.hidden) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      activeIdx = Math.min(activeIdx + 1, items.length - 1);
      items.forEach((el, i) => el.classList.toggle('ac-active', i === activeIdx));
      items[activeIdx]?.scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      activeIdx = Math.max(activeIdx - 1, 0);
      items.forEach((el, i) => el.classList.toggle('ac-active', i === activeIdx));
      items[activeIdx]?.scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'Enter' && activeIdx >= 0) {
      e.preventDefault();
      selectItem(items[activeIdx]);
    } else if (e.key === 'Escape') {
      listEl.hidden = true;
    }
  });
  searchEl.addEventListener('blur', () => {
    setTimeout(() => { listEl.hidden = true; }, 180);
  });
  listEl.addEventListener('mousedown', e => {
    const li = e.target.closest('li[data-id]');
    if (li) selectItem(li);
  });
}

/* ── Set station programmatically (updates both hidden + display) ────────── */
function setStation(which, stationId) {
  const hidden = document.getElementById(which);
  const search = document.getElementById(which + '-search');
  if (hidden) hidden.value = stationId || '';
  if (search && DATA) {
    const st = DATA.stations.find(s => s.station_id === stationId);
    search.value = st ? st.station_name : '';
  } else if (search) {
    search.value = '';
  }
}

/* ── Dropdowns ──────────────────────────────────────────── */
function buildDropdowns() {
  const uniq = uniqueStations(DATA.stations);
  const stationList = uniq.map(s => ({
    id: s.station_id, name: s.station_name, city: s.city, system: s.system_id
  }));
  setupAutocomplete('src-search', 'src', 'src-list', stationList);
  setupAutocomplete('dst-search', 'dst', 'dst-list', stationList);
}

/* ── System Cards ───────────────────────────────────────── */
function buildSysCards() {
  const rrtsCount  = uniqueStations(DATA.stations.filter(s => s.system_id === 'rrts')).length;
  const metroCount = uniqueStations(DATA.stations.filter(s => s.system_id === 'meerut_metro')).length;
  document.getElementById('sys-grid').innerHTML = `
    <div class="sys-card rrts">
      <div class="sys-icon">🚅
      <div class="sys-name" data-en>Namo Bharat RRTS
      <div class="sys-name" data-hi>नमो भारत RRTS
      <div class="sys-op">Delhi–Meerut · NCRTC
      <div class="sys-stats">
        <div><div class="sv">82.15</div><div class="sl" data-en>km</div><div class="sl" data-hi>किमी</div>
        <div><div class="sv">${rrtsCount}</div><div class="sl" data-en>Stations</div><div class="sl" data-hi>स्टेशन</div>
        <div><div class="sv">180</div><div class="sl" data-en>km/h max</div><div class="sl" data-hi>किमी/घंटा</div>
      
    
    <div class="sys-card metro">
      <div class="sys-icon">🚇
      <div class="sys-name" data-en>Meerut Metro
      <div class="sys-name" data-hi>मेरठ मेट्रो
      <div class="sys-op">Meerut City · NCRTC
      <div class="sys-stats">
        <div><div class="sv">22.8</div><div class="sl" data-en>km</div><div class="sl" data-hi>किमी</div>
        <div><div class="sv">${metroCount}</div><div class="sl" data-en>Stations</div><div class="sl" data-hi>स्टेशन</div>
        <div><div class="sv">4</div><div class="sl" data-en>Interchanges</div><div class="sl" data-hi>इंटरचेंज</div>
      
    </div>`;
}

/* ── Stations List ──────────────────────────────────────── */
function buildStations(filter) {
  const list = document.getElementById('stations-list');
  const uniq = uniqueStations(DATA.stations).filter(s => filter === 'all' || s.system_id === filter);
  const isR  = s => s.system_id === 'rrts';
  const col  = s => isR(s) ? '#D94F3A' : '#2E9E52';
  const bg   = s => isR(s) ? 'rgba(217,79,58,.12)' : 'rgba(46,158,82,.1)';
  const bd   = s => isR(s) ? 'rgba(217,79,58,.35)' : 'rgba(46,158,82,.32)';
  const badge= s => isR(s) ? 'RRTS' : 'Metro';

  list.innerHTML = uniq.map(s => `
    <div class="st-row" onclick="quickFill('${s.station_id}')">
<div class="st-dot" style="background:${col(s)}20;border-color:${col(s)}"></div>
<span class="st-name">${s.station_name}</span>
      <span class="st-city">${s.city}</span>
      <span class="st-badge" style="background:${bg(s)};color:${col(s)};border-color:${bd(s)}">${badge(s)}</span>
    </div>`).join('');
}

/* ── Blog / Updates ─────────────────────────────────────── */
function buildBlog() {
  const posts = [
    {
      date: '22 Feb 2026',
      icon: '🎉',
      titleEn: 'Namo Bharat &amp; Meerut Metro fully inaugurated',
      titleHi: 'नमो भारत और मेरठ मेट्रो का पूर्ण उद्घाटन',
      descEn:  'PM Modi inaugurated the complete 82.15 km Delhi–Meerut RRTS corridor and Meerut Metro on 22 February 2026, marking a historic milestone for Indian transit.',
      descHi:  'PM मोदी ने 22 फ़रवरी 2026 को पूर्ण 82.15 किमी दिल्ली–मेरठ RRTS कॉरिडोर और मेरठ मेट्रो का उद्घाटन किया।',
    },
    {
      date: '5 Jan 2025',
      icon: '🚄',
      titleEn: 'Delhi section opens: Sarai Kale Khan to New Ashok Nagar',
      titleHi: 'दिल्ली खंड खुला: सराय काले खां से न्यू अशोक नगर',
      descEn:  'The final Delhi section, including the underground Anand Vihar station and Yamuna crossing, became operational on 5 January 2025.',
      descHi:  'अंतिम दिल्ली खंड, जिसमें भूमिगत आनंद विहार स्टेशन और यमुना क्रॉसिंग शामिल है, 5 जनवरी 2025 को चालू हुआ।',
    },
    {
      date: '18 Aug 2024',
      icon: '📍',
      titleEn: 'Meerut South station becomes operational',
      titleHi: 'मेरठ साउथ स्टेशन चालू हुआ',
      descEn:  'The section extended to Meerut South, bringing the corridor to 42 km and enabling interchange with the upcoming Meerut Metro.',
      descHi:  'सेक्शन मेरठ साउथ तक विस्तारित हुआ, कॉरिडोर 42 किमी हुई और आगामी मेरठ मेट्रो से इंटरचेंज की शुरुआत हुई।',
    },
  ];

  document.getElementById('blog-list').innerHTML = posts.map(p => `
    <div class="sys-card" style="margin-bottom:12px;border-left:3px solid var(--red)">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
        <span style="font-size:1.4rem">${p.icon}</span>
        <div>
          <div class="sys-name" data-en>${p.titleEn}
          <div class="sys-name" data-hi>${p.titleHi}
          <div class="sys-op">${p.date}
        
      
      <p style="font-size:.82rem;color:var(--text2);line-height:1.65" data-en>${p.descEn}</p>
      <p style="font-size:.82rem;color:var(--text2);line-height:1.65" data-hi>${p.descHi}</p>
    </div>`).join('');
}

/* ── Tab listeners ──────────────────────────────────────── */
function initTabListeners() {
  document.querySelectorAll('#tabs .tab').forEach(btn => {
    btn.addEventListener('click', () => {
      // Activate all tabs sharing the same data-sys
      const sys = btn.dataset.sys;
      document.querySelectorAll('#tabs .tab').forEach(b => {
        b.classList.toggle('on', b.dataset.sys === sys);
      });
      buildStations(sys);
    });
  });
}

/* ── Quick fill from station row ────────────────────────── */
function quickFill(id) {
  if (!document.getElementById('src').value) setStation('src', id);
  else setStation('dst', id);
  document.getElementById('search-section').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

/* ── Find route — navigate to SEO-friendly /route/ URL ────── */
function stationToSlug(station_id) {
  return station_id
    .replace(/_rrts$/, '')
    .replace(/_meerut_metro$/, '')
    .replace(/_/g, '-');
}

function onFind() {
  const src = document.getElementById('src').value;
  const dst = document.getElementById('dst').value;
  const btn = document.getElementById('find-btn');
  if (!src || !dst) {
    alert(currentLang === 'hi' ? 'कृपया दोनों स्टेशन चुनें।' : 'Please select both a source and destination station.');
    return;
  }
  if (src === dst) {
    alert(currentLang === 'hi' ? 'स्रोत और गंतव्य एक नहीं हो सकते।' : 'Source and destination cannot be the same.');
    return;
  }

  btn.classList.add('busy');

  const slug = stationToSlug(src) + '-to-' + stationToSlug(dst);

  setTimeout(() => {
    btn.classList.remove('busy');

    // Detect base path for subdirectory GitHub Pages hosting
    var basePath = window.location.pathname.replace(/\/[^\/]*$/, '').replace(/\/route\/.*$/, '');

    // Go directly to route.html (NO 404 flash), route.html will clean URL to /route/<slug>
    window.location.href = window.location.origin + basePath + '/route.html?r=' + encodeURIComponent(slug);
  }, 260);
}

function go(src, dst) {
  const path = RouteFinder.findRoute(GRAPH, src, dst);
  if (!path?.length) {
    RouteUI.renderError('route-result', currentLang === 'hi'
      ? 'इन स्टेशनों के बीच कोई रूट नहीं मिला।'
      : 'No route found between these stations. Please try a different combination.');
    scrollToResult(); return;
  }

  const dist = RouteFinder.calcDistance(path, GRAPH);
  const fare = RouteFinder.calcFare(path, { cityKey: DATA?.cityKey, distance: dist });
  console.log('DEBUG src:', src);
console.log('DEBUG dst:', dst);
console.log('DEBUG path last station_id:', path[path.length-1]?.station_id);
console.log('DEBUG direct lookup:', (function(){
  const a = src, b = dst;
  const key = [a,b].sort().join('__');
  return { key };
})());
  const nX   = path.filter(p => p.line_id === 'interchange').length;
  const time = RouteFinder.calcTime(dist, nX);

  RouteUI.renderRoute('route-result', path, DATA.stations, DATA.interchanges, dist, fare, time, DATA.lines, DATA.cityKey);

  const srcSt = DATA.stations.find(s => s.station_id === src);
  const dstSt = DATA.stations.find(s => s.station_id === dst);
  if (srcSt && dstSt) {
    const names = path.map(p => DATA.stations.find(s => s.station_id === p.station_id)?.station_name || p.station_id);
    const seoHTML = SEOGenerator.seoBlock(srcSt.station_name, dstSt.station_name, names, dist, fare, time);
    const card = document.querySelector('.rc');
    if (card) { const d = document.createElement('div'); d.innerHTML = seoHTML; card.appendChild(d.firstElementChild); }
    SEOGenerator.apply(srcSt.station_name, dstSt.station_name, dist, fare, time);
    // Navigation now handled by onFind() → /route/ URL
  }
  scrollToResult();
}

function scrollToResult() {
  setTimeout(() => document.getElementById('route-result').scrollIntoView({ behavior: 'smooth', block: 'start' }), 80);
}

/* ── URL restore ────────────────────────────────────────── */
function restoreFromURL() {
  const p = new URLSearchParams(window.location.search);
  const from = p.get('from'), to = p.get('to');
  if (from && to) {
    setStation('src', from);
    setStation('dst', to);
    setTimeout(() => go(from, to), 200);
  }
}

/* ── Swap ───────────────────────────────────────────────── */
document.getElementById('swap-btn').addEventListener('click', () => {
  const srcH = document.getElementById('src');
  const dstH = document.getElementById('dst');
  const srcS = document.getElementById('src-search');
  const dstS = document.getElementById('dst-search');
  const tmpId   = srcH.value, tmpName = srcS.value;
  srcH.value = dstH.value; srcS.value = dstS.value;
  dstH.value = tmpId;      dstS.value = tmpName;
});

/* ── Nav menu ───────────────────────────────────────────── */
document.getElementById('menu-btn').addEventListener('click', () => {
  document.getElementById('nav-menu').classList.toggle('open');
});
document.addEventListener('click', e => {
  if (!document.getElementById('nav').contains(e.target)) {
    document.getElementById('nav-menu').classList.remove('open');
  }
});

/* ── Smooth scroll helper ───────────────────────────────── */
function scrollTo(sel) {
  document.querySelector(sel)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  document.getElementById('nav-menu').classList.remove('open');
}

/* ── Language toggle ────────────────────────────────────── */
document.getElementById('lang-btn').addEventListener('click', () => {
  currentLang = currentLang === 'en' ? 'hi' : 'en';
  document.documentElement.classList.toggle('lang-hi', currentLang === 'hi');
  // Add Hindi font if needed
  if (currentLang === 'hi' && !document.getElementById('hindi-font')) {
    const l = document.createElement('link');
    l.id = 'hindi-font';
    l.rel = 'stylesheet';
    l.href = 'https://fonts.googleapis.com/css2?family=Noto+Sans+Devanagari:wght@400;600;700&display=swap';
    document.head.appendChild(l);
  }
});

/* ── Scroll-to-top ──────────────────────────────────────── */
const upBtn = document.getElementById('up-btn');
window.addEventListener('scroll', () => upBtn.classList.toggle('show', scrollY > 380), { passive: true });
upBtn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));

/* ── Helpers ────────────────────────────────────────────── */
function uniqueStations(stations) {
  const seen = new Set();
  return stations.filter(s => {
    const k = `${s.station_name}||${s.system_id}`;
    if (seen.has(k)) return false; seen.add(k); return true;
  }).sort((a, b) => {
    if (a.system_id !== b.system_id) return a.system_id === 'rrts' ? -1 : 1;
    return Number(a.order) - Number(b.order);
  });
}
  }, { once: true });
})();
