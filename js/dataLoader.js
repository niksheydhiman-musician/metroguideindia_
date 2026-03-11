/**
 * dataLoader.js — fetches all JSON data from /data/
 * Nothing is hardcoded. Pure dynamic loading.
 */
const DataLoader = (() => {
  async function loadAll() {
    const names = ['systems','lines','stations','connections','interchanges'];
    const results = await Promise.all(names.map(n =>
      fetch(`/data/${n}.json`).then(r => {
        if (!r.ok) throw new Error(`Cannot load data/${n}.json — HTTP ${r.status}. Make sure the /data folder sits next to index.html.`);
        return r.json();
      })
    ));
    return { systems: results[0], lines: results[1], stations: results[2], connections: results[3], interchanges: results[4] };
  }
  return { loadAll };
})();
