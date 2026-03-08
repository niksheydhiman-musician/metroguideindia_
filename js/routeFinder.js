/**
 * routeFinder.js
 * BFS shortest-path algorithm on the transit graph.
 * Also provides fare and travel-time estimators.
 */
const RouteFinder = (() => {

  /**
   * BFS: find shortest path from source to dest.
   * @returns {Array|null}  [{station_id, line_id}, ...] or null if unreachable
   */
  function findRoute(graph, source, dest) {
    if (!graph[source] || !graph[dest]) return null;
    if (source === dest) return [{ station_id: source, line_id: null }];

    const visited = new Set([source]);
    const queue   = [{ id: source, path: [{ station_id: source, line_id: null }] }];

    while (queue.length) {
      const { id, path } = queue.shift();

      for (const edge of (graph[id] || [])) {
        if (visited.has(edge.neighbor)) continue;
        visited.add(edge.neighbor);

        const newPath = [...path, { station_id: edge.neighbor, line_id: edge.line_id }];
        if (edge.neighbor === dest) return newPath;

        queue.push({ id: edge.neighbor, path: newPath });
      }
    }
    return null;
  }

  /** Sum of edge distances along a path */
  function calcDistance(path, graph) {
    let total = 0;
    for (let i = 0; i < path.length - 1; i++) {
      const from = path[i].station_id;
      const to   = path[i + 1].station_id;
      const edge = (graph[from] || []).find(e => e.neighbor === to);
      if (edge) total += edge.distance_km;
    }
    return Math.round(total * 10) / 10;
  }

  /** Approximate RRTS/Metro fare slab (INR) */
  function calcFare(km) {
    if (km <=  5) return 20;
    if (km <= 12) return 30;
    if (km <= 20) return 40;
    if (km <= 30) return 55;
    if (km <= 45) return 70;
    if (km <= 60) return 90;
    return 110;
  }

  /** Approximate travel time in minutes */
  function calcTime(km) {
    // ~90 km/h effective speed + 2 min boarding margin per interchange
    return Math.ceil(km * 0.75 + 6);
  }

  return { findRoute, calcDistance, calcFare, calcTime };
})();
