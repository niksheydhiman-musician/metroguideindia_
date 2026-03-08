/**
 * routeFinder.js
 * BFS + real fare lookup table sourced from meerutmetro.in official data.
 *
 * KEY FIX — RRTS PATH PREFERENCE:
 *   BFS finds shortest hop-count. But since interchange edges add hops (2 extra
 *   nodes per interchange), purely RRTS routes within Meerut will now naturally
 *   win because they're shorter hop-count after graphBuilder adds direct edges.
 */
const RouteFinder = (() => {

  /* ── Real Fare Table (Standard Coach) ─────────────────────────────────────
     Source: meerutmetro.in — official NCRTC data, March 2026.
     Key = "from__to" (sorted alphabetically for bidirectionality).
     Meerut Metro fares: ₹10–₹60 (distance-based, short urban hops).
  ──────────────────────────────────────────────────────────────────────── */
  const FARE_TABLE = {
    // ── From Sarai Kale Khan ───────────────────────────────────────────────
    'sarai_kale_khan__new_ashok_nagar':   30,
    'sarai_kale_khan__anand_vihar':       50,
    'sarai_kale_khan__sahibabad':         60,
    'sarai_kale_khan__ghaziabad':         80,
    'sarai_kale_khan__guldhar':           90,
    'sarai_kale_khan__duhai':            100,
    'sarai_kale_khan__murad_nagar':      120,
    'sarai_kale_khan__modi_nagar_south': 140,
    'sarai_kale_khan__modi_nagar_north': 140,
    'sarai_kale_khan__meerut_south_rrts':160,
    'sarai_kale_khan__shatabdi_nagar_rrts':180,
    'sarai_kale_khan__begumpul_rrts':    200,
    'sarai_kale_khan__modipuram_rrts':   210,
    // ── From New Ashok Nagar ───────────────────────────────────────────────
    'new_ashok_nagar__anand_vihar':       30,
    'new_ashok_nagar__sahibabad':         50,
    'new_ashok_nagar__ghaziabad':         60,
    'new_ashok_nagar__guldhar':           70,
    'new_ashok_nagar__duhai':             80,
    'new_ashok_nagar__murad_nagar':      100,
    'new_ashok_nagar__modi_nagar_south': 120,
    'new_ashok_nagar__modi_nagar_north': 120,
    'new_ashok_nagar__meerut_south_rrts':150,
    'new_ashok_nagar__shatabdi_nagar_rrts':160,
    'new_ashok_nagar__begumpul_rrts':    180,
    'new_ashok_nagar__modipuram_rrts':   190,
    // ── From Anand Vihar ───────────────────────────────────────────────────
    'anand_vihar__sahibabad':             30,
    'anand_vihar__ghaziabad':             50,
    'anand_vihar__guldhar':               60,
    'anand_vihar__duhai':                 70,
    'anand_vihar__murad_nagar':           80,
    'anand_vihar__modi_nagar_south':     100,
    'anand_vihar__modi_nagar_north':     100,
    'anand_vihar__meerut_south_rrts':    130,
    'anand_vihar__shatabdi_nagar_rrts':  150,
    'anand_vihar__begumpul_rrts':        160,
    'anand_vihar__modipuram_rrts':       180,
    // ── From Sahibabad ────────────────────────────────────────────────────
    'sahibabad__ghaziabad':               30,
    'sahibabad__guldhar':                 40,
    'sahibabad__duhai':                   50,
    'sahibabad__murad_nagar':             70,
    'sahibabad__modi_nagar_south':        90,
    'sahibabad__modi_nagar_north':        90,
    'sahibabad__meerut_south_rrts':      110,
    'sahibabad__shatabdi_nagar_rrts':    130,
    'sahibabad__begumpul_rrts':          150,
    'sahibabad__modipuram_rrts':         160,
    // ── From Ghaziabad ────────────────────────────────────────────────────
    'ghaziabad__guldhar':                 30,
    'ghaziabad__duhai':                   40,
    'ghaziabad__murad_nagar':             60,
    'ghaziabad__modi_nagar_south':        70,
    'ghaziabad__modi_nagar_north':        80,
    'ghaziabad__meerut_south_rrts':      100,
    'ghaziabad__shatabdi_nagar_rrts':    110,
    'ghaziabad__begumpul_rrts':          130,
    'ghaziabad__modipuram_rrts':         140,
    // ── From Guldhar ──────────────────────────────────────────────────────
    'guldhar__duhai':                     30,
    'guldhar__murad_nagar':               40,
    'guldhar__modi_nagar_south':          60,
    'guldhar__modi_nagar_north':          70,
    'guldhar__meerut_south_rrts':         90,
    'guldhar__shatabdi_nagar_rrts':      100,
    'guldhar__begumpul_rrts':            120,
    'guldhar__modipuram_rrts':           130,
    // ── From Duhai ────────────────────────────────────────────────────────
    'duhai__murad_nagar':                 30,
    'duhai__modi_nagar_south':            50,
    'duhai__modi_nagar_north':            60,
    'duhai__meerut_south_rrts':           80,
    'duhai__shatabdi_nagar_rrts':         90,
    'duhai__begumpul_rrts':              110,
    'duhai__modipuram_rrts':             120,
    // ── From Murad Nagar ─────────────────────────────────────────────────
    'murad_nagar__modi_nagar_south':      30,
    'murad_nagar__modi_nagar_north':      40,
    'murad_nagar__meerut_south_rrts':     60,
    'murad_nagar__shatabdi_nagar_rrts':   70,
    'murad_nagar__begumpul_rrts':         90,
    'murad_nagar__modipuram_rrts':       100,
    // ── From Modi Nagar South ────────────────────────────────────────────
    'modi_nagar_south__modi_nagar_north': 30,
    'modi_nagar_south__meerut_south_rrts':50,
    'modi_nagar_south__shatabdi_nagar_rrts':60,
    'modi_nagar_south__begumpul_rrts':    80,
    'modi_nagar_south__modipuram_rrts':   90,
    // ── From Modi Nagar North ────────────────────────────────────────────
    'modi_nagar_north__meerut_south_rrts':40,
    'modi_nagar_north__shatabdi_nagar_rrts':50,
    'modi_nagar_north__begumpul_rrts':    70,
    'modi_nagar_north__modipuram_rrts':   80,
    // ── Within Meerut RRTS ───────────────────────────────────────────────
    'meerut_south_rrts__shatabdi_nagar_rrts': 30,
    'meerut_south_rrts__begumpul_rrts':       50,
    'meerut_south_rrts__modipuram_rrts':      60,
    'shatabdi_nagar_rrts__begumpul_rrts':     30,
    'shatabdi_nagar_rrts__modipuram_rrts':    40,
    'begumpul_rrts__modipuram_rrts':          30,
    // ── Meerut Metro (intra-city) ─────────────────────────────────────────
    // Short urban hops ₹10–₹60
    'meerut_south_meerut_metro__partapur':    10,
    'meerut_south_meerut_metro__rithani':     20,
    'meerut_south_meerut_metro__shatabdi_nagar_meerut_metro': 30,
    'meerut_south_meerut_metro__brahampuri':  30,
    'meerut_south_meerut_metro__meerut_central': 40,
    'meerut_south_meerut_metro__bhaisali_bus_adda': 40,
    'meerut_south_meerut_metro__begumpul_meerut_metro': 50,
    'meerut_south_meerut_metro__mes_colony':  50,
    'meerut_south_meerut_metro__daurli':      60,
    'meerut_south_meerut_metro__meerut_north':60,
    'meerut_south_meerut_metro__modipuram_meerut_metro': 60,
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
    'shatabdi_nagar_meerut_metro__meerut_central': 20,
    'shatabdi_nagar_meerut_metro__bhaisali_bus_adda': 30,
    'shatabdi_nagar_meerut_metro__begumpul_meerut_metro': 30,
    'shatabdi_nagar_meerut_metro__mes_colony':40,
    'shatabdi_nagar_meerut_metro__daurli':    40,
    'shatabdi_nagar_meerut_metro__meerut_north': 50,
    'shatabdi_nagar_meerut_metro__modipuram_meerut_metro': 60,
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
    'bhaisali_bus_adda__begumpul_meerut_metro': 10,
    'bhaisali_bus_adda__mes_colony':          20,
    'bhaisali_bus_adda__daurli':              30,
    'bhaisali_bus_adda__meerut_north':        30,
    'bhaisali_bus_adda__modipuram_meerut_metro': 40,
    'begumpul_meerut_metro__mes_colony':      10,
    'begumpul_meerut_metro__daurli':          20,
    'begumpul_meerut_metro__meerut_north':    30,
    'begumpul_meerut_metro__modipuram_meerut_metro': 30,
    'mes_colony__daurli':                     10,
    'mes_colony__meerut_north':               20,
    'mes_colony__modipuram_meerut_metro':     30,
    'daurli__meerut_north':                   10,
    'daurli__modipuram_meerut_metro':         20,
    'meerut_north__modipuram_meerut_metro':   10,
  };

  /** Fare lookup — symmetric (sorted pair) */
  function lookupFare(id1, id2) {
    const key  = [id1, id2].sort().join('__');
    // Direct lookup
    if (FARE_TABLE[key] !== undefined) return FARE_TABLE[key];
    // If one side is an interchange twin, try the RRTS variant
    const normalize = id => id.replace('_meerut_metro', '_rrts').replace(/_rrts$/, '').replace(/_meerut_metro$/, '');
    const k2 = [normalize(id1), normalize(id2)].sort().join('__');
    return FARE_TABLE[k2] || null;
  }

  /** BFS shortest path */
  function findRoute(graph, src, dst) {
    if (!graph[src] || !graph[dst]) return null;
    if (src === dst) return [{ station_id: src, line_id: null }];
    const visited = new Set([src]);
    const queue   = [{ id: src, path: [{ station_id: src, line_id: null }] }];
    while (queue.length) {
      const { id, path } = queue.shift();
      for (const edge of (graph[id] || [])) {
        if (visited.has(edge.neighbor)) continue;
        visited.add(edge.neighbor);
        const np = [...path, { station_id: edge.neighbor, line_id: edge.line_id }];
        if (edge.neighbor === dst) return np;
        queue.push({ id: edge.neighbor, path: np });
      }
    }
    return null;
  }

  /** Sum distances along path */
  function calcDistance(path, graph) {
    let t = 0;
    for (let i = 0; i < path.length - 1; i++) {
      const edge = (graph[path[i].station_id] || []).find(e => e.neighbor === path[i+1].station_id);
      if (edge) t += edge.distance_km;
    }
    return Math.round(t * 10) / 10;
  }

  /** Real fare: look up direct pair first, else use distance-based slab */
  function calcFare(path) {
    const src = path[0].station_id;
    const dst = path[path.length - 1].station_id;
    const direct = lookupFare(src, dst);
    if (direct) return direct;

    // Fallback: sum segment fares along the path
    let total = 0;
    for (let i = 0; i < path.length - 1; i++) {
      const f = lookupFare(path[i].station_id, path[i+1].station_id);
      if (f) total += f;
    }
    return total || 30; // minimum ₹30
  }

  /** Travel time estimate */
  function calcTime(distance, numInterchanges) {
    // RRTS avg 100 km/h → 0.6 min/km, Metro avg 40 km/h → 1.5 min/km (mixed)
    const base = Math.ceil(distance * 0.72 + 5);
    return base + (numInterchanges * 4); // 4 min per interchange walk
  }

  return { findRoute, calcDistance, calcFare, calcTime };
})();
