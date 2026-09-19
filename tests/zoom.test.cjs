const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../Radar.qml'), 'utf8');
function radar() {
  const model = vm.createContext({});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../Model.js'), 'utf8'), model);
  const state = vm.createContext({zoomLevel: 0, maxZoomLevel: 6, viewCenter: {x: 0, y: 0}, chartRadius: 150, width: 348, height: 348, pressed: false, Qt: {point: (x, y) => ({x, y})}});
  Object.defineProperty(state, 'zoom', {get: () => 2 ** state.zoomLevel});
  state.root = state;
  state.setCenter = (x, y) => { state.viewCenter = model.boundedCenter(x, y, state.zoom); };
  for (const name of ['zoomBy', 'zoomIn', 'zoomOut']) {
    vm.runInContext(source.match(new RegExp('    function ' + name + '\\([^]*?\\n    }'))[0], state);
  }
  const body = source.split('onWheel: function(wheel) {')[1].split('\n        onPressed:')[0].replace(/}\s*$/, '');
  state.wheel = (delta, x = 234, y = 174) => {
    state.event = {x, y, angleDelta: {y: delta}};
    vm.runInContext('(function(wheel) {' + body + '})(event)', state);
    return state.event.accepted;
  };
  return state;
}
test('buttons and keyboard zoom by 25%, as in Omastorm', () => {
  const s = radar(); s.zoomIn(); assert.ok(Math.abs(s.zoom - 1.25) < 1e-12);
  s.zoomOut(); assert.ok(Math.abs(s.zoom - 1) < 1e-12);
});
test('wheel uses the Omastorm factor regardless of delta magnitude', () => {
  for (const delta of [1, 120, 960]) {
    const s = radar(); s.wheel(delta); assert.ok(Math.abs(s.zoom - 1 / .85) < 1e-12);
    s.wheel(-delta); assert.ok(Math.abs(s.zoom - 1) < 1e-12);
  }
});
test('wheel anchors the pointer and keeps drag continuity', () => {
  const s = radar(); s.pressed = true;
  const before = s.viewCenter.x + 60 / (s.chartRadius * s.zoom);
  s.wheel(120);
  assert.ok(Math.abs(s.viewCenter.x + 60 / (s.chartRadius * s.zoom) - before) < 1e-12);
  assert.equal(s.pressCenter, s.viewCenter);
  assert.equal(s.pressPoint.x, 234);
});
test('zoom stays bounded and ignores horizontal and outside events', () => {
  const s = radar(); s.wheel(-120); assert.equal(s.zoom, 1);
  for (let i = 0; i < 100; i++) s.wheel(120);
  assert.equal(s.zoom, 64);
  assert.equal(s.wheel(-120, 0, 0), false);
  assert.equal(s.wheel(0), false); assert.equal(s.zoom, 64);
});
