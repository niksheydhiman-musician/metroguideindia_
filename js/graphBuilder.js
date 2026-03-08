/**
 * graphBuilder.js
 * Converts connections array into a bidirectional adjacency map.
 * Stations = nodes, connections = edges (with line_id and distance_km).
 */
const GraphBuilder = (() => {

  /**
   * @param {Array} connections  — from connections.json
   * @returns {Object}  { station_id: [{ neighbor, line_id, distance_km }, ...] }
   */
  function build(connections) {
    const graph = {};

    connections.forEach(({ from_station, to_station, line_id, distance_km }) => {
      if (!graph[from_station]) graph[from_station] = [];
      if (!graph[to_station])   graph[to_station]   = [];

      // undirected — add both directions
      graph[from_station].push({ neighbor: to_station, line_id, distance_km: Number(distance_km) });
      graph[to_station].push({ neighbor: from_station, line_id, distance_km: Number(distance_km) });
    });

    return graph;
  }

  return { build };
})();
