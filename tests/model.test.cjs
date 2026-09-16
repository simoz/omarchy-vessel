const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const m = vm.createContext({});
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname, '../Model.js'), 'utf8'), m);
test('nautical miles convert to kilometres', () => {
  assert.equal(m.distance(10, 'nm'), '10.0 nm');
  assert.equal(m.distance(10, 'km'), '18.5 km');
});
test('radar puts north above and east to the right of the user', () => {
  let north = m.point({bearing: 0, distance: 25}, 300, 25);
  let east = m.point({bearing: 90, distance: 25}, 300, 25);
  assert.equal(north.x, 150); assert.equal(north.y, 24);
  assert.equal(east.x, 276); assert.equal(east.y, 150);
});
test('relative bearing and signal age are explicit', () => {
  assert.equal(m.compass(359), 'N');
  assert.equal(m.compass(135), 'SE');
  assert.equal(m.age(100, 220000), '2m ago');
  assert.equal(m.age(null, 220000), 'No signal yet');
});
