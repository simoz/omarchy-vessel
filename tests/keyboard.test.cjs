const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const Qt = {ControlModifier: 1, AltModifier: 2, MetaModifier: 4, ShiftModifier: 8, KeypadModifier: 16};
['F1', 'Escape', 'Left', 'Right', 'Up', 'Down', 'Home', 'PageUp', 'PageDown', 'Return', 'Enter'].forEach((key, i) => Qt['Key_' + key] = 100 + i);
const keyboard = vm.createContext({Qt});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../Keyboard.js'), 'utf8'), keyboard);

test('keyboard shortcuts accept shifted punctuation, uppercase and keypad input', () => {
  for (const [key, text, modifiers, expected] of [
    [0, '?', Qt.ShiftModifier, 'help'], [Qt.Key_F1, '', 0, 'help'],
    [0, '+', Qt.ShiftModifier, 'zoomIn'], [0, '=', 0, 'zoomIn'],
    [0, '+', Qt.KeypadModifier, 'zoomIn'], [0, '-', 0, 'zoomOut'],
    [0, 'F', Qt.ShiftModifier, 'expand'], [0, 's', 0, 'settings'],
    [0, '[', 0, 'previous'], [0, ']', 0, 'next'],
    [0, ' ', 0, 'pause'], [0, 'p', 0, 'pause'],
    [0, 'r', 0, 'reconnect'], [Qt.Key_Return, '', 0, 'reconnect'],
    [Qt.Key_Enter, '', Qt.KeypadModifier, 'reconnect'],
    [0, '0', 0, 'center'], [Qt.Key_Home, '', 0, 'center'],
    [Qt.Key_Escape, '', 0, 'dismiss']
  ]) assert.equal(keyboard.command(key, text, modifiers), expected);
});
test('desktop and editor modifier combinations never trigger radar actions', () => {
  for (const modifier of [Qt.ControlModifier, Qt.AltModifier, Qt.MetaModifier]) {
    for (const text of ['f', 's', 'r', '?', '+', ' '])
      assert.equal(keyboard.command(0, text, modifier | Qt.ShiftModifier), '');
    assert.equal(keyboard.command(Qt.Key_Left, '', modifier), '');
  }
  assert.equal(keyboard.command(0, '\t', 0), '');
  assert.equal(keyboard.command(0, 'a', 0), '');
});
test('arrow and vim movement agree; page keys scroll instead of panning', () => {
  for (const [key, text, command] of [['Left','h','left'], ['Right','l','right'], ['Up','k','up'], ['Down','j','down']]) {
    assert.equal(keyboard.command(Qt['Key_' + key], '', 0), command);
    assert.equal(keyboard.command(0, text, 0), command);
  }
  assert.equal(keyboard.command(Qt.Key_PageUp, '', 0), 'pageUp');
  assert.equal(keyboard.command(Qt.Key_PageDown, '', 0), 'pageDown');
});
test('keyboard vessel navigation wraps and survives a missing selection or empty fleet', () => {
  const selected = [], positioned = [];
  const state = vm.createContext({ships: [{mmsi:'a'}, {mmsi:'b'}, {mmsi:'c'}], selectedShip:{mmsi:'c'},
    revealShip(ship) {selected.push(ship.mmsi);}, contacts:{positionViewAtIndex(i) {positioned.push(i);}}, ListView:{Contain:0}});
  const source = fs.readFileSync(path.join(__dirname, '../Widget.qml'), 'utf8');
  vm.runInContext(source.match(/    function selectVessel\([^]*?\n    }/)[0], state);
  state.selectVessel(1); assert.equal(selected.pop(), 'a'); assert.equal(positioned.pop(), 0);
  state.selectedShip = {mmsi:'a'}; state.selectVessel(-1); assert.equal(selected.pop(), 'c');
  state.selectedShip = null; state.selectVessel(1); assert.equal(selected.pop(), 'b');
  state.ships = []; state.selectVessel(1); assert.equal(selected.length, 0);
});
