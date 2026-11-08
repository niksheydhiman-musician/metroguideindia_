/**
 * dataLoader.js — loads city-specific route data from /data/
 */
const DataLoader = (() => {
  const CITY_DATASETS = [
    { cityKey: 'delhi',     pathRegex: /\/delhi-metro(?:\/|$)/,     file: 'delhi.json' },
    { cityKey: 'bengaluru', pathRegex: /\/bengaluru-metro(?:\/|$)/, file: 'bengaluru.json' },
    { cityKey: 'rrts',      pathRegex: /\/namo-bharat(?:\/|$)/,     file: 'rrts.json' },
  ];

  function normalize(payload, cityKey) {
    if (cityKey === 'bengaluru' && Array.isArray(payload.operationalLines)) {
      return {
        cityKey,
        systems: [{ system_id: 'bengaluru_metro', system_name: payload.metadata.networkName }],
        lines: payload.operationalLines.map(line => ({
          line_id: line.lineId, line_name: line.lineName, color: line.hexCode,
        })),
        stations: payload.stations.map(station => ({
          station_id: station.id, station_name: station.name, city: 'Bengaluru',
          system_id: 'bengaluru_metro', line_id: station.lines[0],
          interchange: station.isInterchange ? 'yes' : 'no',
        })),
        connections: Object.entries(payload.interstationDistances).flatMap(([line, edges]) =>
          edges.map(edge => ({
            from_station: edge.fromStationId, to_station: edge.toStationId,
            line_id: line, distance_km: edge.distanceKm,
          }))
        ),
        interchanges: payload.interchangeHubs.map(hub => ({
          station_id: hub.stationId, change_platform: hub.description,
          instructions: `Allow about ${hub.transferTimeMinutes} minutes`,
        })),
        fareRules: payload.fareRules,
        benchmarkTrip: payload.metadata.whitefieldToChallaghattaTrip,
        landmarks: [],
      };
    }
    return {
      cityKey: payload.city_key || cityKey || 'rrts',
      systems: payload.systems || [],
      lines: payload.lines || [],
      stations: payload.stations || [],
      connections: payload.connections || [],
      interchanges: payload.interchanges || [],
      landmarks: payload.landmarks || [],
    };
  }

  function detectCity() {
    const pathname = (window.location.pathname || '/').toLowerCase();
    const cityParam = new URLSearchParams(window.location.search).get('city');
    if (cityParam) {
      const byParam = CITY_DATASETS.find(c => c.cityKey === String(cityParam).toLowerCase());
      if (byParam) return byParam;
    }
    const exact = CITY_DATASETS.find(c => c.pathRegex.test(pathname));
    return exact || CITY_DATASETS[CITY_DATASETS.length - 1];
  }

  async function loadLegacySplitFiles(cityKey = 'rrts') {
    const names = ['systems', 'lines', 'stations', 'connections', 'interchanges'];
    const results = await Promise.all(names.map(n =>
      fetch(`/data/${n}.json`).then(r => {
        if (!r.ok) throw new Error(`Cannot load data/${n}.json — HTTP ${r.status}.`);
        return r.json();
      })
    ));
    return normalize({
      city_key: cityKey,
      systems: results[0],
      lines: results[1],
      stations: results[2],
      connections: results[3],
      interchanges: results[4],
      landmarks: [],
    }, cityKey);
  }

  async function loadAll() {
    const city = detectCity();
    try {
      const resp = await fetch(`/data/${city.file}`);
      if (!resp.ok) throw new Error(`Cannot load data/${city.file} — HTTP ${resp.status}.`);
      const payload = await resp.json();
      return normalize(payload, city.cityKey);
    } catch (err) {
      if (city.cityKey === 'bengaluru') throw err;
      // Backward-compatibility for existing pages still relying on split JSON files.
      return loadLegacySplitFiles(city.cityKey);
    }
  }

  return { loadAll };
})();

if (typeof window !== 'undefined') {
  window.DataLoader = DataLoader;
}
