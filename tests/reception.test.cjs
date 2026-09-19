const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

// Exercise the QML service's actual transition functions with a controllable
// process and timers, including transitions before an asynchronous exit arrives.
function service() {
  const timer = () => ({running: true, stop() {this.running = false;}, restart() {this.running = true;}});
  const state = vm.createContext({
    users: 1, viewers: 1, detailProcess: {running: false}, paused: false, stopping: false, pendingRestart: false,
    report: {status: 'LIVE', ships: [{mmsi: '123'}], total: 1},
    basemap: {available: true}, config: {pythonExecutable: 'python3'}, signature: '', helper: '/plugin/backend/vessel.py',
    process: {running: true}, startTimer: timer(), startupWatch: timer(),
    cityProcess: {running: false}, cityQuery: "", cityResults: [], cityError: "",
    loadSettings() {}
  });
  const source = fs.readFileSync(path.join(__dirname, '../VesselService.qml'), 'utf8');
  for (const name of ['clearCitySearch', 'searchCity', 'setViewing', 'helperCommand', 'stopReceiver', 'pause', 'togglePaused', 'restart', 'start', 'configure', 'detach']) {
    const match = source.match(new RegExp('    function ' + name + '\\([^]*?\\n    }'));
    assert.ok(match, name);
    vm.runInContext(match[0], state);
  }
  return state;
}
test('pause stops receiver and scheduled starts while preserving the snapshot and map', () => {
  const s = service(), ships = s.report.ships, map = s.basemap;
  s.pendingRestart = true;
  s.pause();
  assert.equal(s.process.running, false);
  assert.equal(s.pendingRestart, false);
  assert.equal(s.startTimer.running, false);
  assert.equal(s.startupWatch.running, false);
  assert.equal(s.report.status, 'PAUSED');
  assert.equal(s.report.ships, ships);
  assert.equal(s.basemap, map);
  s.start();
  assert.equal(s.process.running, false);
});
test('resume schedules a new connection and a rapid second pause cancels it', () => {
  const s = service();
  s.pause(); s.togglePaused();
  assert.equal(s.paused, false);
  assert.equal(s.startTimer.running, true);
  s.pause(); s.start();
  assert.equal(s.process.running, false);
  s.togglePaused(); s.start();
  assert.equal(s.process.running, true);
  assert.equal(s.report.status, 'STARTING');
});
test('another monitor or configuration refresh does not undo manual pause', () => {
  const s = service(); s.pause();
  s.configure({pythonExecutable: '/usr/bin/python3'});
  assert.equal(s.paused, true);
  assert.equal(s.process.running, false);
  s.users = 2; s.detach();
  assert.equal(s.users, 1);
  assert.equal(s.report.status, 'PAUSED');
  s.detach(); s.start();
  assert.equal(s.process.running, false);
});
test('helper arguments preserve spaces and metacharacters without a shell', () => {
  const s = service();
  s.config.pythonExecutable = '/path with spaces/python3';
  s.helper = '/plugin with spaces/backend/vessel.py';
  const query = 'Genoa; echo example';
  assert.deepEqual(Array.from(s.helperCommand(['--search-city', query])), [
    '/path with spaces/python3', '-B', '/plugin with spaces/backend/vessel.py', '--search-city', query
  ]);
});
test('a second monitor does not reset an already scheduled receiver start', () => {
  const s = service();
  s.process.running = false;
  s.signature = JSON.stringify(s.config);
  const snapshot = s.report;
  s.configure({pythonExecutable: 'python3'});
  assert.equal(s.report, snapshot);
  assert.equal(s.startTimer.running, true);
});

test('closing the last view stops all downloads and reopening resumes reception', () => {
  const s = service();
  s.detailProcess.running = true;
  s.cityProcess.running = true;
  s.cityQuery = 'Genoa';
  s.wantedDetail = 'pending';
  s.setViewing(false);
  assert.equal(s.process.running, false);
  assert.equal(s.detailProcess.running, false);
  assert.equal(s.wantedDetail, '');
  assert.equal(s.cityProcess.running, false);
  s.searchCity('Genoa');
  assert.equal(s.cityProcess.running, false);
  s.restart(); s.start();
  assert.equal(s.process.running, false);
  assert.equal(s.startTimer.running, false);
  s.setViewing(true); s.start();
  assert.equal(s.process.running, true);
});
test('other visible monitors keep reception alive and manual pause survives reopening', () => {
  const s = service();
  s.setViewing(true); s.setViewing(false);
  assert.equal(s.process.running, true);
  s.pause(); s.setViewing(false); s.setViewing(true); s.start();
  assert.equal(s.paused, true);
  assert.equal(s.process.running, false);
});

test('attaching a closed widget never schedules reception', () => {
  const s = service();
  s.viewers = 0; s.process.running = false; s.startTimer.running = false;
  s.configure({pythonExecutable: 'python3'}); s.start();
  assert.equal(s.process.running, false);
  assert.equal(s.startTimer.running, false);
});
