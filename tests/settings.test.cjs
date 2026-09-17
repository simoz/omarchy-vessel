const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function form(mode) {
  const saved = [];
  const state = vm.createContext({canSave:true, provider:'aisstream', locationMode:mode, cityName:'Genoa',
    apiKey:{text:'replacement'}, radius:{text:'25'}, latitude:{text:'44.4'}, longitude:{text:'8.9'},
    kilometres:{checked:false}, miles:{checked:false}, VesselService:{saveSettings(value) {saved.push(value);}}});
  const source = fs.readFileSync(path.join(__dirname, '../SettingsForm.qml'), 'utf8');
  vm.runInContext(source.match(/    function save\([^]*?\n    }/)[0], state);
  return {state,saved};
}
test('location modes save unambiguous preferences and leave demo mode', () => {
  for (const mode of ['city','ip','coordinates']) {
    const {state,saved} = form(mode);
    state.save();
    assert.equal(saved.length,1);
    assert.equal(saved[0].autoLocation,mode==='ip');
    assert.equal(saved[0].cityName,mode==='city'?'Genoa':'');
    assert.equal(saved[0].demo,false);
    assert.equal(saved[0].latitude,'44.4');
    assert.equal(saved[0].apiKey,'replacement');
    assert.equal(state.apiKey.text,'');
  }
});
test('invalid or saving forms cannot submit; a blank key is passed through for preservation', () => {
  const {state,saved} = form('city');
  state.canSave=false;state.save();assert.equal(saved.length,0);
  state.canSave=true;state.apiKey.text='';state.kilometres.checked=true;state.save();
  assert.equal(saved[0].apiKey,'');assert.equal(saved[0].unit,'km');
});

test('OpenWaters saves its token separately and allows anonymous credentials', () => {
  const {state,saved} = form('city');
  state.provider='openwaters';state.apiKey.text='';state.save();
  assert.equal(saved[0].provider,'openwaters');
  assert.equal(saved[0].openwatersKey,'');
  assert.equal(Object.hasOwn(saved[0],'apiKey'),false);
});
