const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../VesselService.qml'), 'utf8');
function bodyAfter(text, marker) {
  const start = text.indexOf(marker) + marker.length;
  assert.ok(start >= marker.length);
  const brace = text.indexOf('{', start); let depth = 1, end = brace + 1;
  while (depth && end < text.length) { if (text[end] === '{') depth++; if (text[end] === '}') depth--; end++; }
  return text.slice(brace + 1, end - 1);
}
function service() {
  const state = vm.createContext({viewers: 1, wantedDetail: '', completedDetail: '', detailRetryAt: 0,
    mapDetail: {available: false}, detailProcess: {running: false, received: false, query: ''},
    process: {running: true}, helperCommand: args => ['python3', '-B', '/plugin/backend/vessel.py', ...args]});
  state.root = state;
  for (const name of ['requestDetail', 'startDetail']) {
    vm.runInContext(source.match(new RegExp('    function ' + name + '\\([^]*?\\n    }'))[0], state);
  }
  const process = source.slice(source.indexOf('id: detailProcess'), source.indexOf('property var config:'));
  state.read = data => { state.data = JSON.stringify(data); vm.runInContext('(function(data){' + bodyAfter(process, 'onRead: data =>') + '})(data)', state); };
  state.exit = () => { state.query = state.detailProcess.query; state.received = state.detailProcess.received; state.detailProcess.running = false;
    vm.runInContext('(function(){' + bodyAfter(process, 'onExited:') + '})()', state); };
  return state;
}
test('map requests are independent of reception and coalesce to the latest viewport', () => {
  const s = service(); s.requestDetail({zoom: 1}); const first = s.detailProcess.query;
  assert.deepEqual(Array.from(s.detailProcess.command).slice(-1), ['--map-detail']);
  s.requestDetail({zoom: 2}); s.requestDetail({zoom: 4});
  assert.equal(s.detailProcess.query, first);
  s.read({available: true, origin: [1, 2, 25]}); assert.equal(s.mapDetail.available, false);
  s.exit(); assert.equal(s.detailProcess.query, JSON.stringify({zoom: 4}));
  assert.equal(s.process.running, true);
});
test('complete results replace the map once; duplicate requests use the displayed map', () => {
  const s = service(); s.requestDetail({zoom: 2}); s.read({available: true, level: 12}); s.exit();
  assert.equal(s.mapDetail.level, 12); s.requestDetail({zoom: 2}); assert.equal(s.detailProcess.running, false);
});
test('failed batches retain the previous map and back off', () => {
  const s = service(); const previous = {available: true, level: 10}; s.mapDetail = previous;
  s.requestDetail({zoom: 8}); s.read({available: false}); s.exit();
  assert.equal(s.mapDetail, previous); s.requestDetail({zoom: 8}); assert.equal(s.detailProcess.running, false);
  s.detailRetryAt = 0; s.requestDetail({zoom: 8}); assert.equal(s.detailProcess.running, true);
});
test('closing the map discards in-flight replies without another request', () => {
  const s = service(); s.requestDetail({zoom: 8}); s.requestDetail(null);
  s.read({available: true}); s.exit(); assert.equal(s.mapDetail.available, false); assert.equal(s.detailProcess.running, false);
});

// Exercise loading/fallback transitions with the expression used by the radar.
test('offline geography is reserved for failed detail, not initial loading', () => {
  const radarSource = fs.readFileSync(path.join(__dirname, '../Radar.qml'), 'utf8');
  const expression = radarSource.match(/readonly property bool mapLoading: ([\s\S]*?)\n    signal/)[1];
  const state = {detailEnabled: true, detailed: false, detailQuery: 'view-a', failedDetailQuery: ''};
  const loading = () => vm.runInNewContext(expression, state);
  assert.equal(loading(), true);
  state.failedDetailQuery = 'view-a';
  assert.equal(loading(), false);
  state.detailQuery = 'view-b';
  assert.equal(loading(), true);
  state.detailed = true;
  assert.equal(loading(), false);
  state.detailed = false;
  state.detailEnabled = false;
  assert.equal(loading(), false); // A disabled detail layer needs no network map.
});

test('hidden views cannot start downloads or restart a canceled map request', () => {
  const s = service();
  s.requestDetail({zoom: 8});
  s.viewers = 0;
  s.requestDetail({zoom: 9});
  s.read({available: true}); s.exit();
  assert.equal(s.detailProcess.running, false);
  assert.equal(s.mapDetail.available, false);
  s.requestDetail({zoom: 10}); s.startDetail();
  assert.equal(s.detailProcess.running, false);
});
