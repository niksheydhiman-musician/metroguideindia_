/**
 * routeUI.js
 * Builds the visual route card from a BFS path.
 * Handles regular stops, interchange nodes, origin and destination styling.
 */
const RouteUI = (() => {

  const LINE_META = {
    rrts_main:         { color: '#E8384F', label: 'Namo Bharat RRTS' },
    meerut_metro_main: { color: '#2DDE4A', label: 'Meerut Metro'     },
    interchange:       { color: '#F5C842', label: 'Interchange'       },
  };

  function getColor(line_id) {
    return (LINE_META[line_id] || LINE_META['rrts_main']).color;
  }
  function getLabel(line_id) {
    return (LINE_META[line_id] || LINE_META['rrts_main']).label;
  }

  /**
   * Render a complete route into #containerId.
   */
  function renderRoute(containerId, path, stations, interchanges, distance, fare, time) {
    const el = document.getElementById(containerId);
    if (!el) return;

    const stationMap     = Object.fromEntries(stations.map(s     => [s.station_id, s]));
    const interchangeMap = Object.fromEntries(interchanges.map(i => [i.station_id, i]));

    // Enrich each step with display data
    const steps = path.map((step, idx) => ({
      ...step,
      station:     stationMap[step.station_id] || {},
      intData:     interchangeMap[step.station_id] || null,
      isInterchange: step.line_id === 'interchange',
      isFirst:     idx === 0,
      isLast:      idx === path.length - 1,
    }));

    el.innerHTML = `
      <div class="result-card" id="result-inner">

        <!-- Summary Bar -->
        <div class="result-summary">
          <div class="sum-item">
            <div class="sum-val">${distance} <span>km</span></div>
            <div class="sum-lbl">Distance</div>
          </div>
          <div class="sum-sep"></div>
          <div class="sum-item">
            <div class="sum-val">₹${fare}</div>
            <div class="sum-lbl">Est. Fare</div>
          </div>
          <div class="sum-sep"></div>
          <div class="sum-item">
            <div class="sum-val">${time} <span>min</span></div>
            <div class="sum-lbl">Est. Time</div>
          </div>
        </div>

        <!-- Station Steps -->
        <div class="result-steps">
          ${steps.map((s, i) => renderStep(s, i, steps)).join('')}
        </div>

      </div>
    `;

    el.style.display = 'block';
    // Trigger entrance animation
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const card = document.getElementById('result-inner');
        if (card) card.classList.add('visible');
      });
    });
  }

  function renderStep(s, i, steps) {
    const { station_id, line_id, station, intData, isInterchange, isFirst, isLast } = s;

    // Resolve the colour for the connector line going INTO this step
    function resolveLineColor(fromIdx) {
      for (let j = fromIdx; j >= 0; j--) {
        const lid = steps[j].line_id;
        if (lid && lid !== 'interchange') return getColor(lid);
      }
      return getColor('rrts_main');
    }

    const lineColorAbove = i > 0 ? resolveLineColor(i - 1) : getColor(line_id || 'rrts_main');
    const lineColorBelow = resolveLineColor(i);

    const name = station.station_name || station_id;

    if (isInterchange && intData) {
      return `
        <div class="step interchange-step">
          <div class="step-rail">
            <div class="rail-seg" style="background:${lineColorAbove}"></div>
            <div class="rail-node xchange-node">
              <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2.2">
                <path d="M5 13l-3-3 3-3M15 7l3 3-3 3M2 10h16"/>
              </svg>
            </div>
            <div class="rail-seg" style="background:${getColor(steps[i+1]?.line_id || 'meerut_metro_main')}"></div>
          </div>
          <div class="step-body xchange-body">
            <div class="xchange-tag">Change Train</div>
            <div class="xchange-name">${name}</div>
            <div class="xchange-detail">
              <span class="platform-pill">${intData.change_platform}</span>
              <span class="xchange-instr">${intData.instructions}</span>
            </div>
          </div>
        </div>`;
    }

    // Determine display line for badge (use next non-interchange if current is null/interchange)
    let displayLine = line_id;
    if (!displayLine || displayLine === 'interchange') {
      for (let j = i + 1; j < steps.length; j++) {
        if (steps[j].line_id && steps[j].line_id !== 'interchange') { displayLine = steps[j].line_id; break; }
      }
      if (!displayLine) displayLine = 'rrts_main';
    }

    const dotColor = getColor(displayLine);

    return `
      <div class="step regular-step ${isFirst ? 'step-first' : ''} ${isLast ? 'step-last' : ''}">
        <div class="step-rail">
          ${!isFirst ? `<div class="rail-seg" style="background:${lineColorAbove}"></div>` : '<div class="rail-seg invisible"></div>'}
          <div class="rail-node ${isFirst ? 'node-origin' : isLast ? 'node-dest' : 'node-mid'}" style="--dot-color:${dotColor}">
            ${isFirst ? '<span>A</span>' : isLast ? '<span>B</span>' : ''}
          </div>
          ${!isLast ? `<div class="rail-seg" style="background:${lineColorBelow}"></div>` : '<div class="rail-seg invisible"></div>'}
        </div>
        <div class="step-body">
          <div class="step-name">${name}</div>
          <div class="step-tags">
            <span class="line-pill" style="--pill-color:${dotColor}">${getLabel(displayLine)}</span>
            ${station.city ? `<span class="city-pill">${station.city}</span>` : ''}
          </div>
        </div>
      </div>`;
  }

  function renderError(containerId, msg) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = `
      <div class="error-box">
        <div class="error-icon">⚠️</div>
        <p>${msg}</p>
      </div>`;
    el.style.display = 'block';
  }

  function clear(containerId) {
    const el = document.getElementById(containerId);
    if (el) { el.innerHTML = ''; el.style.display = 'none'; }
  }

  return { renderRoute, renderError, clear };
})();
