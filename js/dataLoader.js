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
      // Backward-compatibility for existing pages still relying on split JSON files.
      return loadLegacySplitFiles(city.cityKey);
    }
  }

  return { loadAll };
})();
