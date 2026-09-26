"""Normalize untrusted AIS reports and retain a bounded, distance-sorted fleet."""

import re
from datetime import datetime

from geometry import coordinates, distance_bearing, number

MAX_AGE, STALE_AGE = 1800, 300
MAX_TRACKED_SHIPS, MAX_VISIBLE_SHIPS = 2000, 200
# Spread the wake across the whole expiry window: 20 points, 90 s apart, span
# 30 minutes. Shorter wakes stay hidden under the marker at typical ranges.
TRACK_POINTS, TRACK_MIN_MOVE = 20, 0.01
TRACK_INTERVAL = MAX_AGE // TRACK_POINTS
# Jumps faster than any AIS speed are receiver glitches; restart the wake.
TRACK_MAX_KNOTS = 120
POSITION_TYPES = (
    "PositionReport",
    "StandardClassBPositionReport",
    "ExtendedClassBPositionReport",
)
MESSAGE_TYPES = sorted((*POSITION_TYPES, "ShipStaticData", "StaticDataReport"))
TYPES = {
    30: "Fishing",
    31: "Towing",
    32: "Towing",
    33: "Dredging",
    34: "Diving",
    35: "Military",
    36: "Sailing",
    37: "Pleasure craft",
    50: "Pilot",
    51: "Search & rescue",
    52: "Tug",
    53: "Port tender",
    54: "Anti-pollution",
    55: "Law enforcement",
    58: "Medical",
}
NAVIGATION = {
    0: "Under way",
    1: "At anchor",
    2: "Not under command",
    3: "Restricted manoeuvrability",
    4: "Constrained by draught",
    5: "Moored",
    6: "Aground",
    7: "Fishing",
    8: "Sailing",
    14: "AIS-SART active",
}
# Saved state is re-validated with the same limits as live AIS reports.
SAVED_TEXT = dict(name=80, type=80, destination=80, status=80, eta=80, callSign=7)
SAVED_NUMBERS = dict(
    imo=(1000000, 9999999), length=(2, 1022), beam=(2, 126), draught=(0.1, 25.5)
)
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def clean(value, limit=80):
    """Discard AIS padding and control characters; never stringify structured data."""
    if not isinstance(value, str):
        return ""
    return re.sub(r"[\x00-\x1f\x7f]", "", value).strip(" @")[:limit]


def category(code):
    if type(code) is not int:
        return "Unknown"
    for low, high, name in (
        (60, 69, "Passenger"),
        (70, 79, "Cargo"),
        (80, 89, "Tanker"),
        (40, 49, "High-speed craft"),
    ):
        if low <= code <= high:
            return name
    return TYPES.get(code, "Unknown" if code == 0 else "Other")


def dimensions(value):
    """Return (length, beam) in metres; AIS uses 0 for unavailable sides."""
    if not isinstance(value, dict):
        return None, None
    sides = [value.get(key) for key in "ABCD"]
    if not all(type(side) is int for side in sides):
        return None, None
    a, b, c, d = sides
    length = a + b if 0 <= a <= 511 and 0 <= b <= 511 and a and b else None
    beam = c + d if 0 <= c <= 63 and 0 <= d <= 63 and c and d else None
    return length, beam


def eta_text(value):
    """Format a year-less AIS ETA; hour 24 or minute 60 mean the time is unknown."""
    if not isinstance(value, dict):
        return ""
    month, day, hour, minute = (
        value.get(key) for key in ("Month", "Day", "Hour", "Minute")
    )
    if not all(type(part) is int for part in (month, day, hour, minute)):
        return ""
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return ""
    text = f"{day} {MONTHS[month - 1]}"
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        text += f" {hour:02d}:{minute:02d} UTC"
    return text


def extend_track(track, point):
    """Append (time, lat, lon, distance, bearing) without mutating shared history."""
    if not track:
        return [point]
    stamp, lat, lon = point[:3]
    last_stamp, last_lat, last_lon = track[-1][:3]
    moved = distance_bearing(last_lat, last_lon, lat, lon)[0]
    elapsed = stamp - last_stamp
    if moved > max(0.1, TRACK_MAX_KNOTS * elapsed / 3600):
        return [point]
    if elapsed < TRACK_INTERVAL or moved < TRACK_MIN_MOVE:
        return track
    return [*track, point][-TRACK_POINTS:]


def attribution_text(credits):
    """Keep complete credits, omitting a credit already prefixed to another."""
    unique = list(dict.fromkeys(credits))
    return " · ".join(
        credit
        for credit in unique
        if not any(
            other.startswith(credit + separator)
            for other in unique
            for separator in (". ", " · ", "; ", " • ")
        )
    )


