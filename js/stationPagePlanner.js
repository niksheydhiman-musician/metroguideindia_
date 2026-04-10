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

  function stationToSlug(stationId) {
    return String(stationId || '')
      .replace(/_rrts$/, '')
      .replace(/_meerut_metro$/, '')
      .replace(/_/g, '-');
  }

  function getBasePathPrefix() {
    const path = window.location.pathname || '';
    const match = path.match(/^(.*?)(?:\/(?:delhi-metro|bengaluru-metro|namo-bharat)(?:\/|$))/i);
    return match ? match[1] : '';
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
        .map((station) => '<li data-id="' + station.station_id + '"><span class="ac-name">' + station.station_name + '</span><span class="ac-city">' + (station.city || station.system_id || '') + '</span></li>')
        .join('');
      listEl.hidden = false;
      activeIdx = -1;
    };

    toInput.addEventListener('input', () => {
      toInput.dataset.stationId = '';
      renderList(toInput.value);
    });
    toInput.addEventListener('focus', () => renderList(toInput.value));
    toInput.addEventListener('blur', () => setTimeout(hideList, 180));

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
        activeIdx = Math.max(activeIdx - 1, 0);
        items.forEach((el, idx) => el.classList.toggle('ac-active', idx === activeIdx));
        return;
      }
      if (event.key === 'Enter' && activeIdx >= 0) {
        event.preventDefault();
        const station = context.stationById.get(items[activeIdx].getAttribute('data-id'));
        pickDestination(station || null);
      }
    });

    const handleSubmit = () => {
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

      const slug = stationToSlug(fromStation.station_id) + '-to-' + stationToSlug(toStation.station_id);
      const target = window.location.origin + getBasePathPrefix() + '/route.html?city=' + encodeURIComponent(context.cityKey) + '&r=' + encodeURIComponent(slug);
      window.location.href = target;
    };

    btn.addEventListener('click', handleSubmit);
    toInput.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        event.preventDefault();
        handleSubmit();
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
