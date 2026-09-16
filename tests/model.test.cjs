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

test('city labels follow zoom and stay inside the radar circle', () => {
  const city = {name: 'Harbour', x: 0.2, y: -0.1, textWidth: 40};
  const base = m.cityLabels([city], 340, 1, []);
  const zoom = m.cityLabels([city], 340, 2, []);
  assert.equal(base.length, 1); assert.equal(zoom.length, 1);
  assert.ok(Math.abs((zoom[0].dotX - 170) - 2 * (base[0].dotX - 170)) < 1e-9);
  assert.equal(m.cityLabels([{name:'Outside',x:0.8,y:0,textWidth:40}],340,2,[]).length,0);
});
test('city label density respects markers and text collisions', () => {
  const cities = Array.from({length:30},(_,i)=>({name:'Port '+i,x:0,y:-0.4,textWidth:40}));
  const labels = m.cityLabels(cities,340,1,[]);
  assert.ok(labels.length > 0 && labels.length < 10);
  for (let i=0;i<labels.length;i++) for(let j=i+1;j<labels.length;j++) {
    assert.ok(Math.abs(labels[i].x-labels[j].x)>=44 || Math.abs(labels[i].y-labels[j].y)>=14);
  }
  assert.equal(m.cityLabels(cities,340,1,[{x:0,y:0,width:340,height:340}]).length,0);
});
