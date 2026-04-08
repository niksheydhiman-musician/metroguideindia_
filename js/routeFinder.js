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
  // Any station whose ID ends with _metro belongs to a metro system.
  // This pattern supports _meerut_metro, _delhi_metro, _lucknow_metro, etc.
  const isMetro = id => id.endsWith('_metro');
  const isRRTS  = id => !isMetro(id);
  // Get the RRTS-side station_id for a metro interchange node
  const rrtsId  = id => isMetro(id) ? id.replace(/_[a-z0-9]+_metro$/, '_rrts') : id;

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
        const curBase  = step.station_id.replace(/_rrts$/, '').replace(/_[a-z0-9]+_metro$/, '');
        const nextBase = next.station_id.replace(/_rrts$/, '').replace(/_[a-z0-9]+_metro$/, '');
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
        e.neighbor === to.replace(/_[a-z0-9]+_metro$/, '_rrts')
      );
      if (edge && edge.line_id !== 'interchange') total += edge.distance_km;
    }
    return Math.round(total * 10) / 10;
  }

/* ── Fare table (NCRTC official, Standard Coach, March 2026) ─────────────── */
  const FARE = {
    // ── RRTS fares — verified from Official NCRTC Fare Matrix ──
    'sarai_kale_khan__new_ashok_nagar':         30,
    'sarai_kale_khan__anand_vihar':             50,
    'sarai_kale_khan__sahibabad':               60,
    'sarai_kale_khan__ghaziabad':               80,
    'sarai_kale_khan__guldhar':                 90,
    'sarai_kale_khan__duhai':                  100,
    'sarai_kale_khan__murad_nagar':            120,
    'sarai_kale_khan__modi_nagar_south':       140,
    'sarai_kale_khan__modi_nagar_north':       140,
    'sarai_kale_khan__meerut_south_rrts':      160,
    'sarai_kale_khan__shatabdi_nagar_rrts':    180,
    'sarai_kale_khan__begumpul_rrts':          200,
    'sarai_kale_khan__modipuram_rrts':         210,

    'new_ashok_nagar__anand_vihar':             30,
    'new_ashok_nagar__sahibabad':               50,
    'new_ashok_nagar__ghaziabad':               60,
    'new_ashok_nagar__guldhar':                 70,
    'new_ashok_nagar__duhai':                   80,
    'new_ashok_nagar__murad_nagar':            100,
    'new_ashok_nagar__modi_nagar_south':       120,
    'new_ashok_nagar__modi_nagar_north':       130,
    'new_ashok_nagar__meerut_south_rrts':      150,
    'new_ashok_nagar__shatabdi_nagar_rrts':    160,
    'new_ashok_nagar__begumpul_rrts':          180,
    'new_ashok_nagar__modipuram_rrts':         200,

    'anand_vihar__sahibabad':                   30,
    'anand_vihar__ghaziabad':                   40,
    'anand_vihar__guldhar':                     50,
    'anand_vihar__duhai':                       60,
    'anand_vihar__murad_nagar':                 80,
    'anand_vihar__modi_nagar_south':           100,
    'anand_vihar__modi_nagar_north':           100,
    'anand_vihar__meerut_south_rrts':          130,
    'anand_vihar__shatabdi_nagar_rrts':        140,
    'anand_vihar__begumpul_rrts':              160,
    'anand_vihar__modipuram_rrts':             180,

    'sahibabad__ghaziabad':                     30,
    'sahibabad__guldhar':                       30,
    'sahibabad__duhai':                         40,
    'sahibabad__murad_nagar':                   60,
    'sahibabad__modi_nagar_south':              80,
    'sahibabad__modi_nagar_north':              90,
    'sahibabad__meerut_south_rrts':            110,
    'sahibabad__shatabdi_nagar_rrts':          130,
    'sahibabad__begumpul_rrts':                140,
    'sahibabad__modipuram_rrts':               160,

    'ghaziabad__guldhar':                       20,
    'ghaziabad__duhai':                         30,
    'ghaziabad__murad_nagar':                   40,
    'ghaziabad__modi_nagar_south':              60,
    'ghaziabad__modi_nagar_north':              80,
    'ghaziabad__meerut_south_rrts':             90,
    'ghaziabad__shatabdi_nagar_rrts':          110,
    'ghaziabad__begumpul_rrts':                120,
    'ghaziabad__modipuram_rrts':               140,

    'guldhar__duhai':                           20,
    'guldhar__murad_nagar':                     30,
    'guldhar__modi_nagar_south':                50,
    'guldhar__modi_nagar_north':                60,
    'guldhar__meerut_south_rrts':               80,
    'guldhar__shatabdi_nagar_rrts':            100,
    'guldhar__begumpul_rrts':                  120,
    'guldhar__modipuram_rrts':                 130,

    'duhai__murad_nagar':                       20,
    'duhai__modi_nagar_south':                  40,
    'duhai__modi_nagar_north':                  50,
    'duhai__meerut_south_rrts':                 70,
    'duhai__shatabdi_nagar_rrts':               90,
    'duhai__begumpul_rrts':                    100,
    'duhai__modipuram_rrts':                   120,

    'murad_nagar__modi_nagar_south':            20,
    'murad_nagar__modi_nagar_north':            30,
    'murad_nagar__meerut_south_rrts':           60,
    'murad_nagar__shatabdi_nagar_rrts':         70,
    'murad_nagar__begumpul_rrts':               90,
    'murad_nagar__modipuram_rrts':             110,

    'modi_nagar_south__modi_nagar_north':       20,
    'modi_nagar_south__meerut_south_rrts':      40,
    'modi_nagar_south__shatabdi_nagar_rrts':    60,
    'modi_nagar_south__begumpul_rrts':          70,
    'modi_nagar_south__modipuram_rrts':         90,

    'modi_nagar_north__meerut_south_rrts':      30,
    'modi_nagar_north__shatabdi_nagar_rrts':    50,
    'modi_nagar_north__begumpul_rrts':          60,
    'modi_nagar_north__modipuram_rrts':         80,

    'meerut_south_rrts__shatabdi_nagar_rrts':   20,
    'meerut_south_rrts__begumpul_rrts':         40,
    'meerut_south_rrts__modipuram_rrts':        60,

    'shatabdi_nagar_rrts__begumpul_rrts':       20,
    'shatabdi_nagar_rrts__modipuram_rrts':      30,
    'begumpul_rrts__modipuram_rrts':            20,

    // ── Meerut Metro fares — complete matrix, all station pairs ──
    // Fare slab: 1–2 stops = ₹20, 3–5 stops = ₹30, 6–7 stops = ₹40,
    //            8–9 stops = ₹50, 10+ stops = ₹60
    // Stations in order:
    //   1=meerut_south  2=partapur  3=rithani  4=shatabdi_nagar
    //   5=brahampuri  6=meerut_central  7=bhaisali_bus_adda  8=begumpul
    //   9=mes_colony  10=daurli  11=meerut_north  12=modipuram

    'meerut_south_meerut_metro__partapur_meerut_metro':                    20,
    'meerut_south_meerut_metro__rithani_meerut_metro':                     20,
    'meerut_south_meerut_metro__shatabdi_nagar_meerut_metro':              30,
    'meerut_south_meerut_metro__brahampuri_meerut_metro':                  30,
    'meerut_south_meerut_metro__meerut_central_meerut_metro':              30,
    'meerut_south_meerut_metro__bhaisali_bus_adda_meerut_metro':           40,
    'meerut_south_meerut_metro__begumpul_meerut_metro':                    40,
    'meerut_south_meerut_metro__mes_colony_meerut_metro':                  50,
    'meerut_south_meerut_metro__daurli_meerut_metro':                      50,
    'meerut_south_meerut_metro__meerut_north_meerut_metro':                60,
    'meerut_south_meerut_metro__modipuram_meerut_metro':                   60,

    'partapur_meerut_metro__rithani_meerut_metro':                         20,
    'partapur_meerut_metro__shatabdi_nagar_meerut_metro':                  20,
    'partapur_meerut_metro__brahampuri_meerut_metro':                      30,
    'partapur_meerut_metro__meerut_central_meerut_metro':                  30,
    'partapur_meerut_metro__bhaisali_bus_adda_meerut_metro':               30,
    'partapur_meerut_metro__begumpul_meerut_metro':                        40,
    'partapur_meerut_metro__mes_colony_meerut_metro':                      40,
    'partapur_meerut_metro__daurli_meerut_metro':                          50,
    'partapur_meerut_metro__meerut_north_meerut_metro':                    50,
    'partapur_meerut_metro__modipuram_meerut_metro':                       60,

    'rithani_meerut_metro__shatabdi_nagar_meerut_metro':                   20,
    'rithani_meerut_metro__brahampuri_meerut_metro':                       20,
    'rithani_meerut_metro__meerut_central_meerut_metro':                   30,
    'rithani_meerut_metro__bhaisali_bus_adda_meerut_metro':                30,
    'rithani_meerut_metro__begumpul_meerut_metro':                         30,
    'rithani_meerut_metro__mes_colony_meerut_metro':                       40,
    'rithani_meerut_metro__daurli_meerut_metro':                           40,
    'rithani_meerut_metro__meerut_north_meerut_metro':                     50,
    'rithani_meerut_metro__modipuram_meerut_metro':                        50,

    'shatabdi_nagar_meerut_metro__brahampuri_meerut_metro':                20,
    'shatabdi_nagar_meerut_metro__meerut_central_meerut_metro':            20,
    'shatabdi_nagar_meerut_metro__bhaisali_bus_adda_meerut_metro':         30,
    'shatabdi_nagar_meerut_metro__begumpul_meerut_metro':                  30,
    'shatabdi_nagar_meerut_metro__mes_colony_meerut_metro':                30,
    'shatabdi_nagar_meerut_metro__daurli_meerut_metro':                    40,
    'shatabdi_nagar_meerut_metro__meerut_north_meerut_metro':              40,
    'shatabdi_nagar_meerut_metro__modipuram_meerut_metro':                 50,

    'brahampuri_meerut_metro__meerut_central_meerut_metro':                20,
    'brahampuri_meerut_metro__bhaisali_bus_adda_meerut_metro':             20,
    'brahampuri_meerut_metro__begumpul_meerut_metro':                      30,
    'brahampuri_meerut_metro__mes_colony_meerut_metro':                    30,
    'brahampuri_meerut_metro__daurli_meerut_metro':                        30,
    'brahampuri_meerut_metro__meerut_north_meerut_metro':                  40,
    'brahampuri_meerut_metro__modipuram_meerut_metro':                     40,

    'meerut_central_meerut_metro__bhaisali_bus_adda_meerut_metro':         20,
    'meerut_central_meerut_metro__begumpul_meerut_metro':                  20,
    'meerut_central_meerut_metro__mes_colony_meerut_metro':                30,
    'meerut_central_meerut_metro__daurli_meerut_metro':                    30,
    'meerut_central_meerut_metro__meerut_north_meerut_metro':              30,
    'meerut_central_meerut_metro__modipuram_meerut_metro':                 40,

    'bhaisali_bus_adda_meerut_metro__begumpul_meerut_metro':               20,
    'bhaisali_bus_adda_meerut_metro__mes_colony_meerut_metro':             20,
    'bhaisali_bus_adda_meerut_metro__daurli_meerut_metro':                 30,
    'bhaisali_bus_adda_meerut_metro__meerut_north_meerut_metro':           30,
    'bhaisali_bus_adda_meerut_metro__modipuram_meerut_metro':              30,

    'begumpul_meerut_metro__mes_colony_meerut_metro':                      20,
    'begumpul_meerut_metro__daurli_meerut_metro':                          20,
    'begumpul_meerut_metro__meerut_north_meerut_metro':                    30,
    'begumpul_meerut_metro__modipuram_meerut_metro':                       30,

    'mes_colony_meerut_metro__daurli_meerut_metro':                        20,
    'mes_colony_meerut_metro__meerut_north_meerut_metro':                  20,
    'mes_colony_meerut_metro__modipuram_meerut_metro':                     30,

    'daurli_meerut_metro__meerut_north_meerut_metro':                      20,
    'daurli_meerut_metro__modipuram_meerut_metro':                         20,

    'meerut_north_meerut_metro__modipuram_meerut_metro':                   20,
  };

  /* ── Fare lookup — direction-independent ─────────────────────────────────── */
  function lookupFare(a, b) {
    if (FARE[`${a}__${b}`] !== undefined) return FARE[`${a}__${b}`];
    if (FARE[`${b}__${a}`] !== undefined) return FARE[`${b}__${a}`];
    return null;
  }

  // 2026 metro distance slabs (standard fare)
  const METRO_2026_SLABS = {
    delhi: [
      { maxKm: 2,  fare: 11 },
      { maxKm: 5,  fare: 21 },
      { maxKm: 12, fare: 32 },
      { maxKm: 21, fare: 42 },
      { maxKm: 32, fare: 52 },
      { maxKm: Infinity, fare: 64 },
    ],
    bengaluru: [
      { maxKm: 2,  fare: 10 },
      { maxKm: 5,  fare: 20 },
      { maxKm: 12, fare: 30 },
      { maxKm: 21, fare: 40 },
      { maxKm: 32, fare: 50 },
      { maxKm: Infinity, fare: 60 },
    ],
  };

  function fareFromDistanceSlab(distance, cityKey) {
    const slabs = METRO_2026_SLABS[cityKey];
    if (!slabs || !Number.isFinite(distance)) return null;
    const safeDistance = Math.max(0, Number(distance));
    const slab = slabs.find(s => safeDistance <= s.maxKm);
    return slab ? slab.fare : null;
  }

  /* ── Fare calculation ────────────────────────────────────────────────────── */
  function calcFare(path, options = {}) {
    if (!path || path.length < 2) return 20;
    const cityKey = String(options.cityKey || 'rrts').toLowerCase();
    const slabFare = fareFromDistanceSlab(options.distance, cityKey);
    if (slabFare !== null) return slabFare;

    const src = path[0].station_id;
    const dst = path[path.length - 1].station_id;

    // 1) Try direct fare (handles RRTS-only, Metro-only, and cross-system when in table)
    const direct = lookupFare(src, dst);
    if (direct !== null) return direct;

    // 2) Find the first system boundary in the path
    let boundaryIndex = -1;
    for (let i = 1; i < path.length; i++) {
      if (isMetro(path[i - 1].station_id) !== isMetro(path[i].station_id)) {
        boundaryIndex = i;
        break;
      }
    }

    if (boundaryIndex === -1) return 20; // no system change, no direct fare

    const left  = path[boundaryIndex - 1].station_id;
    const right = path[boundaryIndex].station_id;

    // The RRTS-side boundary node is whichever of left/right is NOT metro.
    // For RRTS→Metro: left is the RRTS interchange node, right is first metro station.
    // For Metro→RRTS: left is last metro station, right is the RRTS interchange node.
    const ixRRTS  = isMetro(left) ? right : left;
    const ixMetro = ixRRTS.replace(/_rrts$/, '_meerut_metro');

    const srcIsMetro = isMetro(src);
    const dstIsMetro = isMetro(dst);

    if (!srcIsMetro && dstIsMetro) {
      // RRTS → Metro
      const rrtsFare  = lookupFare(src, ixRRTS);
      const metroFare = lookupFare(ixMetro, dst);
      if (rrtsFare !== null && metroFare !== null) return rrtsFare + metroFare;
    } else if (srcIsMetro && !dstIsMetro) {
      // Metro → RRTS
      const metroFare = lookupFare(src, ixMetro);
      const rrtsFare  = lookupFare(ixRRTS, dst);
      if (rrtsFare !== null && metroFare !== null) return rrtsFare + metroFare;
    }

    return 20;
  }

  function calcTime(distance, nInterchanges) {
    return Math.ceil(distance * 0.72 + 5) + (nInterchanges * 4);
  }

  return { findRoute, calcDistance, calcFare, calcTime };
})();
