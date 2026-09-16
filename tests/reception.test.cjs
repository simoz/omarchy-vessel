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
    users: 1, paused: false, stopping: false, pendingRestart: false,
    report: {status: 'LIVE', ships: [{mmsi: '123'}], total: 1},
    basemap: {available: true}, config: {pythonExecutable: 'python3'}, signature: '', helper: '/plugin/backend/vessel.py',
    process: {running: true}, startTimer: timer(), startupWatch: timer(),
    clearCitySearch() {}, loadSettings() {}
  });
  const source = fs.readFileSync(path.join(__dirname, '../VesselService.qml'), 'utf8');
  for (const name of ['pause', 'togglePaused', 'restart', 'start', 'configure', 'detach']) {
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
