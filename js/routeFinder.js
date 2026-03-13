/**
 * routeFinder.js — Dijkstra + clean interchange detection
 *
 * THREE BUGS FIXED:
 *
 * BUG 1 — Double interchange card:
 *   Old code inserted interchange nodes via post-processing AND the raw Dijkstra
 *   path already contained them → duplicate. Fix: never post-process. Instead,
 *   after path reconstruction, make one clean scan to find the single crossing
 *   point and normalise it.
 *
 * BUG 2 — No interchange shown for destinations like Meerut North:
 *   The interchange node in the raw path had station_id = modipuram_meerut_metro
 *   (the metro twin) but routeUI was looking up the RRTS id. Fix: always
 *   normalise interchange steps to use the RRTS station_id so ixMap lookup works.
 *
 * BUG 3 — Wrong routing (e.g. Modipuram→New Ashok Nagar via Metro):
 *   Interchange penalty was only 0.01 km, cheaper than staying on RRTS for short
 *   hops. Fix: penalty is now 100 km in graphBuilder — Dijkstra never crosses
 *   systems unless the destination is genuinely on the other system.
 */
const RouteFinder = (() => {

  /* ── MinHeap (priority queue for Dijkstra) ─────────────────────────────── */
  class MinHeap {
    constructor() { this.h = []; }
    push(item) { this.h.push(item); this._up(this.h.length - 1); }
    pop() {
      const top = this.h[0], last = this.h.pop();
      if (this.h.length) { this.h[0] = last; this._down(0); }
      return top;
    }
    get size() { return this.h.length; }
    _up(i) {
      while (i > 0) {
        const p = (i - 1) >> 1;
        if (this.h[p].w <= this.h[i].w) break;
        [this.h[p], this.h[i]] = [this.h[i], this.h[p]]; i = p;
      }
    }
    _down(i) {
      const n = this.h.length;
      while (true) {
        let s = i, l = 2*i+1, r = 2*i+2;
        if (l < n && this.h[l].w < this.h[s].w) s = l;
        if (r < n && this.h[r].w < this.h[s].w) s = r;
        if (s === i) break;
        [this.h[s], this.h[i]] = [this.h[i], this.h[s]]; i = s;
      }
    }
  }

  /* ── Helpers ─────────────────────────────────────────────────────────────── */
  const isMetro = id => id.includes('_meerut_metro');
  const isRRTS  = id => !isMetro(id);
  // Get the RRTS-side station_id for any interchange node
  const rrtsId  = id => isMetro(id) ? id.replace('_meerut_metro', '_rrts') : id;

  /* ── Dijkstra ─────────────────────────────────────────────────────────────
     Returns raw path: array of { station_id, line_id } where line_id is the
     edge used to ARRIVE at that node (null for origin).
  ────────────────────────────────────────────────────────────────────────── */
  function dijkstra(graph, src, dst) {
    if (!graph[src] || !graph[dst]) return null;
    if (src === dst) return [{ station_id: src, line_id: null }];

    const dist = {}, prev = {};
    dist[src] = 0;
    const heap = new MinHeap();
    heap.push({ w: 0, id: src });

    while (heap.size) {
      const { w, id } = heap.pop();
      if (w > dist[id]) continue;
      if (id === dst) break;
      for (const edge of (graph[id] || [])) {
        const nd = w + edge.weight;
        if (dist[edge.neighbor] === undefined || nd < dist[edge.neighbor]) {
          dist[edge.neighbor] = nd;
          prev[edge.neighbor] = { from: id, line_id: edge.line_id };
          heap.push({ w: nd, id: edge.neighbor });
        }
      }
    }

    if (dist[dst] === undefined) return null;

    // Reconstruct
    const path = [];
    let cur = dst;
    while (cur !== undefined) {
      const p = prev[cur];
      path.unshift({ station_id: cur, line_id: p ? p.line_id : null });
      cur = p ? p.from : undefined;
    }
    return path;
  }

  /* ── Path cleaning ───────────────────────────────────────────────────────
     Takes the raw Dijkstra path and produces a clean display path:
     1. Collapse any duplicate consecutive stations (can happen with skip-edges)
     2. Find the single system-crossing point (if any)
     3. Replace it with ONE clean interchange step using the RRTS station_id
        so routeUI can look it up in interchanges.json
     4. Strip out any redundant _rrts / _meerut_metro twin nodes that appear
        consecutively (Dijkstra may route through both sides of an interchange)
  ────────────────────────────────────────────────────────────────────────── */
  function cleanPath(raw) {
    if (!raw || raw.length === 0) return raw;

    // Step 1: Remove duplicate consecutive stations
    const deduped = [raw[0]];
    for (let i = 1; i < raw.length; i++) {
      if (raw[i].station_id !== deduped[deduped.length - 1].station_id) {
        deduped.push(raw[i]);
      }
    }

    // Step 2: Find and collapse interchange crossings
    // An interchange crossing is: a node with line_id='interchange'
    // OR two consecutive nodes that are twins of each other (both sides of interchange)
    const result = [];
    let i = 0;
    while (i < deduped.length) {
      const step = deduped[i];

      // Detect: current step is an interchange edge node
      if (step.line_id === 'interchange') {
        // Use the RRTS-side id for lookup, keep line_id='interchange'
        const rid = rrtsId(step.station_id);
        // Avoid duplicate interchange steps
        if (result.length === 0 || result[result.length - 1].line_id !== 'interchange') {
          result.push({ station_id: rid, line_id: 'interchange' });
        }
        i++; continue;
      }

      // Detect: two consecutive nodes are RRTS+Metro twins of the same station
      // e.g. shatabdi_nagar_rrts → shatabdi_nagar_meerut_metro
      if (i + 1 < deduped.length) {
        const next = deduped[i + 1];
        const curBase  = step.station_id.replace(/_rrts$/, '').replace(/_meerut_metro$/, '');
        const nextBase = next.station_id.replace(/_rrts$/, '').replace(/_meerut_metro$/, '');
        if (curBase === nextBase && curBase !== step.station_id) {
          // This is an implicit interchange crossing — emit one interchange step
          const rid = isRRTS(step.station_id) ? step.station_id : rrtsId(step.station_id);
          if (result.length === 0 || result[result.length - 1].line_id !== 'interchange') {
            result.push({ station_id: rid, line_id: 'interchange' });
          }
          i += 2; continue;
        }
      }

      result.push(step);
      i++;
    }

    return result;
  }

  /* ── Public findRoute ────────────────────────────────────────────────────── */
  function findRoute(graph, src, dst) {
    const raw = dijkstra(graph, src, dst);
    if (!raw) return null;
    return cleanPath(raw);
  }

  /* ── Distance (km, ignoring interchange edges) ──────────────────────────── */
  function calcDistance(path, graph) {
    let total = 0;
    for (let i = 0; i < path.length - 1; i++) {
      const from = path[i].station_id, to = path[i + 1].station_id;
      // For interchange steps, the station_id is RRTS-side; look for both twins
      const fromEdges = graph[from] || graph[from.replace(/_rrts$/, '_meerut_metro')] || [];
      const edge = fromEdges.find(e =>
        e.neighbor === to ||
        e.neighbor === to.replace(/_rrts$/, '_meerut_metro') ||
        e.neighbor === to.replace(/_meerut_metro$/, '_rrts')
      );
      if (edge && edge.line_id !== 'interchange') total += edge.distance_km;
    }
    return Math.round(total * 10) / 10;
  }

  /* ── Fare table (NCRTC official, Standard Coach, Feb 2026) ─────────────── */
  const FARE = {
    // ── RRTS fares — verified from meerutmetro.in (NCRTC official source, Feb 2026) ──
    'sarai_kale_khan__new_ashok_nagar':          30,
    'sarai_kale_khan__anand_vihar':              50,
    'sarai_kale_khan__sahibabad':                60,
    'sarai_kale_khan__ghaziabad':                80,
    'sarai_kale_khan__guldhar':                  90,
    'sarai_kale_khan__duhai':                   100,
    'sarai_kale_khan__murad_nagar':             120,
    'sarai_kale_khan__modi_nagar_south':        140,
    'sarai_kale_khan__modi_nagar_north':        140,
    'sarai_kale_khan__meerut_south_rrts':       160,
    'sarai_kale_khan__shatabdi_nagar_rrts':     180,
    'sarai_kale_khan__begumpul_rrts':           200,
    'sarai_kale_khan__modipuram_rrts':          210,
    'new_ashok_nagar__anand_vihar':              20,
    'new_ashok_nagar__sahibabad':                50,
    'new_ashok_nagar__ghaziabad':                60,
    'new_ashok_nagar__guldhar':                  70,
    'new_ashok_nagar__duhai':                    80,
    'new_ashok_nagar__murad_nagar':             100,
    'new_ashok_nagar__modi_nagar_south':        120,
    'new_ashok_nagar__modi_nagar_north':        130,
    'new_ashok_nagar__meerut_south_rrts':       150,
    'new_ashok_nagar__shatabdi_nagar_rrts':     160,
    'new_ashok_nagar__begumpul_rrts':           180,
    'new_ashok_nagar__modipuram_rrts':          200,
    'anand_vihar__sahibabad':                    20,
    'anand_vihar__ghaziabad':                    30,
    'anand_vihar__guldhar':                      40,
    'anand_vihar__duhai':                        50,
    'anand_vihar__murad_nagar':                  70,
    'anand_vihar__modi_nagar_south':             90,
    'anand_vihar__modi_nagar_north':             90,
    'anand_vihar__meerut_south_rrts':           110,
    'anand_vihar__shatabdi_nagar_rrts':         130,
    'anand_vihar__begumpul_rrts':               150,
    'anand_vihar__modipuram_rrts':              160,
    'sahibabad__ghaziabad':                      20,
    'sahibabad__guldhar':                        30,
    'sahibabad__duhai':                          40,
    'sahibabad__murad_nagar':                    60,
    'sahibabad__modi_nagar_south':               80,
    'sahibabad__modi_nagar_north':               80,
    'sahibabad__meerut_south_rrts':             100,
    'sahibabad__shatabdi_nagar_rrts':           120,
    'sahibabad__begumpul_rrts':                 140,
    'sahibabad__modipuram_rrts':                150,
    'ghaziabad__guldhar':                        20,
    'ghaziabad__duhai':                          20,
    'ghaziabad__murad_nagar':                    40,
    'ghaziabad__modi_nagar_south':               60,
    'ghaziabad__modi_nagar_north':               60,
    'ghaziabad__meerut_south_rrts':              80,
    'ghaziabad__shatabdi_nagar_rrts':           100,
    'ghaziabad__begumpul_rrts':                 120,
    'ghaziabad__modipuram_rrts':                130,
    'guldhar__duhai':                            20,
    'guldhar__murad_nagar':                      30,
    'guldhar__modi_nagar_south':                 50,
    'guldhar__modi_nagar_north':                 50,
    'guldhar__meerut_south_rrts':                70,
    'guldhar__shatabdi_nagar_rrts':              90,
    'guldhar__begumpul_rrts':                   110,
    'guldhar__modipuram_rrts':                  120,
    'duhai__murad_nagar':                        20,
    'duhai__modi_nagar_south':                   40,
    'duhai__modi_nagar_north':                   40,
    'duhai__meerut_south_rrts':                  60,
    'duhai__shatabdi_nagar_rrts':                80,
    'duhai__begumpul_rrts':                     100,
    'duhai__modipuram_rrts':                    110,
    'murad_nagar__modi_nagar_south':             20,
    'murad_nagar__modi_nagar_north':             20,
    'murad_nagar__meerut_south_rrts':            40,
    'murad_nagar__shatabdi_nagar_rrts':          60,
    'murad_nagar__begumpul_rrts':                80,
    'murad_nagar__modipuram_rrts':               90,
    'modi_nagar_south__modi_nagar_north':        20,
    'modi_nagar_south__meerut_south_rrts':       20,
    'modi_nagar_south__shatabdi_nagar_rrts':     40,
    'modi_nagar_south__begumpul_rrts':           60,
    'modi_nagar_south__modipuram_rrts':          70,
    'modi_nagar_north__meerut_south_rrts':       20,
    'modi_nagar_north__shatabdi_nagar_rrts':     40,
    'modi_nagar_north__begumpul_rrts':           60,
    'modi_nagar_north__modipuram_rrts':          70,
    'meerut_south_rrts__shatabdi_nagar_rrts':    20,
    'meerut_south_rrts__begumpul_rrts':          40,
    'meerut_south_rrts__modipuram_rrts':         50,
    'shatabdi_nagar_rrts__begumpul_rrts':        20,
    'shatabdi_nagar_rrts__modipuram_rrts':       30,
    'begumpul_rrts__modipuram_rrts':             20,
    // ── Meerut Metro fares (official NCRTC data) ─────────────────────────────
    'meerut_south_meerut_metro__partapur':                   20,
    'meerut_south_meerut_metro__rithani':                    20,
    'meerut_south_meerut_metro__shatabdi_nagar_meerut_metro':30,
    'meerut_south_meerut_metro__brahampuri':                 30,
    'meerut_south_meerut_metro__meerut_central':             30,
    'meerut_south_meerut_metro__bhaisali_bus_adda':          40,
    'meerut_south_meerut_metro__begumpul_meerut_metro':      40,
    'meerut_south_meerut_metro__mes_colony':                 50,
    'meerut_south_meerut_metro__daurli':                     50,
    'meerut_south_meerut_metro__meerut_north':               60,
    'meerut_south_meerut_metro__modipuram_meerut_metro':     60,
    'partapur__rithani':                                     20,
    'partapur__shatabdi_nagar_meerut_metro':                 20,
    'partapur__brahampuri':                                  20,
    'partapur__meerut_central':                              20,
    'partapur__bhaisali_bus_adda':                           30,
    'partapur__begumpul_meerut_metro':                       30,
    'partapur__mes_colony':                                  40,
    'partapur__daurli':                                      40,
    'partapur__meerut_north':                                50,
    'partapur__modipuram_meerut_metro':                      60,
    'rithani__shatabdi_nagar_meerut_metro':                  20,
    'rithani__brahampuri':                                   20,
    'rithani__meerut_central':                               20,
    'rithani__bhaisali_bus_adda':                            30,
    'rithani__begumpul_meerut_metro':                        30,
    'rithani__mes_colony':                                   40,
    'rithani__daurli':                                       40,
    'rithani__meerut_north':                                 50,
    'rithani__modipuram_meerut_metro':                       50,
    'shatabdi_nagar_meerut_metro__brahampuri':               20,
    'shatabdi_nagar_meerut_metro__meerut_central':           20,
    'shatabdi_nagar_meerut_metro__bhaisali_bus_adda':        20,
    'shatabdi_nagar_meerut_metro__begumpul_meerut_metro':    20,
    'shatabdi_nagar_meerut_metro__mes_colony':               30,
    'shatabdi_nagar_meerut_metro__daurli':                   30,
    'shatabdi_nagar_meerut_metro__meerut_north':             40,
    'shatabdi_nagar_meerut_metro__modipuram_meerut_metro':   50,
    'brahampuri__meerut_central':                            20,
    'brahampuri__bhaisali_bus_adda':                         20,
    'brahampuri__begumpul_meerut_metro':                     20,
    'brahampuri__mes_colony':                                30,
    'brahampuri__daurli':                                    30,
    'brahampuri__meerut_north':                              40,
    'brahampuri__modipuram_meerut_metro':                    50,
    'meerut_central__bhaisali_bus_adda':                     20,
    'meerut_central__begumpul_meerut_metro':                 20,
    'meerut_central__mes_colony':                            30,
    'meerut_central__daurli':                                30,
    'meerut_central__meerut_north':                          40,
    'meerut_central__modipuram_meerut_metro':                50,
    'bhaisali_bus_adda__begumpul_meerut_metro':              20,
    'bhaisali_bus_adda__mes_colony':                         20,
    'bhaisali_bus_adda__daurli':                             30,
    'bhaisali_bus_adda__meerut_north':                       30,
    'bhaisali_bus_adda__modipuram_meerut_metro':             40,
    'begumpul_meerut_metro__mes_colony':                     20,
    'begumpul_meerut_metro__daurli':                         20,
    'begumpul_meerut_metro__meerut_north':                   30,
    'begumpul_meerut_metro__modipuram_meerut_metro':         30,
    'mes_colony__daurli':                                    20,
    'mes_colony__meerut_north':                              20,
    'mes_colony__modipuram_meerut_metro':                    30,
    'daurli__meerut_north':                                  20,
    'daurli__modipuram_meerut_metro':                        20,
    'meerut_north__modipuram_meerut_metro':                  20,
  };

  function normId(id) {
    return id.replace(/_rrts$/, '').replace(/_meerut_metro$/, '');
  }

  function lookupFare(a, b) {
    // FARE table keys use "earlier station first" ordering along the physical line,
    // which is NOT alphabetical. Try both orderings (a__b and b__a) and both
    // normalised forms (stripping _rrts / _meerut_metro suffixes).
    const na = normId(a), nb = normId(b);
    if (FARE[a + '__' + b]   !== undefined) return FARE[a + '__' + b];
    if (FARE[b + '__' + a]   !== undefined) return FARE[b + '__' + a];
    if (FARE[na + '__' + nb] !== undefined) return FARE[na + '__' + nb];
    if (FARE[nb + '__' + na] !== undefined) return FARE[nb + '__' + na];
    return null;
  }

  function calcFare(path) {
    const src = path[0].station_id;
    const dst = path[path.length - 1].station_id;

    // Same-system routes: direct point-to-point lookup covers everything
    const direct = lookupFare(src, dst);
    if (direct !== null) return direct;

    // Cross-system route: find the interchange and sum each system's fare.
    // cleanPath() guarantees at most one interchange step per route (RRTS-side ID).
    const ixIdx = path.findIndex(p => p.line_id === 'interchange');
    if (ixIdx !== -1) {
      const ixRrts  = path[ixIdx].station_id;                          // RRTS-side ID
      const ixMetro = ixRrts.replace(/_rrts$/, '_meerut_metro');       // Metro-side ID

      // Fare from src to the interchange station (try both side IDs)
      let f1 = lookupFare(src, ixRrts);
      if (f1 === null) f1 = lookupFare(src, ixMetro);

      // Fare from the interchange station to dst (try both side IDs)
      let f2 = lookupFare(ixRrts, dst);
      if (f2 === null) f2 = lookupFare(ixMetro, dst);

      if (f1 !== null && f2 !== null) return f1 + f2;
    }

    return 20; // absolute fallback
  }

  function calcTime(distance, nInterchanges) {
    return Math.ceil(distance * 0.72 + 5) + (nInterchanges * 4);
  }

  return { findRoute, calcDistance, calcFare, calcTime };
})();
