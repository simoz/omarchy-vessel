"""Normalize untrusted AIS reports and retain a bounded, distance-sorted fleet."""

import re
from datetime import datetime

from geometry import coordinates, distance_bearing, number

MAX_AGE, STALE_AGE = 1800, 300
MAX_TRACKED_SHIPS, MAX_VISIBLE_SHIPS = 2000, 200
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
        if kind == "StaticDataReport":
            report_a = body.get("ReportA") or {}
            report_b = body.get("ReportB") or {}
            if not isinstance(report_a, dict) or not isinstance(report_b, dict):
                return
            if report_a.get("Valid") is True:
                name = clean(report_a.get("Name")) or name
            if report_b.get("Valid") is True:
                kind_code = report_b.get("ShipType")
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
        destination = clean(body.get("Destination"))
        if destination:
            ship["destination"] = destination
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
        ship.update(
            latitude=lat,
            longitude=lon,
            distance=distance,
            bearing=bearing,
            lastSeen=stamp,
            timeSource=source,
            speed=body.get("Sog") if number(body.get("Sog"), 0, 102.2) else None,
            course=body.get("Cog") if number(body.get("Cog"), 0, 359.9) else None,
        )

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
                visible.append(ship | {"stale": now - position_time > STALE_AGE})
        self.ships = retained
        visible.sort(key=lambda ship: (ship["distance"], ship["mmsi"]))
        return dict(
            ships=visible[:MAX_VISIBLE_SHIPS],
            total=len(visible),
            lastSignal=self.last_signal,
        )
