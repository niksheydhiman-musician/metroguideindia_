/**
 * routeFinder.js
 * Dijkstra's algorithm for shortest-DISTANCE path.
 *
 * WHY DIJKSTRA INSTEAD OF BFS:
 *   BFS finds fewest hops. For "New Ashok Nagar → Bhaisali Bus Adda",
 *   BFS incorrectly picks interchange at Begumpul (fewer hops going 1 stop
 *   backwards on Metro) over Shatabdi Nagar (correct, shorter total distance).
 *   Dijkstra uses real km weights, always finding the shortest real-world path.
 *
 * PATH RECONSTRUCTION:
 *   After Dijkstra, we reconstruct the explicit step list including interchange
 *   nodes so the UI can render "Change Train" cards correctly.
 *
 * INTERCHANGE DISPLAY:
 *   After finding the shortest path, we scan for system transitions and
 *   INSERT interchange steps at every point where the line changes system.
 *   This ensures all 4 interchange stations show the card when crossed.
 */
const RouteFinder = (() => {

  /* ── Min-heap (priority queue) ───────────────────────────────────────────── */
  class MinHeap {
    constructor() { this.h = []; }
    push(item) {
      this.h.push(item);
      this._up(this.h.length - 1);
    }
    pop() {
      const top = this.h[0];
      const last = this.h.pop();
      if (this.h.length) { this.h[0] = last; this._down(0); }
      return top;
    }
    get size() { return this.h.length; }
    _up(i) {
      while (i > 0) {
        const p = (i - 1) >> 1;
        if (this.h[p].dist <= this.h[i].dist) break;
        [this.h[p], this.h[i]] = [this.h[i], this.h[p]];
        i = p;
      }
    }
    _down(i) {
      const n = this.h.length;
      while (true) {
        let s = i, l = 2*i+1, r = 2*i+2;
        if (l < n && this.h[l].dist < this.h[s].dist) s = l;
        if (r < n && this.h[r].dist < this.h[s].dist) s = r;
        if (s === i) break;
        [this.h[s], this.h[i]] = [this.h[i], this.h[s]];
        i = s;
      }
    }
  }

  /* ── Dijkstra ─────────────────────────────────────────────────────────────
     Returns array of { station_id, line_id } representing the optimal path.
     line_id is the edge used to ARRIVE at that station.
  ────────────────────────────────────────────────────────────────────────── */
  function findRoute(graph, src, dst) {
    if (!graph[src] || !graph[dst]) return null;
    if (src === dst) return [{ station_id: src, line_id: null }];

    const dist = {};   // best distance to each node
    const prev = {};   // { station_id, line_id } of predecessor
    const heap = new MinHeap();

    dist[src] = 0;
    heap.push({ dist: 0, id: src });

    while (heap.size) {
      const { dist: d, id } = heap.pop();
      if (d > dist[id]) continue;  // stale entry
      if (id === dst) break;

      for (const edge of (graph[id] || [])) {
        const nd = d + edge.weight;
        if (dist[edge.neighbor] === undefined || nd < dist[edge.neighbor]) {
          dist[edge.neighbor] = nd;
          prev[edge.neighbor] = { from: id, line_id: edge.line_id };
          heap.push({ dist: nd, id: edge.neighbor });
        }
      }
    }

    if (dist[dst] === undefined) return null;

    // Reconstruct path backwards
    const raw = [];
    let cur = dst;
    while (cur !== undefined) {
      const p = prev[cur];
      raw.unshift({ station_id: cur, line_id: p ? p.line_id : null });
      cur = p ? p.from : undefined;
    }

    // Insert interchange steps where system changes
    return insertInterchangeSteps(raw, graph);
  }

  /**
   * Walk the raw Dijkstra path and insert explicit interchange nodes
   * wherever the line transitions through an interchange edge.
   * This gives the UI the 'interchange' line_id entries it needs to render
   * "Change Train" cards — at ALL 4 interchange stations, not just Modipuram.
   */
  function insertInterchangeSteps(raw, graph) {
    const result = [];
    for (let i = 0; i < raw.length; i++) {
      const step = raw[i];
      result.push(step);

      if (i < raw.length - 1) {
        const next = raw[i + 1];
        // If the edge between step and next is an interchange edge,
        // insert it explicitly (it may have been collapsed by Dijkstra skip-edges)
        if (step.line_id !== 'interchange' && next.line_id === 'interchange') {
          // already have it
        }
        // If next step uses a different system but we skipped the interchange node,
        // check if there's an interchange edge between them in the graph
        const stepSystem  = step.station_id.includes('_meerut_metro') ? 'metro' : 'rrts';
        const nextSystem  = next.station_id.includes('_meerut_metro') ? 'metro' : 'rrts';

        if (stepSystem !== nextSystem && next.line_id !== 'interchange') {
          // Find the interchange twin of current step
          const twin = step.station_id.endsWith('_rrts')
            ? step.station_id.replace('_rrts', '_meerut_metro')
            : step.station_id.replace('_meerut_metro', '_rrts');
          if (graph[twin]) {
            result.push({ station_id: twin, line_id: 'interchange' });
          }
        }
      }
    }
    return result;
  }

  /* ── Distance (real km, excluding interchange 0-distance hops) ─────────── */
  function calcDistance(path, graph) {
    let total = 0;
    for (let i = 0; i < path.length - 1; i++) {
      const from = path[i].station_id;
      const to   = path[i + 1].station_id;
      const edge = (graph[from] || []).find(e => e.neighbor === to);
      if (edge && edge.line_id !== 'interchange') total += edge.distance_km;
    }
    return Math.round(total * 10) / 10;
  }

  /* ── Real NCRTC fare table (Standard Coach, Feb 2026) ───────────────────── */
  const FARE = {
    'sarai_kale_khan__new_ashok_nagar':    30,
    'sarai_kale_khan__anand_vihar':        50,
    'sarai_kale_khan__sahibabad':          60,
    'sarai_kale_khan__ghaziabad':          80,
    'sarai_kale_khan__guldhar':            90,
    'sarai_kale_khan__duhai':             100,
    'sarai_kale_khan__murad_nagar':       120,
    'sarai_kale_khan__modi_nagar_south':  140,
    'sarai_kale_khan__modi_nagar_north':  140,
    'sarai_kale_khan__meerut_south_rrts': 160,
    'sarai_kale_khan__shatabdi_nagar_rrts':180,
    'sarai_kale_khan__begumpul_rrts':     200,
    'sarai_kale_khan__modipuram_rrts':    210,
    'new_ashok_nagar__anand_vihar':        30,
    'new_ashok_nagar__sahibabad':          50,
    'new_ashok_nagar__ghaziabad':          60,
    'new_ashok_nagar__guldhar':            70,
    'new_ashok_nagar__duhai':              80,
    'new_ashok_nagar__murad_nagar':       100,
    'new_ashok_nagar__modi_nagar_south':  120,
    'new_ashok_nagar__modi_nagar_north':  120,
    'new_ashok_nagar__meerut_south_rrts': 150,
    'new_ashok_nagar__shatabdi_nagar_rrts':160,
    'new_ashok_nagar__begumpul_rrts':     180,
    'new_ashok_nagar__modipuram_rrts':    190,
    'anand_vihar__sahibabad':              30,
    'anand_vihar__ghaziabad':              50,
    'anand_vihar__guldhar':                60,
    'anand_vihar__duhai':                  70,
    'anand_vihar__murad_nagar':            80,
    'anand_vihar__modi_nagar_south':      100,
    'anand_vihar__modi_nagar_north':      100,
    'anand_vihar__meerut_south_rrts':     130,
    'anand_vihar__shatabdi_nagar_rrts':   150,
    'anand_vihar__begumpul_rrts':         160,
    'anand_vihar__modipuram_rrts':        180,
    'sahibabad__ghaziabad':                30,
    'sahibabad__guldhar':                  40,
    'sahibabad__duhai':                    50,
    'sahibabad__murad_nagar':              70,
    'sahibabad__modi_nagar_south':         90,
    'sahibabad__modi_nagar_north':         90,
    'sahibabad__meerut_south_rrts':       110,
    'sahibabad__shatabdi_nagar_rrts':     130,
    'sahibabad__begumpul_rrts':           150,
    'sahibabad__modipuram_rrts':          160,
    'ghaziabad__guldhar':                  30,
    'ghaziabad__duhai':                    40,
    'ghaziabad__murad_nagar':              60,
    'ghaziabad__modi_nagar_south':         70,
    'ghaziabad__modi_nagar_north':         80,
    'ghaziabad__meerut_south_rrts':       100,
    'ghaziabad__shatabdi_nagar_rrts':     110,
    'ghaziabad__begumpul_rrts':           130,
    'ghaziabad__modipuram_rrts':          140,
    'guldhar__duhai':                      30,
    'guldhar__murad_nagar':                40,
    'guldhar__modi_nagar_south':           60,
    'guldhar__modi_nagar_north':           70,
    'guldhar__meerut_south_rrts':          90,
    'guldhar__shatabdi_nagar_rrts':       100,
    'guldhar__begumpul_rrts':             120,
    'guldhar__modipuram_rrts':            130,
    'duhai__murad_nagar':                  30,
    'duhai__modi_nagar_south':             50,
    'duhai__modi_nagar_north':             60,
    'duhai__meerut_south_rrts':            80,
    'duhai__shatabdi_nagar_rrts':          90,
    'duhai__begumpul_rrts':               110,
    'duhai__modipuram_rrts':              120,
    'murad_nagar__modi_nagar_south':       30,
    'murad_nagar__modi_nagar_north':       40,
    'murad_nagar__meerut_south_rrts':      60,
    'murad_nagar__shatabdi_nagar_rrts':    70,
    'murad_nagar__begumpul_rrts':          90,
    'murad_nagar__modipuram_rrts':        100,
    'modi_nagar_south__modi_nagar_north':  30,
    'modi_nagar_south__meerut_south_rrts': 50,
    'modi_nagar_south__shatabdi_nagar_rrts':60,
    'modi_nagar_south__begumpul_rrts':     80,
    'modi_nagar_south__modipuram_rrts':    90,
    'modi_nagar_north__meerut_south_rrts': 40,
    'modi_nagar_north__shatabdi_nagar_rrts':50,
    'modi_nagar_north__begumpul_rrts':     70,
    'modi_nagar_north__modipuram_rrts':    80,
    'meerut_south_rrts__shatabdi_nagar_rrts':30,
    'meerut_south_rrts__begumpul_rrts':    50,
    'meerut_south_rrts__modipuram_rrts':   60,
    'shatabdi_nagar_rrts__begumpul_rrts':  30,
    'shatabdi_nagar_rrts__modipuram_rrts': 40,
    'begumpul_rrts__modipuram_rrts':       30,
    // Meerut Metro fares
    'meerut_south_meerut_metro__partapur':    10,
    'meerut_south_meerut_metro__rithani':     20,
    'meerut_south_meerut_metro__shatabdi_nagar_meerut_metro':30,
    'meerut_south_meerut_metro__brahampuri':  30,
    'meerut_south_meerut_metro__meerut_central':40,
    'meerut_south_meerut_metro__bhaisali_bus_adda':40,
    'meerut_south_meerut_metro__begumpul_meerut_metro':50,
    'meerut_south_meerut_metro__mes_colony':  50,
    'meerut_south_meerut_metro__daurli':      60,
    'meerut_south_meerut_metro__meerut_north':60,
    'meerut_south_meerut_metro__modipuram_meerut_metro':60,
    'partapur__rithani':                      10,
    'partapur__shatabdi_nagar_meerut_metro':  20,
    'partapur__brahampuri':                   20,
    'partapur__meerut_central':               30,
    'partapur__bhaisali_bus_adda':            30,
    'partapur__begumpul_meerut_metro':        40,
    'partapur__mes_colony':                   40,
    'partapur__daurli':                       50,
    'partapur__meerut_north':                 50,
    'partapur__modipuram_meerut_metro':       60,
    'rithani__shatabdi_nagar_meerut_metro':   10,
    'rithani__brahampuri':                    20,
    'rithani__meerut_central':                20,
    'rithani__bhaisali_bus_adda':             30,
    'rithani__begumpul_meerut_metro':         30,
    'rithani__mes_colony':                    40,
    'rithani__daurli':                        50,
    'rithani__meerut_north':                  50,
    'rithani__modipuram_meerut_metro':        60,
    'shatabdi_nagar_meerut_metro__brahampuri':10,
    'shatabdi_nagar_meerut_metro__meerut_central':20,
    'shatabdi_nagar_meerut_metro__bhaisali_bus_adda':30,
    'shatabdi_nagar_meerut_metro__begumpul_meerut_metro':30,
    'shatabdi_nagar_meerut_metro__mes_colony':40,
    'shatabdi_nagar_meerut_metro__daurli':    40,
    'shatabdi_nagar_meerut_metro__meerut_north':50,
    'shatabdi_nagar_meerut_metro__modipuram_meerut_metro':60,
    'brahampuri__meerut_central':             10,
    'brahampuri__bhaisali_bus_adda':          20,
    'brahampuri__begumpul_meerut_metro':      20,
    'brahampuri__mes_colony':                 30,
    'brahampuri__daurli':                     40,
    'brahampuri__meerut_north':               40,
    'brahampuri__modipuram_meerut_metro':     50,
    'meerut_central__bhaisali_bus_adda':      10,
    'meerut_central__begumpul_meerut_metro':  20,
    'meerut_central__mes_colony':             30,
    'meerut_central__daurli':                 40,
    'meerut_central__meerut_north':           40,
    'meerut_central__modipuram_meerut_metro': 50,
    'bhaisali_bus_adda__begumpul_meerut_metro':10,
    'bhaisali_bus_adda__mes_colony':          20,
    'bhaisali_bus_adda__daurli':              30,
    'bhaisali_bus_adda__meerut_north':        30,
    'bhaisali_bus_adda__modipuram_meerut_metro':40,
    'begumpul_meerut_metro__mes_colony':      10,
    'begumpul_meerut_metro__daurli':          20,
    'begumpul_meerut_metro__meerut_north':    30,
    'begumpul_meerut_metro__modipuram_meerut_metro':30,
    'mes_colony__daurli':                     10,
    'mes_colony__meerut_north':               20,
    'mes_colony__modipuram_meerut_metro':     30,
    'daurli__meerut_north':                   10,
    'daurli__modipuram_meerut_metro':         20,
    'meerut_north__modipuram_meerut_metro':   10,
  };

  function lookupFare(a, b) {
    const key = [a, b].sort().join('__');
    if (FARE[key] !== undefined) return FARE[key];
    // Try normalising interchange twins
    const norm = id => id.replace(/_rrts$/, '').replace(/_meerut_metro$/, '');
    const k2 = [norm(a), norm(b)].sort().join('__');
    return FARE[k2] ?? null;
  }

  function calcFare(path) {
    const src = path[0].station_id;
    const dst = path[path.length - 1].station_id;
    const direct = lookupFare(src, dst);
    if (direct !== null) return direct;
    // Fallback: sum consecutive segment fares
    let total = 0;
    for (let i = 0; i < path.length - 1; i++) {
      if (path[i].line_id !== 'interchange' && path[i+1].line_id !== 'interchange') {
        total += lookupFare(path[i].station_id, path[i+1].station_id) || 0;
      }
    }
    return total || 30;
  }

  function calcTime(distance, nInterchanges) {
    return Math.ceil(distance * 0.72 + 5) + (nInterchanges * 4);
  }

  return { findRoute, calcDistance, calcFare, calcTime };
})();