def message_time(metadata, received):
    """Use only timezone-aware, plausible AIS times; otherwise label receipt time."""
    raw = metadata.get("time_utc")
    if isinstance(raw, str):
        normalized = re.sub(r" \+0000 UTC$", "+00:00", raw).replace(" ", "T", 1)
        if re.search(r"(?:Z|[+-]\d{2}:\d{2})$", normalized):
            try:
                stamp = datetime.fromisoformat(normalized).timestamp()
                if stamp <= received + 60:
                    return stamp, "AIS timestamp"
            except (ValueError, OverflowError):
                pass
    return received, "Received"


class Fleet:
    """Merge Class A/B reports by MMSI; metadata never refreshes a position's age."""

    def __init__(self, lat, lon, radius):
        self.lat, self.lon, self.radius = lat, lon, radius
        self.ships, self.last_signal = {}, None

    def ingest(self, envelope, now):
        if (
            not isinstance(envelope, dict)
            or envelope.get("MessageType") not in MESSAGE_TYPES
        ):
            return
        kind, metadata, message = (
            envelope["MessageType"],
            envelope.get("MetaData"),
            envelope.get("Message"),
        )
        if not isinstance(metadata, dict) or not isinstance(message, dict):
            return
        body = message.get(kind)
        if not isinstance(body, dict) or body.get("Valid") is False:
            return
        mmsi = str(metadata.get("MMSI") or body.get("UserID", ""))
        if not re.fullmatch(r"[0-9]{9}", mmsi):
            return
        ship = self.ships.get(
            mmsi,
            dict(mmsi=mmsi, name="", type="Unknown", destination="", lastSeen=None),
        ).copy()
        name, kind_code = (
            clean(body.get("Name")) or clean(metadata.get("ShipName")),
            body.get("Type"),
        )
        # Call sign and dimensions come from Class A static data or Class B part B.
        static = body if kind == "ShipStaticData" else {}
        if kind == "StaticDataReport":
            report_a = body.get("ReportA") or {}
            report_b = body.get("ReportB") or {}
            if not isinstance(report_a, dict) or not isinstance(report_b, dict):
                return
            if report_a.get("Valid") is True:
                name = clean(report_a.get("Name")) or name
            if report_b.get("Valid") is True:
                kind_code = report_b.get("ShipType")
                static = report_b
        self.last_signal, ship["touched"] = now, now
        source = clean(envelope.get("source")).split(":", 1)[0]
        if source:
            credits = dict(ship.get("credits", {}))
            if source in credits or len(credits) < 8:
                credits[source] = clean(envelope.get("attribution"), 600) or source
            ship["credits"] = credits
            ship["attribution"] = attribution_text(credits.values())
        if name:
            ship["name"] = name
        if type(kind_code) is int and kind_code > 0:
            ship["type"] = category(kind_code)
        if kind == "ShipStaticData":
            imo = body.get("ImoNumber")
            if type(imo) is int and 1000000 <= imo <= 9999999:
                ship["imo"] = imo
        destination = clean(body.get("Destination"))
        if destination:
            ship["destination"] = destination
        call_sign = clean(static.get("CallSign"), 7)
        if call_sign:
            ship["callSign"] = call_sign
        length, beam = dimensions(static.get("Dimension"))
        if length:
            ship["length"] = length
        if beam:
            ship["beam"] = beam
        if kind == "ShipStaticData":
            draught = body.get("MaximumStaticDraught")
            if number(draught, 0.1, 25.5):
                ship["draught"] = round(draught, 1)
            eta = eta_text(body.get("Eta"))
            if eta:
                ship["eta"] = eta
        if kind in POSITION_TYPES:
            self.update_position(ship, body, metadata, now)
        self.ships[mmsi] = ship
        if len(self.ships) > MAX_TRACKED_SHIPS:
            del self.ships[min(self.ships, key=lambda key: self.ships[key]["touched"])]

    def update_position(self, ship, body, metadata, now):
        lat, lon = body.get("Latitude"), body.get("Longitude")
        if not coordinates(lat, lon):
            return
        stamp, source = message_time(metadata, now)
        if ship["lastSeen"] is not None and stamp < ship["lastSeen"]:
            return
        distance, bearing = distance_bearing(self.lat, self.lon, lat, lon)
        ship["track"] = extend_track(
            ship.get("track", []), (stamp, lat, lon, distance, bearing)
        )
        # Only Class A reports carry a navigational status; 15 means undefined.
        status = body.get("NavigationalStatus")
        if type(status) is int and 0 <= status <= 15:
            if status in NAVIGATION:
                ship["status"] = NAVIGATION[status]
            else:
                ship.pop("status", None)
        heading = body.get("TrueHeading")
        ship.update(
            # 511 marks an unavailable heading.
            heading=heading if type(heading) is int and 0 <= heading <= 359 else None,
            latitude=lat,
            longitude=lon,
            distance=distance,
            bearing=bearing,
            lastSeen=stamp,
            timeSource=source,
            speed=body.get("Sog") if number(body.get("Sog"), 0, 102.2) else None,
            course=body.get("Cog") if number(body.get("Cog"), 0, 359.9) else None,
        )

    def export(self):
        """Serializable fleet state; observer-relative values are recomputed on load."""
        return dict(
            version=1,
            ships={
                mmsi: {
                    key: value
                    for key, value in ship.items()
                    if key not in ("mmsi", "distance", "bearing", "attribution")
                }
                | {"track": [list(point[:3]) for point in ship.get("track", [])]}
                for mmsi, ship in self.ships.items()
            },
        )

    def restore(self, data, now):
        """Merge saved state as untrusted input, keeping only recent, valid fields."""
        if not isinstance(data, dict) or data.get("version") != 1:
            return
        saved = data.get("ships")
        if not isinstance(saved, dict):
            return
        for mmsi, raw in list(saved.items())[:MAX_TRACKED_SHIPS]:
            ship = self.restored_ship(mmsi, raw, now)
            if ship and mmsi not in self.ships:
                self.ships[mmsi] = ship

    def restored_ship(self, mmsi, raw, now):
        if not isinstance(raw, dict) or not re.fullmatch(r"[0-9]{9}", str(mmsi)):
            return None
        recent = now - MAX_AGE, now + 60
        if not number(raw.get("touched"), *recent):
            return None
        ship = dict(
            mmsi=mmsi,
            name="",
            type="Unknown",
            destination="",
            lastSeen=None,
            touched=raw["touched"],
        )
        for key, limit in SAVED_TEXT.items():
            text = clean(raw.get(key), limit)
            if text:
                ship[key] = text
        for key, (low, high) in SAVED_NUMBERS.items():
            if number(raw.get(key), low, high):
                ship[key] = raw[key]
        credits = raw.get("credits")
        if isinstance(credits, dict):
            credits = {
                clean(source): clean(text, 600)
                for source, text in list(credits.items())[:8]
                if clean(source) and clean(text, 600)
            }
            if credits:
                ship["credits"] = credits
                ship["attribution"] = attribution_text(credits.values())
        lat, lon, seen = raw.get("latitude"), raw.get("longitude"), raw.get("lastSeen")
        if coordinates(lat, lon) and number(seen, *recent):
            distance, bearing = distance_bearing(self.lat, self.lon, lat, lon)
            # A different observer location leaves distant contacts behind.
            if distance > 2 * self.radius:
                return None
            track = []
            points = raw.get("track")
            for point in points[-TRACK_POINTS:] if isinstance(points, list) else []:
                if (
                    isinstance(point, list)
                    and len(point) == 3
                    and number(point[0], recent[0], seen)
                    and coordinates(point[1], point[2])
                    and (not track or point[0] >= track[-1][0])
                ):
                    track.append(
                        (*point, *distance_bearing(self.lat, self.lon, *point[1:]))
                    )
            ship.update(
                latitude=lat,
                longitude=lon,
                distance=distance,
                bearing=bearing,
                lastSeen=seen,
                timeSource=raw.get("timeSource")
                if raw.get("timeSource") in ("AIS timestamp", "Received")
                else "Received",
                speed=raw.get("speed") if number(raw.get("speed"), 0, 102.2) else None,
                course=raw.get("course")
                if number(raw.get("course"), 0, 359.9)
                else None,
                heading=raw.get("heading")
                if type(raw.get("heading")) is int and 0 <= raw["heading"] <= 359
                else None,
                track=track,
            )
        return ship

    def snapshot(self, now):
        retained, visible = {}, []
        for mmsi, ship in self.ships.items():
            position_time = ship["lastSeen"]
            last_update = (
                position_time if position_time is not None else ship["touched"]
            )
            # Static metadata must not keep an expired position on the radar.
            if now - last_update >= MAX_AGE:
                continue
            retained[mmsi] = ship
            if position_time is not None and ship["distance"] <= self.radius:
                # Emit only the polar offsets the radar needs, oldest first.
                track = [
                    [round(point[3], 4), round(point[4], 3)]
                    for point in ship.get("track", [])
                    if now - point[0] < MAX_AGE
                ]
                visible.append(
                    ship | {"stale": now - position_time > STALE_AGE, "track": track}
                )
        self.ships = retained
        visible.sort(key=lambda ship: (ship["distance"], ship["mmsi"]))
        return dict(
            ships=visible[:MAX_VISIBLE_SHIPS],
            total=len(visible),
            lastSignal=self.last_signal,
        )
