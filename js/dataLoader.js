/**
 * dataLoader.js
 * Fetches all JSON data files from /data/ and returns them as a single object.
 * This is the ONLY place data is loaded — nothing is hardcoded.
 */
const DataLoader = (() => {

  async function loadAll() {
    const files = ['systems', 'lines', 'stations', 'connections', 'interchanges'];
    try {
      const results = await Promise.all(
        files.map(name =>
          fetch(`data/${name}.json`)
            .then(res => {
              if (!res.ok) throw new Error(`Failed to fetch data/${name}.json (${res.status})`);
              return res.json();
            })
        )
      );
      return {
        systems:      results[0],
        lines:        results[1],
        stations:     results[2],
        connections:  results[3],
        interchanges: results[4],
      };
    } catch (err) {
      throw new Error('DataLoader: ' + err.message);
    }
  }

  return { loadAll };
})();
