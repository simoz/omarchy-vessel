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
    return (unit === "km" ? nm * 1.852 : nm).toFixed(1) + " " + (unit === "km" ? "km" : "nm");
}
// Project relative bearing and range onto a north-up radar with a 24-pixel margin.
function point(ship, size, radius) {
    var angle = ship.bearing * Math.PI / 180;
    var r = Math.min(1, ship.distance / radius) * (size / 2 - 24);
    // Canvas Y grows downwards, so north needs a negative cosine offset.
    return {x: size / 2 + Math.sin(angle) * r, y: size / 2 - Math.cos(angle) * r};
}

// Labels use the same normalized coordinates as land and the same zoom as ships.
// Prefer larger settlements, reject collisions, and keep every text box inside
// the circular chart. Widths come from Canvas text metrics, not guessed glyphs.
function cityLabels(cities, size, zoom, occupied) {
    var mid = size / 2, r = mid - 24;
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
function closestContact(ships, x, y, size, radius) {
    var nearest = null, best = 16 * 16;
    ships.forEach(function(ship) {
        if (ship.distance > radius) return;
        var p = point(ship, size, radius);
        var squared = Math.pow(x - p.x, 2) + Math.pow(y - p.y, 2);
        if (squared <= best && (nearest === null || squared < best)) {
            best = squared; nearest = ship;
        }
    });
    return nearest;
}
