/**
 * routeUI.js
 * Renders the route result card including interchange steps.
 * Works with Dijkstra path which includes explicitly inserted interchange nodes.
 */
const RouteUI = (() => {

  const LINE = {
    rrts_main:         { color: '#C0392B', label: 'Namo Bharat RRTS' },
    meerut_metro_main: { color: '#27764A', label: 'Meerut Metro'     },
    interchange:       { color: '#A0620A', label: 'Interchange'       },
  };
  const getLine = lid => LINE[lid] || LINE.rrts_main;

  function renderRoute(cid, path, stations, interchanges, distance, fare, time) {
    const el = document.getElementById(cid);
    if (!el) return;

    const stMap = Object.fromEntries(stations.map(s => [s.station_id, s]));

    // Build interchange lookup — keyed by BOTH system variants of the station name
    const ixMap = {};
    interchanges.forEach(ix => {
      ixMap[ix.station_id] = ix;
      // Also index by metro twin
      const twin = ix.station_id.endsWith('_rrts')
        ? ix.station_id.replace('_rrts', '_meerut_metro')
        : ix.station_id.replace('_meerut_metro', '_rrts');
      ixMap[twin] = ix;
    });

    const steps = path.map((p, i) => ({
      ...p,
      st:    stMap[p.station_id] || {},
      ix:    ixMap[p.station_id] || null,
      isX:   p.line_id === 'interchange',
      first: i === 0,
      last:  i === path.length - 1,
    }));

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
          ${steps.map((s, i) => renderStep(s, i, steps)).join('')}
        </div>
      </div>`;

    el.style.display = 'block';
    requestAnimationFrame(() => requestAnimationFrame(() => {
      document.getElementById('rc-inner')?.classList.add('rc-visible');
    }));
  }

  /* Resolve the line color by scanning backward (direction='up') or forward */
  function resolveColor(steps, idx, dir) {
    const range = dir === 'up'
      ? Array.from({length: idx}, (_, k) => idx - 1 - k)
      : Array.from({length: steps.length - idx - 1}, (_, k) => idx + 1 + k);
    for (const j of range) {
      const lid = steps[j].line_id;
      if (lid && lid !== 'interchange') return getLine(lid).color;
    }
    return getLine('rrts_main').color;
  }

  function renderStep(s, i, steps) {
    const { station_id, line_id, st, ix, isX, first, last } = s;
    const name = st.station_name || station_id;
    const colorAbove = i > 0 ? resolveColor(steps, i, 'up') : getLine(line_id || 'rrts_main').color;
    const colorBelow = resolveColor(steps, i, 'down');

    if (isX && ix) {
      // Find next non-interchange line for "→ Metro" label
      const nextStep = steps.slice(i + 1).find(s2 => s2.line_id && s2.line_id !== 'interchange');
      const toColor  = nextStep ? getLine(nextStep.line_id).color : getLine('meerut_metro_main').color;
      const toLabel  = nextStep ? getLine(nextStep.line_id).label : 'Meerut Metro';

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
          <div class="step-body xchange-card">
            <div class="xchange-label">🔄 Change Train</div>
            <div class="xchange-name">${name}</div>
            <div class="xchange-meta">
              <span class="platform-tag">${ix.change_platform}</span>
              <span class="xchange-arrow">→</span>
              <span class="xchange-to" style="color:${toColor}">${toLabel}</span>
            </div>
          </div>
        </div>`;
    }

    // Determine line badge — look at surrounding non-interchange steps
    let displayLid = line_id;
    if (!displayLid || displayLid === 'interchange') {
      for (let j = i + 1; j < steps.length; j++) {
        if (steps[j].line_id && steps[j].line_id !== 'interchange') { displayLid = steps[j].line_id; break; }
      }
      if (!displayLid) {
        for (let j = i - 1; j >= 0; j--) {
          if (steps[j].line_id && steps[j].line_id !== 'interchange') { displayLid = steps[j].line_id; break; }
        }
      }
      if (!displayLid) displayLid = 'rrts_main';
    }
    const lm = getLine(displayLid);

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
            ${st.city ? `<span class="city-tag">${st.city}</span>` : ''}
          </div>
        </div>
      </div>`;
  }

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
