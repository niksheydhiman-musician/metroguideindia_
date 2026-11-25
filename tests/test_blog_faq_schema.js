const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const scripts = new Map();
const document = {
  getElementById(id) { return scripts.get(id) || null; },
  createElement() {
    return { remove() { scripts.delete(this.id); } };
  },
  head: { appendChild(script) { scripts.set(script.id, script); } },
};
const window = {};
const source = fs.readFileSync('js/blogBridge.js', 'utf8')
  .replace('global.BlogBridge = BlogBridge;', 'global.testSetFaqSchema = setFaqSchema;');
vm.runInNewContext(source, { window, document });

const slug = 'delhi-metro-fare-calculator-how-fares-are-calculated-by-distance-in-2026';
window.testSetFaqSchema(slug, [{ question: 'Visible question?', answerText: 'Visible answer.' }]);
const schema = JSON.parse(scripts.get('post-faq-schema').textContent);
assert.equal(schema.mainEntity.length, 1);
assert.equal(schema.mainEntity[0].name, 'Visible question?');
assert.equal(schema.mainEntity[0].acceptedAnswer.text, 'Visible answer.');

window.testSetFaqSchema(slug, []);
assert.equal(scripts.has('post-faq-schema'), false);
