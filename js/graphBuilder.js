/**
 * graphBuilder.js
 * Builds a weighted bidirectional adjacency graph.
 *
 * WHY EXTRA RRTS EDGES:
 *   connections.json only has the sequential chain (each station to next).
 *   The RRTS corridor in Meerut (South → Shatabdi → Begumpul → Modipuram)
 *   needs direct skip-edges so Dijkstra can correctly evaluate ALL paths,
 *   including non-stop RRTS travel skipping intermediate interchange stations.
 *
 * INTERCHANGE WEIGHT:
 *   Interchange edges (platform change) get weight 0.01 km — effectively free
 *   in distance terms but present in the path so the UI can show "Change Train".
 */
const GraphBuilder = (() => {

  // Direct RRTS edges within Meerut — real approximate distances
  const EXTRA = [
    { from_station: 'meerut_south_rrts',   to_station: 'shatabdi_nagar_rrts',  line_id: 'rrts_main', distance_km: 4.58  },
    { from_station: 'shatabdi_nagar_rrts', to_station: 'begumpul_rrts',         line_id: 'rrts_main', distance_km: 5.76  },
    { from_station: 'begumpul_rrts',       to_station: 'modipuram_rrts',        line_id: 'rrts_main', distance_km: 13.52 },
    { from_station: 'meerut_south_rrts',   to_station: 'begumpul_rrts',         line_id: 'rrts_main', distance_km: 10.34 },
    { from_station: 'meerut_south_rrts',   to_station: 'modipuram_rrts',        line_id: 'rrts_main', distance_km: 23.86 },
    { from_station: 'shatabdi_nagar_rrts', to_station: 'modipuram_rrts',        line_id: 'rrts_main', distance_km: 19.28 },
  ];

  function build(connections) {
    const graph = {};

    const addEdge = (from, to, line_id, distance_km) => {
      if (!graph[from]) graph[from] = [];
      if (!graph[to])   graph[to]   = [];
      const w = line_id === 'interchange' ? 0.01 : +distance_km;
      graph[from].push({ neighbor: to,   line_id, distance_km: +distance_km, weight: w });
      graph[to].push({   neighbor: from, line_id, distance_km: +distance_km, weight: w });
    };

    [...connections, ...EXTRA].forEach(c =>
      addEdge(c.from_station, c.to_station, c.line_id, c.distance_km)
    );

    return graph;
  }

  return { build };
})();
