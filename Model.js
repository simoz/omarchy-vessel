// All chart coordinates share the same margin; the outer space holds compass labels.
// Reconcile snapshots by MMSI so Qt keeps existing delegates and Canvas textures.
// Sorting moves rows; only new/expired vessels create or destroy delegates.
function syncShips(model, ships) {
    var wanted = {};
    ships.forEach(function(ship) { wanted[ship.mmsi] = true; });
    for (var i = model.count - 1; i >= 0; i--) {
        if (!wanted[model.get(i).mmsi]) model.remove(i);
    }
    ships.forEach(function(ship, index) {
        var position = index;
        while (position < model.count && model.get(position).mmsi !== ship.mmsi) position++;
        var signature = JSON.stringify(ship);
        if (position === model.count) {
            model.insert(index, {mmsi: ship.mmsi, ship: ship, signature: signature});
        } else {
            if (position !== index) model.move(position, index, 1);
            if (model.get(index).signature !== signature) {
                model.setProperty(index, "ship", ship);
                model.setProperty(index, "signature", signature);
            }
        }
    });
}

function radarRadius(size) { return Math.max(1, size / 2 - 24); }
// Low AIS speed means stationary, not necessarily moored or anchored.
function motion(ship) {
    if (typeof ship.speed !== "number" || !isFinite(ship.speed) || ship.speed < 0) return "unknown";
    return ship.speed < 0.5 ? "stationary" : "moving";
}
function inView(position, size, margin) {
    // Absorb floating-point rounding at the range ring, especially at high zoom.
    return Math.hypot(position.x - size / 2, position.y - size / 2) <= radarRadius(size) - (margin || 0) + 0.000001;
}

// Backend timestamps use seconds; QML Date.now() uses milliseconds.
function age(seconds, now) {
    if (typeof seconds !== "number" || !isFinite(seconds)) return "No signal yet";
    var elapsed = Math.max(0, Math.floor(now / 1000 - seconds));
    if (elapsed < 60) return elapsed + "s ago";
    return Math.floor(elapsed / 60) + "m ago";
}
// Round the bearing to the nearest of eight compass directions.
function compass(bearing) {
    return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][Math.round(bearing / 45) % 8];
}
// Retain nautical miles internally and convert only the displayed label.
function distance(nm, unit) {
    // One nautical mile is 1,852 metres; a statute mile is 1,609.344 metres.
    if (unit === "km") return (nm * 1.852).toFixed(1) + " km";
    if (unit === "mi") return (nm * 1852 / 1609.344).toFixed(1) + " mi";
    return nm.toFixed(1) + " nm";
}
// Project bearing/range into screen pixels. center is a pixel offset from the
// observer, not the normalized geographic center used to constrain panning.
function point(ship, size, radius, center) {
    var angle = ship.bearing * Math.PI / 180;
    var r = (ship.distance / radius) * radarRadius(size);
    // Canvas Y grows downwards, so north needs a negative cosine offset.
    center = center || {x: 0, y: 0};
    return {x: size / 2 + Math.sin(angle) * r - center.x, y: size / 2 - Math.cos(angle) * r - center.y};
}

// Labels use the same normalized coordinates as land and the same zoom as ships.
// Prefer larger settlements, reject collisions, and keep every text box inside
// the circular chart. Widths come from Canvas text metrics, not guessed glyphs.
function cityLabels(cities, size, zoom, occupied) {
    var mid = size / 2, r = radarRadius(size);
    var boxes = occupied.slice(), labels = [];
    function overlaps(a, b) {
        return a.x < b.x + b.width + 4 && a.x + a.width + 4 > b.x &&
               a.y < b.y + b.height + 3 && a.y + a.height + 3 > b.y;
    }
    function inside(box) {
        return [[box.x, box.y], [box.x + box.width, box.y],
                [box.x, box.y + box.height], [box.x + box.width, box.y + box.height]].every(function(p) {
            return Math.pow(p[0] - mid, 2) + Math.pow(p[1] - mid, 2) < Math.pow(r - 3, 2);
        });
    }
    cities.forEach(function(city) {
        if (labels.length >= 10 || Math.hypot(city.x, city.y) * zoom > 1) return;
        var x = mid + city.x * zoom * r, y = mid + city.y * zoom * r;
        var w = city.textWidth + 4, h = 14;
        var choices = [{x: x + 5, y: y - 17, width: w, height: h},
                       {x: x - w - 5, y: y - 17, width: w, height: h},
                       {x: x + 5, y: y + 4, width: w, height: h},
                       {x: x - w - 5, y: y + 4, width: w, height: h},
                       {x: x + 5, y: y - 32, width: w, height: h},
                       {x: x - w - 5, y: y - 32, width: w, height: h}];
        for (var i = 0; i < choices.length; i++) {
            var box = choices[i];
            if (inside(box) && !boxes.some(function(other) { return overlaps(box, other); })) {
                boxes.push(box);
                labels.push({name: city.name, x: box.x + 2, y: box.y + 10, dotX: x, dotY: y});
                break;
            }
        }
    });
    return labels;
}

// Keep a 16-pixel click radius around each tiny mark. Distance, not draw order,
// resolves overlapping targets; contacts outside the current view are ignored.
function closestContact(ships, x, y, size, radius, center) {
    var nearest = null, best = 16 * 16;
    ships.forEach(function(ship) {
        var p = point(ship, size, radius, center);
        if (!inView(p, size)) return;
        var squared = Math.pow(x - p.x, 2) + Math.pow(y - p.y, 2);
        if (squared <= best && (nearest === null || squared < best)) {
            best = squared; nearest = ship;
        }
    });
    return nearest;
}

// The entire viewport must remain inside the observer's loaded coverage circle.
// Centers use coverage-radius units, independent of zoom and widget size.
function boundedCenter(x, y, zoom) {
    var limit = Math.max(0, 1 - 1 / zoom), length = Math.hypot(x, y);
    var scale = length > limit && length > 0 ? limit / length : 1;
    return {x: x * scale, y: y * scale};
}

// A vessel's position in coverage-radius units, for explicit list-to-map navigation.
function shipCenter(ship, coverageRadius) {
    var angle = ship.bearing * Math.PI / 180;
    var range = ship.distance / coverageRadius;
    return {x: Math.sin(angle) * range, y: -Math.cos(angle) * range};
}

// VesselFinder detail pages use IMO; MMSI search also covers vessels without one.
function vesselUrl(ship) {
    if (!ship) return "";
    if (/^[1-9][0-9]{6}$/.test(String(ship.imo)))
        return "https://www.vesselfinder.com/vessels/details/" + ship.imo;
    if (/^[0-9]{9}$/.test(String(ship.mmsi)))
        return "https://www.vesselfinder.com/vessels?name=" + ship.mmsi;
    return "";
}
