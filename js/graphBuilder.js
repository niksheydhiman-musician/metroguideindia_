/**
 * graphBuilder.js
 * Builds a weighted bidirectional adjacency graph.
 *
 * CORE DESIGN PRINCIPLE:
 *   The RRTS and Meerut Metro are two SEPARATE systems connected only at 4 points.
 *   Interchange edges carry a HIGH PENALTY WEIGHT (100 km equivalent) so Dijkstra
 *   will NEVER use an interchange unless there is genuinely no direct path within
 *   the same system to the destination.
 *
 *   Example: Modipuram → New Ashok Nagar
 *     Via RRTS direct:     ~82 km → WINS
 *     Via Metro then RRTS: ~82 km + 100 penalty = 182 km → LOSES
 *
 *   Example: Sarai Kale Khan → Meerut North (metro-only station)
 *     Via RRTS to Shatabdi Nagar + interchange + Metro: ~62 km + 100 penalty + ~3 km = 165 km
 *     Via RRTS to Begumpul + interchange + Metro back: ~72 km + 100 + 1.2 km = 173 km
 *     → Shatabdi Nagar interchange WINS (shortest total)
 *
 * RRTS MEERUT SKIP-EDGES:
 *   The sequential connections.json has no direct RRTS edge between e.g. Meerut South
 *   and Begumpul. We add skip-edges with real distances so Dijkstra routes RRTS→RRTS
 *   correctly without needing to visit every intermediate interchange node.
 */
const GraphBuilder = (() => {

  // RRTS skip-edges within Meerut (all sequential + skip combinations)
  const RRTS_MEERUT = [
    { from_station: 'meerut_south_rrts',   to_station: 'shatabdi_nagar_rrts',  line_id: 'rrts_main', distance_km: 4.58  },
    { from_station: 'shatabdi_nagar_rrts', to_station: 'begumpul_rrts',         line_id: 'rrts_main', distance_km: 5.76  },
    { from_station: 'begumpul_rrts',       to_station: 'modipuram_rrts',        line_id: 'rrts_main', distance_km: 13.52 },
    { from_station: 'meerut_south_rrts',   to_station: 'begumpul_rrts',         line_id: 'rrts_main', distance_km: 10.34 },
    { from_station: 'meerut_south_rrts',   to_station: 'modipuram_rrts',        line_id: 'rrts_main', distance_km: 23.86 },
    { from_station: 'shatabdi_nagar_rrts', to_station: 'modipuram_rrts',        line_id: 'rrts_main', distance_km: 19.28 },
  ];

  // HIGH PENALTY for interchange — makes Dijkstra avoid crossing systems
  // unless the destination is on the other system (no alternative).
  // 100 km >> any real route segment, so it only gets used when necessary.
  const INTERCHANGE_PENALTY = 100;

  function build(connections) {
    const graph = {};

    const addEdge = (from, to, line_id, distance_km) => {
      if (!graph[from]) graph[from] = [];
      if (!graph[to])   graph[to]   = [];
      // Interchange edges: real distance 0 but Dijkstra weight = high penalty
      const weight = line_id === 'interchange' ? INTERCHANGE_PENALTY : +distance_km;
      graph[from].push({ neighbor: to,   line_id, distance_km: +distance_km, weight });
      graph[to].push({   neighbor: from, line_id, distance_km: +distance_km, weight });
    };

    [...connections, ...RRTS_MEERUT].forEach(c =>
      addEdge(c.from_station, c.to_station, c.line_id, c.distance_km)
    );

    return graph;
  }

  return { build };
})();
