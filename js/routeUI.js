/**
 * routeUI.js — renders the route result card
 *
 * Works with the clean path from routeFinder.cleanPath():
 *   - Regular steps have line_id = 'rrts_main' or 'meerut_metro_main'
 *   - Interchange steps have line_id = 'interchange' and station_id = RRTS-side id
 *     so interchanges.json lookup always works
 *   - No duplicate interchange steps (routeFinder guarantees exactly one per crossing)
 */
const RouteUI = (() => {

  const DEFAULT_LINE = {
    rrts_main:         { color: '#C0392B', label: 'Namo Bharat RRTS' },
    meerut_metro_main: { color: '#27764A', label: 'Meerut Metro'     },
    interchange:       { color: '#A0620A', label: 'Interchange'       },
  };
  let activeLineMap = { ...DEFAULT_LINE };
  const getLine = lid => activeLineMap[lid] || DEFAULT_LINE.rrts_main;
  const esc = (s) => String(s ?? '')
  .replaceAll('&','&amp;')
  .replaceAll('<','&lt;')
  .replaceAll('>','&gt;')
  .replaceAll('"','&quot;')
  .replaceAll("'","&#39;");

  function buildLineMap(lines = []) {
    const map = { ...DEFAULT_LINE };
    lines.forEach(line => {
      if (!line?.line_id) return;
      map[line.line_id] = {
        color: line.color || map[line.line_id]?.color || '#C0392B',
        label: line.line_name || line.line_id,
      };
    });
    return map;
  }

  /* ── Main render ─────────────────────────────────────────────────────────── */
  function renderRoute(cid, path, stations, interchanges, distance, fare, time, lines = [], cityKey = '') {
    const el = document.getElementById(cid);
    if (!el) return;
    activeLineMap = buildLineMap(lines);

    // Build lookup maps
    const stMap = {};
    stations.forEach(s => stMap[s.station_id] = s);

    // ixMap keyed by RRTS station_id (routeFinder always stores RRTS-side id)
    const ixMap = {};
    interchanges.forEach(ix => {
      ixMap[ix.station_id] = ix;
      // Also accept metro twin in case of any edge case
      const metroTwin = ix.station_id.replace(/_rrts$/, '_meerut_metro');
      ixMap[metroTwin] = ix;
    });
    // Use station-level interchange flags as additional lookup fallback.
    stations.forEach(s => {
      if (String(s.interchange || '').toLowerCase() !== 'yes') return;
      if (!ixMap[s.station_id]) {
        ixMap[s.station_id] = {
          station_id: s.station_id,
          change_platform: 'Follow interchange signs',
          instructions: `Change trains at ${s.station_name}`,
        };
      }
    });

    // Resolve station name: try stMap directly, then try RRTS/metro twin
    function stName(id) {
      if (stMap[id]) return stMap[id].station_name;
      const twin = id.endsWith('_rrts')
        ? id.replace(/_rrts$/, '_meerut_metro')
        : id.replace(/_meerut_metro$/, '_rrts');
      if (stMap[twin]) return stMap[twin].station_name;
      // Strip suffix as last resort
      return id.replace(/_rrts$/, '').replace(/_meerut_metro$/, '').replace(/_/g, ' ');
    }
    function stCity(id) {
      if (stMap[id]) return stMap[id].city || '';
      const twin = id.endsWith('_rrts') ? id.replace(/_rrts$/, '_meerut_metro') : id.replace(/_meerut_metro$/, '_rrts');
      return stMap[twin]?.city || '';
    }

    // Count interchange steps for time
    const nX = path.filter(p => p.line_id === 'interchange').length;

    el.innerHTML = `
      <div class="rc" id="rc-inner">
        <div class="rc-summary">
          <div class="rc-sum-item">
            <div class="rc-val">${distance}<span> km</span></div>
            <div class="rc-lbl">Distance</div>
          </div>
          <div class="rc-sep"></div>
          <div class="rc-sum-item">
            <div class="rc-val">₹${fare}</div>
            <div class="rc-lbl">Std. Fare</div>
          </div>
          <div class="rc-sep"></div>
          <div class="rc-sum-item">
            <div class="rc-val">${time}<span> min</span></div>
            <div class="rc-lbl">Est. Time</div>
          </div>
        </div>
        <div class="rc-steps">
          ${path.map((step, i) => renderStep(step, i, path, stName, stCity, ixMap)).join('')}
        </div>
      </div>
      ${(() => {
        const fromId   = path[0]?.station_id;
        const toId     = path[path.length - 1]?.station_id;
        const fromName = stName(fromId);
        const toName   = stName(toId);

        const hasR = path.some(p => p.line_id === 'rrts_main');
        const hasM = path.some(p => p.line_id === 'meerut_metro_main');
        const city = String(cityKey || '').toLowerCase();
        const isDelhi = city === 'delhi';
        const isBengaluru = city === 'bengaluru';
        const systemLabel = isDelhi
          ? 'Delhi Metro'
          : isBengaluru
            ? 'Bengaluru Metro'
            : (hasR && hasM) ? 'RRTS + Metro' : hasM ? 'Meerut Metro' : 'RRTS';

        const premium = Math.round((Number(fare || 0) * 1.2) / 10) * 10;
        const t    = Number(time || 0);
        const tMin = Math.max(5, Math.round(t - 10));
        const tMax = Math.max(tMin, Math.round(t + 10));

        // Top stations: pick up to 4 intermediate non-interchange stations
        const mids = path.slice(1, -1)
          .filter(p => p.line_id !== 'interchange')
          .map(p => stName(p.station_id));

        const seen = new Set();
        const topStations = mids.filter(n => (seen.has(n) ? false : (seen.add(n), true))).slice(0, 4);

        // Major hubs
        const hubs = [];
        const fn = (fromName + ' ' + toName).toLowerCase();
        if (fn.includes('sarai kale khan')) hubs.push('Delhi Metro Pink Line & ISBT at Sarai Kale Khan');
        if (fn.includes('anand vihar')) hubs.push('Delhi Metro Blue Line & Anand Vihar ISBT');

        // Determine fare display and ticketing based on system
        const isMeerutMetroOnly = !hasR && hasM;  // Meerut Metro only (single-class, no Premium coach)
        const isRRTSMix = hasR && hasM;   // RRTS + Meerut Metro interchange
        const showPremium = hasR && !isMeerutMetroOnly && !isDelhi && !isBengaluru;

        const fareDisplay = !showPremium
          ? `₹${esc(fare)} (Standard).`
          : `~₹${esc(fare)} (Standard) | ~₹${esc(premium)} (Premium).`;

        // Static disclaimer string — no user input involved, escaping not required
        const interchangeDisclaimer = isRRTSMix
          ? `<div class="route-seo-note">⚠️ <strong>Note:</strong> Premium ticket holders must move to the Standard/General coach when transferring to Meerut Metro trains.</div>`
          : '';

        const ticketingConfig = isDelhi
          ? { pre: 'Use DMRC channels for QR and smart card travel.', url: 'https://www.delhimetrorail.com/', color: '#1a2a6c' }
          : isBengaluru
            ? { pre: 'Use BMRCL channels for QR and smart card travel.', url: 'https://www.bmrc.co.in/', color: '#6c2e9d' }
            : { pre: 'Use Namo Bharat App or NCMC.', url: 'https://www.rrts.co.in/', color: '#C0392B' };
        const ticketingText = `${ticketingConfig.pre} <a href="${ticketingConfig.url}" rel="nofollow noopener" target="_blank" style="color:${ticketingConfig.color};font-weight:600">Official Website</a>`;

        return `
          <div class="route-seo-box" data-system="${esc(systemLabel)}">
            <div class="route-seo-title">Route Summary</div>
            <p class="route-seo-lead">
              Looking for ${esc(fromName)} to ${esc(toName)} ${esc(systemLabel)} route?
              This ${esc(distance)} km trip takes about ${esc(time)} minutes on average.
            </p>
            <div class="route-seo-lines">
              <div><strong>Fare:</strong> ${fareDisplay}</div>
              ${interchangeDisclaimer}
              <div><strong>Time:</strong> Approx. ${esc(tMin)}–${esc(tMax)} mins.</div>
              <div><strong>Interchanges:</strong> ${esc(nX)} (${esc(nX === 0 ? 'Direct Route' : 'With Interchanges')}).</div>
              <div><strong>Major Hubs:</strong> ${esc(hubs.length ? hubs.join('; ') : '—')}.</div>
              <div><strong>Top Stations:</strong> ${esc(topStations.length ? topStations.join(', ') : '—')}.</div>
              <div><strong>Ticketing:</strong> ${ticketingText}</div>
            </div>
          </div>`;
      })()}`;

    el.style.display = 'block';
    requestAnimationFrame(() => requestAnimationFrame(() => {
      document.getElementById('rc-inner')?.classList.add('rc-visible');
    }));
  }

  /* ── Color helpers ───────────────────────────────────────────────────────── */
  // Scan outward from index to find the nearest real line color
  function nearestColor(path, idx, direction) {
    const range = direction === 'up'
      ? Array.from({length: idx},        (_, k) => idx - 1 - k)
      : Array.from({length: path.length - idx - 1}, (_, k) => idx + 1 + k);
    for (const j of range) {
      const lid = path[j].line_id;
      if (lid && lid !== 'interchange') return getLine(lid).color;
    }
    return getLine('rrts_main').color;
  }

  /* ── Step renderer ───────────────────────────────────────────────────────── */
  function renderStep(step, i, path, stName, stCity, ixMap) {
    const { station_id, line_id } = step;
    const first = i === 0, last = i === path.length - 1;
    const colorAbove = i > 0 ? nearestColor(path, i, 'up') : getLine(line_id || 'rrts_main').color;
    const colorBelow = nearestColor(path, i, 'down');

    /* ── Interchange step ────────────────────────────────────────────────── */
    if (line_id === 'interchange') {
      const ix = ixMap[station_id];
      const name = stName(station_id);

      // Find next real line (what we're switching TO)
      const nextStep = path.slice(i + 1).find(s => s.line_id && s.line_id !== 'interchange');
      const toColor  = nextStep ? getLine(nextStep.line_id).color : getLine('meerut_metro_main').color;
      const toLabel  = nextStep ? getLine(nextStep.line_id).label : 'Meerut Metro';
      const platform = ix ? ix.change_platform : 'Follow interchange signs';
      const instruction = `Change trains at ${name}`;

      return `
        <div class="step step-xchange">
          <div class="rail">
            <div class="rail-line" style="background:${colorAbove}"></div>
            <div class="rail-dot dot-xchange">
              <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
                <path d="M4 12l-3-3 3-3M14 6l3 3-3 3M1 9h16"/>
              </svg>
            </div>
            <div class="rail-line" style="background:${toColor}"></div>
          </div>
          <div class="xchange-card">
            <div class="xchange-label">🔄 ${instruction}</div>
            <div class="xchange-name">${name}</div>
            <div class="xchange-meta">
              <span class="platform-tag">${platform}</span>
              <span class="xchange-arrow">→</span>
              <span class="xchange-to" style="color:${toColor}">${toLabel}</span>
            </div>
          </div>
        </div>`;
    }

    /* ── Regular step ────────────────────────────────────────────────────── */
    // Resolve display line: if null (origin), look forward; else use own line_id
    let displayLid = line_id;
    if (!displayLid) {
      for (let j = i + 1; j < path.length; j++) {
        if (path[j].line_id && path[j].line_id !== 'interchange') { displayLid = path[j].line_id; break; }
      }
      if (!displayLid) displayLid = 'rrts_main';
    }
    const lm = getLine(displayLid);
    const name = stName(station_id);
    const city = stCity(station_id);

    return `
      <div class="step step-regular ${first ? 'step-first' : ''} ${last ? 'step-last' : ''}">
        <div class="rail">
          ${!first ? `<div class="rail-line" style="background:${colorAbove}"></div>` : '<div class="rail-line invis"></div>'}
          <div class="rail-dot ${first ? 'dot-origin' : last ? 'dot-dest' : 'dot-mid'}" style="--dc:${lm.color}">
            ${first ? '<span>A</span>' : last ? '<span>B</span>' : ''}
          </div>
          ${!last ? `<div class="rail-line" style="background:${colorBelow}"></div>` : '<div class="rail-line invis"></div>'}
        </div>
        <div class="step-body">
          <div class="step-name">${name}</div>
          <div class="step-tags">
            <span class="line-tag" style="background:${lm.color}14;color:${lm.color};border-color:${lm.color}38">${lm.label}</span>
            ${city ? `<span class="city-tag">${city}</span>` : ''}
          </div>
        </div>
      </div>`;
  }

  /* ── Error / clear ───────────────────────────────────────────────────────── */
  function renderError(cid, msg) {
    const el = document.getElementById(cid);
    if (!el) return;
    el.innerHTML = `<div class="rc-error"><span>⚠️</span><p>${msg}</p></div>`;
    el.style.display = 'block';
  }

  function clear(cid) {
    const el = document.getElementById(cid);
    if (el) { el.innerHTML = ''; el.style.display = 'none'; }
  }

  return { renderRoute, renderError, clear };
})();
