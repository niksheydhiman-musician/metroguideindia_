/**
 * graphBuilder.js
 * Builds a bidirectional adjacency graph from connections.json.
 *
 * KEY FIX: The RRTS corridor continues through Meerut South → Shatabdi Nagar
 * → Begumpul → Modipuram on the RRTS tracks. These RRTS-to-RRTS connections
 * already exist in connections.json (they were missing — we add them here as
 * virtual RRTS edges so BFS finds the direct RRTS path without going through
 * Meerut Metro stations).
 *
 * RRTS stations in Meerut with direct RRTS connections:
 *   meerut_south_rrts → shatabdi_nagar_rrts  (distance ~4.2 km, same line)
 *   shatabdi_nagar_rrts → begumpul_rrts       (distance ~5.4 km, same line)
 *   begumpul_rrts → modipuram_rrts            (distance ~12.2 km, same line)
 */
const GraphBuilder = (() => {

  // These are the RRTS-within-Meerut connections that must exist so BFS finds
  // the correct all-RRTS path. Derived from real station coordinates.
  const RRTS_MEERUT_EXTRA = [
    { connection_id: 'cx1', from_station: 'meerut_south_rrts',   to_station: 'shatabdi_nagar_rrts', line_id: 'rrts_main', distance_km: 4.2  },
    { connection_id: 'cx2', from_station: 'shatabdi_nagar_rrts', to_station: 'begumpul_rrts',        line_id: 'rrts_main', distance_km: 5.4  },
    { connection_id: 'cx3', from_station: 'begumpul_rrts',       to_station: 'modipuram_rrts',       line_id: 'rrts_main', distance_km: 12.2 },
  ];

  function build(connections) {
    // Merge real connections with the extra RRTS-within-Meerut ones
    const allConns = [...connections, ...RRTS_MEERUT_EXTRA];
    const graph = {};

    allConns.forEach(({ from_station, to_station, line_id, distance_km }) => {
      if (!graph[from_station]) graph[from_station] = [];
      if (!graph[to_station])   graph[to_station]   = [];
      graph[from_station].push({ neighbor: to_station, line_id, distance_km: +distance_km });
      graph[to_station].push({ neighbor: from_station, line_id, distance_km: +distance_km });
    });

    return graph;
  }

  return { build };
})();
