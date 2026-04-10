(function () {
  'use strict';

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function stationToSlug(stationId) {
    return String(stationId || '')
      .replace(/_rrts$/, '')
      .replace(/_meerut_metro$/, '')
      .replace(/_/g, '-');
  }

  function detectCityKey() {
    const path = String(window.location.pathname || '').toLowerCase();
    if (/\/delhi-metro(?:\/|$)/.test(path)) return 'delhi';
    if (/\/bengaluru-metro(?:\/|$)/.test(path)) return 'bengaluru';
    if (/\/namo-bharat(?:\/|$)/.test(path)) return 'rrts';
    return null;
  }

  function hasScriptLoaded(path) {
    var normalized = String(path || '').replace(/\/+$/, '');
    return Array.from(document.querySelectorAll('script[src]')).some(function (tag) {
      try {
        var scriptPath = new URL(tag.getAttribute('src') || '', window.location.origin).pathname.replace(/\/+$/, '');
        return scriptPath === normalized;
      } catch (error) {
        return false;
      }
    });
  }

  function loadScriptOnce(path) {
    if (hasScriptLoaded(path)) return Promise.resolve();
    return new Promise(function (resolve, reject) {
      var script = document.createElement('script');
      script.src = path;
      script.async = false;
      script.onload = function () { resolve(); };
      script.onerror = function () { reject(new Error('Failed to load ' + path)); };
      document.head.appendChild(script);
    });
  }

  function setupAutocomplete(searchEl, hiddenEl, listEl, stationList) {
    if (!searchEl || !hiddenEl || !listEl) return;

    let activeIndex = -1;

    function hideList() {
      listEl.hidden = true;
      listEl.innerHTML = '';
      activeIndex = -1;
    }

    function renderList(query) {
      const q = String(query || '').toLowerCase().trim();
      const filtered = q
        ? stationList.filter((s) => s.name.toLowerCase().includes(q) || s.city.toLowerCase().includes(q) || s.system.toLowerCase().includes(q))
        : stationList;
      const limited = filtered.slice(0, 20);
      if (!limited.length) {
        hideList();
        return;
      }

      listEl.innerHTML = limited
        .map((s) => '<li data-id="' + escapeHtml(s.id) + '"><span class="ac-name">' + escapeHtml(s.name) + '</span><span class="ac-city">' + escapeHtml(s.city) + '</span></li>')
        .join('');
      listEl.hidden = false;
      activeIndex = -1;
    }

    function selectItem(item) {
      if (!item) return;
      const stationId = item.getAttribute('data-id') || '';
      const station = stationList.find((s) => s.id === stationId);
      if (!station) return;
      hiddenEl.value = station.id;
      searchEl.value = station.name;
      hideList();
    }

    searchEl.addEventListener('input', function () {
      hiddenEl.value = '';
      renderList(searchEl.value);
    });

    searchEl.addEventListener('focus', function () {
      renderList(searchEl.value);
    });

    searchEl.addEventListener('blur', function () {
      window.setTimeout(hideList, 180);
    });

    searchEl.addEventListener('keydown', function (event) {
      const items = Array.from(listEl.querySelectorAll('li[data-id]'));
      if (listEl.hidden || !items.length) return;

      if (event.key === 'ArrowDown') {
        event.preventDefault();
        activeIndex = Math.min(activeIndex + 1, items.length - 1);
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        activeIndex = Math.max(activeIndex - 1, 0);
      } else if (event.key === 'Enter' && activeIndex >= 0) {
        event.preventDefault();
        selectItem(items[activeIndex]);
        return;
      } else if (event.key === 'Escape') {
        hideList();
        return;
      } else {
        return;
      }

      items.forEach(function (el, idx) {
        el.classList.toggle('ac-active', idx === activeIndex);
      });
      if (items[activeIndex]) {
        items[activeIndex].scrollIntoView({ block: 'nearest' });
      }
    });

    listEl.addEventListener('mousedown', function (event) {
      const item = event.target.closest('li[data-id]');
      if (!item) return;
      selectItem(item);
    });
  }

  function init(container, payload) {
    const srcSearch = container.querySelector('#global-src-search');
    const srcHidden = container.querySelector('#global-src');
    const srcList = container.querySelector('#global-src-list');
    const dstSearch = container.querySelector('#global-dst-search');
    const dstHidden = container.querySelector('#global-dst');
    const dstList = container.querySelector('#global-dst-list');
    const findBtn = container.querySelector('#global-find-btn');
    const swapBtn = container.querySelector('#global-swap-btn');

    if (!srcSearch || !srcHidden || !srcList || !dstSearch || !dstHidden || !dstList || !findBtn || !swapBtn) {
      return;
    }

    const stations = Array.isArray(payload && payload.stations) ? payload.stations : [];
    const stationList = stations
      .filter(function (s) {
        return s && s.station_id && s.station_name;
      })
      .map(function (s) {
        return {
          id: s.station_id,
          name: String(s.station_name || ''),
          city: String(s.city || ''),
          system: String(s.system_id || '')
        };
      });

    setupAutocomplete(srcSearch, srcHidden, srcList, stationList);
    setupAutocomplete(dstSearch, dstHidden, dstList, stationList);

    swapBtn.addEventListener('click', function () {
      const srcId = srcHidden.value;
      const srcName = srcSearch.value;
      srcHidden.value = dstHidden.value;
      srcSearch.value = dstSearch.value;
      dstHidden.value = srcId;
      dstSearch.value = srcName;
    });

    function submitRoute() {
      const fromId = srcHidden.value;
      const toId = dstHidden.value;

      if (!fromId || !toId) {
        alert('Please select both a source and destination station.');
        return;
      }
      if (fromId === toId) {
        alert('Source and destination cannot be the same station.');
        return;
      }

      const payloadCity = String((payload && payload.cityKey) || '').toLowerCase();
      const city = payloadCity || detectCityKey() || 'rrts';
      const slug = stationToSlug(fromId) + '-to-' + stationToSlug(toId);
      const target = '/route.html?city=' + encodeURIComponent(city) + '&r=' + encodeURIComponent(slug) + '&from=' + encodeURIComponent(fromId) + '&to=' + encodeURIComponent(toId);
      window.location.assign(target);
    }

    findBtn.addEventListener('click', function (event) {
      event.preventDefault();
      submitRoute();
    });

    [srcSearch, dstSearch].forEach(function (inputEl) {
      inputEl.addEventListener('keydown', function (event) {
        if (event.key === 'Enter') {
          event.preventDefault();
          submitRoute();
        }
      });
    });
  }

  async function bootstrap() {
    const container = document.getElementById('global-search-section');
    if (!container) return;

    if (!window.DataLoader || typeof window.DataLoader.loadAll !== 'function') {
      try {
        await loadScriptOnce('/js/dataLoader.js');
      } catch (error) {
        return;
      }
      if (!window.DataLoader || typeof window.DataLoader.loadAll !== 'function') {
        return;
      }
    }

    try {
      const payload = await window.DataLoader.loadAll();
      init(container, payload || {});
    } catch (error) {
      // No-op fallback: keep UI visible even if data load fails.
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrap, { once: true });
  } else {
    bootstrap();
  }
})();
