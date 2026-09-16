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
