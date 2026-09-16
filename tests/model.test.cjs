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

test('small radar marks keep generous hit targets and select the closest contact', () => {
  const near={mmsi:'near',bearing:90,distance:10};
  const other={mmsi:'other',bearing:90,distance:11};
  const p=m.point(near,340,25);
  assert.equal(m.closestContact([near,other],p.x,p.y,340,25).mmsi,'near');
  assert.equal(m.closestContact([near],p.x,p.y+15,340,25).mmsi,'near');
  assert.equal(m.closestContact([near],p.x,p.y+17,340,25),null);
  assert.equal(m.closestContact([near],p.x,p.y,340,5),null);
});
test('panning keeps the complete viewport within loaded coverage', () => {
  assert.equal(m.boundedCenter(1, 1, 1).x, 0);
  const p = m.boundedCenter(3, 4, 2);
  assert.ok(Math.abs(Math.hypot(p.x, p.y) - 0.5) < 1e-9);
  assert.ok(Math.abs(p.x / p.y - 0.75) < 1e-9);
  assert.equal(m.boundedCenter(0.1, 0, 4).x, 0.1);
});
test('panned contact selection includes ships beyond the original view radius', () => {
  const ship = {mmsi: 'east', bearing: 90, distance: 15};
  const offset = {x: 63, y: 0};
  const p = m.point(ship, 300, 12.5, offset);
  assert.ok(p.x < 276);
  assert.equal(m.closestContact([ship], p.x, p.y, 300, 12.5, offset), ship);
  assert.equal(m.closestContact([ship], p.x, p.y, 300, 12.5), null);
});
test('selecting a vessel reveals it at every zoom, including the coverage boundary', () => {
  for (const zoom of [1, 2, 4, 8, 16, 32, 64]) {
    for (const bearing of [0, 45, 90, 135, 180, 225, 270, 315]) {
      for (const distance of [0, 4.5, 24.9, 25]) {
        const ship = {bearing, distance};
        const wanted = m.shipCenter(ship, 25);
        const center = m.boundedCenter(wanted.x, wanted.y, zoom);
        const scale = zoom * m.radarRadius(340);
        const position = m.point(ship, 340, 25 / zoom, {x: center.x * scale, y: center.y * scale});
        assert.ok(m.inView(position, 340), `Hidden at zoom ${zoom}, bearing ${bearing}, distance ${distance}`);
      }
    }
  }
});
