(function () {
  'use strict';

  const CITY_PATH_MAP = [
    { key: 'delhi', regex: /\/delhi-metro(?:\/|$)/i },
    { key: 'bengaluru', regex: /\/bengaluru-metro(?:\/|$)/i },
    { key: 'rrts', regex: /\/namo-bharat(?:\/|$)/i }
  ];

  function detectCityKey() {
    const path = window.location.pathname || '';
    const matched = CITY_PATH_MAP.find((c) => c.regex.test(path));
    return matched ? matched.key : 'rrts';
  }

  function normalizeName(value) {
    return String(value || '')
      .toLowerCase()
      .replace(/&/g, 'and')
      .replace(/[^a-z0-9]+/g, ' ')
      .trim();
  }

  const AUTOCOMPLETE_BLUR_DELAY = 180;

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function stationNameToSlug(stationName) {
    return String(stationName || '')
      .toLowerCase()
      .trim()
      .replace(/\s+/g, '-')
      .replace(/[^a-z0-9-]/g, '')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '');
  }

  function stationToSlug(station) {
    const isStationObject = station && typeof station === 'object';
    const nameSlug = stationNameToSlug(isStationObject ? station.station_name : '');
    if (nameSlug) return nameSlug;
    const stationId = isStationObject ? station.station_id : station;
    return String(stationId || '')
      .replace(/_rrts$/, '')
      .replace(/_meerut_metro$/, '')
      .replace(/_/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '')
      .toLowerCase();
  }

  function normalizePath(path) {
    return ('/' + String(path || '').replace(/^\/+/, '')).replace(/\/{2,}/g, '/');
  }

  function getCityRouteDirectory(cityKey) {
    if (cityKey === 'delhi') return '/delhi-metro/routes';
    if (cityKey === 'bengaluru') return '/bengaluru-metro/routes';
    return '/routes';
  }

  function getBasePathPrefix() {
    const path = window.location.pathname || '';
    const match = path.match(/^(.*?)(?:\/(?:delhi-metro|bengaluru-metro|namo-bharat)(?:\/|$))/i);
    return match ? match[1] : '';
  }

  function withBasePath(path) {
    const base = getBasePathPrefix();
    return normalizePath((base ? base.replace(/\/+$/, '') : '') + '/' + String(path || '').replace(/^\/+/, ''));
  }

  function buildStaticRouteURL(cityKey, routeSlug) {
    const routeDir = getCityRouteDirectory(cityKey);
    return withBasePath(routeDir + '/' + routeSlug + '.html');
  }

  async function routeFileExists(url) {
    try {
      const headResponse = await fetch(url, { method: 'HEAD', cache: 'no-store' });
      if (headResponse.ok) return true;
      if (headResponse.status !== 405 && headResponse.status !== 501) return false;
    } catch (err) {
      return false;
    }
    try {
      const getResponse = await fetch(url, { method: 'GET', cache: 'no-store', headers: { Range: 'bytes=0-0' } });
      return getResponse.ok;
    } catch (err) {
      return false;
    }
  }

  function loadScriptOnce(src) {
    const url = withBasePath(src);
    const normalizedUrl = url.replace(/\/+$/, '');
    const existing = Array.from(document.querySelectorAll('script[src]')).find((scriptTag) => {
      const scriptSrc = new URL(scriptTag.getAttribute('src') || '', window.location.origin).pathname.replace(/\/+$/, '');
      return scriptSrc === normalizedUrl;
    });
    if (existing) {
      return Promise.resolve();
    }
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = url;
      script.async = false;
      script.onload = () => {
        script.dataset.loaded = 'true';
        resolve();
      };
      script.onerror = () => reject(new Error('Failed to load ' + url));
      document.head.appendChild(script);
    });
  }

  function ensureInlineResultContainer(anchorEl) {
    const main = anchorEl.closest('main') || document.querySelector('main') || document.body;
    let result = main.querySelector('#route-result');
    if (!result) {
      result = document.createElement('section');
      result.id = 'route-result';
      result.setAttribute('aria-live', 'polite');
      result.style.display = 'none';
      result.style.marginTop = '24px';
      result.style.marginBottom = '24px';
      anchorEl.insertAdjacentElement('afterend', result);
    }
    return result;
  }

  async function renderInlineFallback(anchorEl, context, fromStation, toStation) {
    const payload = await loadData();
    if (!payload) return false;

    await loadScriptOnce('/js/graphBuilder.js');
    await loadScriptOnce('/js/routeFinder.js');
    await loadScriptOnce('/js/routeUI.js');

    const graphBuilder = (typeof GraphBuilder !== 'undefined') ? GraphBuilder : window.GraphBuilder;
    const routeFinder = (typeof RouteFinder !== 'undefined') ? RouteFinder : window.RouteFinder;
    const routeUI = (typeof RouteUI !== 'undefined') ? RouteUI : window.RouteUI;
    if (!graphBuilder || !routeFinder || !routeUI) return false;

    const graph = graphBuilder.build(payload.connections || []);
    const path = routeFinder.findRoute(graph, fromStation.station_id, toStation.station_id);
    if (!path || !path.length) return false;

    const distance = routeFinder.calcDistance(path, graph);
    const fare = routeFinder.calcFare(path, { cityKey: context.cityKey, distance });
    const interchanges = path.filter((step) => step.line_id === 'interchange').length;
    const time = routeFinder.calcTime(distance, interchanges);
    const resultEl = ensureInlineResultContainer(anchorEl);

    routeUI.renderRoute('route-result', path, payload.stations || [], payload.interchanges || [], distance, fare, time, payload.lines || [], context.cityKey);
    setTimeout(() => resultEl.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80);
    return true;
  }

  function trackInteraction(action, meta) {
    if (typeof window.gtag !== 'function') return;
    window.gtag('event', 'station_planner_interaction', {
      event_category: 'station_pages',
      event_label: action,
      planner_action: action,
      station_name: meta.stationName,
      planner_placement: meta.placement,
      city_key: meta.cityKey
    });
  }

  function plannerTemplate() {
    return [
      '<div class="sc" style="max-width:780px;margin:0 auto">',
      '  <div class="fd">',
      '    <label class="fl">From (Origin)</label>',
      '    <input type="text" class="ac-input station-planner-from" readonly aria-label="Origin station">',
      '  </div>',
      '  <div class="fd ac-wrap">',
      '    <label class="fl">To (Destination)</label>',
      '    <input type="text" class="ac-input station-planner-to" list="station-planner-options" placeholder="Search destination station…" autocomplete="off" spellcheck="false" aria-label="Destination station">',
      '    <ul class="ac-list station-planner-list" hidden></ul>',
      '  </div>',
      '  <button class="btn-find station-planner-btn" type="button"><span class="btn-label">Plan Journey</span></button>',
      '</div>'
    ].join('');
  }

  function ensureDatalist(doc) {
    let datalist = doc.getElementById('station-planner-options');
    if (!datalist) {
      datalist = doc.createElement('datalist');
      datalist.id = 'station-planner-options';
      doc.body.appendChild(datalist);
    }
    return datalist;
  }

  async function loadData() {
    if (window.DataLoader && typeof window.DataLoader.loadAll === 'function') {
      return window.DataLoader.loadAll();
    }
    return null;
  }

  function resolveStationByName(map, value) {
    const key = normalizeName(value);
    return map.get(key) || null;
  }

  function bindPlanner(container, context) {
    const fromInput = container.querySelector('.station-planner-from');
    const toInput = container.querySelector('.station-planner-to');
    const listEl = container.querySelector('.station-planner-list');
    const btn = container.querySelector('.station-planner-btn');
    const placement = container.getAttribute('data-planner-placement') || 'unknown';

    if (!fromInput || !toInput || !btn) return;

    fromInput.value = context.currentStationName;
    if (context.currentStation) {
      fromInput.dataset.stationId = context.currentStation.station_id;
      fromInput.value = context.currentStation.station_name;
    }

    let touched = false;
    const markTouched = () => {
      if (touched) return;
      touched = true;
      trackInteraction('focus_destination', {
        stationName: context.currentStationName,
        placement,
        cityKey: context.cityKey
      });
    };

    toInput.addEventListener('focus', markTouched, { passive: true });
    toInput.addEventListener('input', markTouched, { passive: true });

    let activeIdx = -1;

    const hideList = () => {
      if (!listEl) return;
      listEl.hidden = true;
      listEl.innerHTML = '';
      activeIdx = -1;
    };

    const pickDestination = (station) => {
      if (!station) return;
      toInput.value = station.station_name;
      toInput.dataset.stationId = station.station_id;
      hideList();
    };

    const renderList = (query) => {
      if (!listEl) return;
      const text = normalizeName(query);
      const filtered = text
        ? context.stationList.filter((station) => normalizeName(station.station_name).includes(text))
        : context.stationList;
      const limited = filtered.slice(0, 20);
      if (!limited.length) {
        hideList();
        return;
      }
      listEl.innerHTML = limited
        .map((station) => `<li data-id="${escapeHtml(station.station_id)}"><span class="ac-name">${escapeHtml(station.station_name)}</span><span class="ac-city">${escapeHtml(station.city || station.system_id || '')}</span></li>`)
        .join('');
      listEl.hidden = false;
      activeIdx = -1;
    };

    toInput.addEventListener('input', () => {
      toInput.dataset.stationId = '';
      renderList(toInput.value);
    });
    toInput.addEventListener('focus', () => renderList(toInput.value));
    toInput.addEventListener('blur', () => setTimeout(hideList, AUTOCOMPLETE_BLUR_DELAY));

    if (listEl) {
      listEl.addEventListener('mousedown', (event) => {
        const item = event.target.closest('li[data-id]');
        if (!item) return;
        const station = context.stationById.get(item.getAttribute('data-id'));
        pickDestination(station || null);
      });
    }

    toInput.addEventListener('keydown', (event) => {
      if (!listEl || listEl.hidden) return;
      const items = Array.from(listEl.querySelectorAll('li[data-id]'));
      if (!items.length) return;
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        activeIdx = Math.min(activeIdx + 1, items.length - 1);
        items.forEach((el, idx) => el.classList.toggle('ac-active', idx === activeIdx));
        return;
      }
      if (event.key === 'ArrowUp') {
        event.preventDefault();
        activeIdx = activeIdx < 0 ? -1 : Math.max(activeIdx - 1, 0);
        items.forEach((el, idx) => el.classList.toggle('ac-active', idx === activeIdx));
        return;
      }
      if (event.key === 'Enter' && activeIdx >= 0) {
        event.preventDefault();
        const station = context.stationById.get(items[activeIdx].getAttribute('data-id'));
        pickDestination(station || null);
      }
    });

    const handleSubmit = async (event) => {
      if (event && typeof event.preventDefault === 'function') {
        event.preventDefault();
      }

      const fromStation = context.currentStation || resolveStationByName(context.stationMap, fromInput.value);
      const selectedTo = context.stationById.get(toInput.dataset.stationId || '');
      const toStation = selectedTo || resolveStationByName(context.stationMap, toInput.value);

      if (!fromStation) {
        alert('Could not detect the origin station on this page. Please use the main route planner.');
        return;
      }
      if (!toStation) {
        alert('Please select a valid destination station from the suggestions.');
        return;
      }
      if (fromStation.station_id === toStation.station_id) {
        alert('Origin and destination cannot be the same station.');
        return;
      }

      trackInteraction('plan_journey', {
        stationName: fromStation.station_name,
        placement,
        cityKey: context.cityKey
      });

      const routeSlug = stationToSlug(fromStation) + '-to-' + stationToSlug(toStation);
      const targetURL = buildStaticRouteURL(context.cityKey, routeSlug);

      btn.disabled = true;
      try {
        const canRedirect = await routeFileExists(targetURL);
        if (canRedirect) {
          window.location.assign(targetURL);
          return;
        }
        const renderedInline = await renderInlineFallback(container, context, fromStation, toStation);
        if (!renderedInline) {
          alert('Detailed route page is not available yet for this pair. Please use the main route planner.');
        }
      } finally {
        btn.disabled = false;
      }
    };

    btn.addEventListener('click', handleSubmit);
    const parentForm = btn.closest('form');
    if (parentForm) {
      parentForm.addEventListener('submit', handleSubmit);
    }
    toInput.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        handleSubmit(event);
      }
    });
  }

  async function initStationPlanner() {
    const plannerRoots = Array.from(document.querySelectorAll('[data-station-planner]'));
    if (!plannerRoots.length) return;

    plannerRoots.forEach((root) => {
      if (!root.querySelector('.station-planner-btn')) {
        root.innerHTML = plannerTemplate();
      }
    });

    const helper = window.MetroGuidePlanner || {};
    const currentStationName = typeof helper.resolveCurrentOrigin === 'function'
      ? helper.resolveCurrentOrigin(document)
      : ((document.querySelector('h1.rp-title, h1') || {}).textContent || '').trim();
    if (!currentStationName) return;

    if (typeof helper.ensureCurrentOrigin === 'function') {
      helper.ensureCurrentOrigin(document, currentStationName);
    }

    const payload = await loadData();
    const stations = Array.isArray(payload && payload.stations) ? payload.stations : [];
    const stationMap = new Map();
    const stationById = new Map();

    stations.forEach((station) => {
      if (!station || !station.station_id || !station.station_name) return;
      stationById.set(station.station_id, station);
      const key = normalizeName(station.station_name);
      if (!key || stationMap.has(key)) return;
      stationMap.set(key, station);
    });

    const stationList = Array.from(stationById.values()).sort((a, b) => a.station_name.localeCompare(b.station_name));

    const datalist = ensureDatalist(document);
    datalist.innerHTML = stationList
      .map((station) => '<option value="' + station.station_name.replace(/"/g, '&quot;') + '"></option>')
      .join('');

    const cityKey = detectCityKey();
    const currentStation = resolveStationByName(stationMap, currentStationName);

    const context = {
      cityKey,
      currentStationName,
      currentStation,
      stationMap,
      stationById,
      stationList
    };

    plannerRoots.forEach((root) => bindPlanner(root, context));
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initStationPlanner);
  } else {
    initStationPlanner();
  }
})();
