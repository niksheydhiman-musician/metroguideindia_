const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const payload = JSON.parse(fs.readFileSync('data/bengaluru.json', 'utf8'));
const context = {
  URLSearchParams,
  console,
  window: { location: { pathname: '/route.html', search: '?city=bengaluru' } },
  fetch: async () => ({ ok: true, json: async () => payload }),
};
vm.createContext(context);
for (const [file, name] of [
  ['js/dataLoader.js', 'DataLoader'],
  ['js/graphBuilder.js', 'GraphBuilder'],
  ['js/routeFinder.js', 'RouteFinder'],
]) {
  vm.runInContext(fs.readFileSync(file, 'utf8') + `\nglobalThis.${name} = ${name};`, context);
}

(async () => {
  const data = await context.DataLoader.loadAll();
  const graph = context.GraphBuilder.build(data.connections);
  for (const [from, to, distance, fare, lines] of [
    ['whitefield-kadugodi', 'electronic-city', 48.25, 90, 'PURPLE,GREEN,YELLOW'],
    ['challaghatta', 'whitefield-kadugodi', 43.95, 85, 'PURPLE'],
    ['central-silk-board', 'jayanagar', 6.5, 25, 'YELLOW,GREEN'],
  ]) {
    const path = context.RouteFinder.findRoute(graph, from, to);
    const actualDistance = context.RouteFinder.calcDistance(path, graph, 2);
    assert.equal(actualDistance, distance);
    assert.equal(context.RouteFinder.calcFare(path, {
      cityKey: data.cityKey, distance: actualDistance, fareRules: data.fareRules,
    }), fare);
    assert.equal([...new Set(path.map(step => step.line_id).filter(Boolean))].join(','), lines);
  }
  const direct = [{ station_id: 'a', line_id: null }, { station_id: 'b', line_id: 'PURPLE' }];
  const bounds = [2, 4, 6, 8, 10, 12, 15, 18, 21, 24, 27, 30, 33, 37, 42, 46];
  for (const [i, bound] of bounds.entries()) {
    const fareAt = distance => context.RouteFinder.calcFare(direct, {
      cityKey: data.cityKey, distance, fareRules: data.fareRules,
    });
    assert.equal(fareAt(bound), 10 + i * 5);
    assert.equal(fareAt(bound + 0.01), 15 + i * 5);
  }
  assert.throws(() => context.RouteFinder.calcFare(direct, {
    cityKey: data.cityKey, distance: 40,
  }), /fare rules and distance are required/);
  console.log('Bengaluru route engine checks passed.');
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
