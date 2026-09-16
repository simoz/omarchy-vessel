#!/usr/bin/env python3
"""Vessel's JSON-lines receiver. Only live mode needs the managed WebSocket dependency."""
import argparse
import asyncio
from contextlib import suppress
from datetime import datetime
import json
import logging
import math
import random
import re
import signal
import sys
import time
import urllib.request

import basemap
from geometry import GENOVA, bounding_boxes, coordinates, destination, distance_bearing, number
import settings

MAX_AGE, STALE_AGE = 1800, 300
POSITION_TYPES = ("PositionReport", "StandardClassBPositionReport", "ExtendedClassBPositionReport")
MESSAGE_TYPES = sorted((*POSITION_TYPES, "ShipStaticData", "StaticDataReport"))
TYPES = {30:"Fishing",31:"Towing",32:"Towing",33:"Dredging",34:"Diving",35:"Military",
         36:"Sailing",37:"Pleasure craft",50:"Pilot",51:"Search & rescue",52:"Tug",
         53:"Port tender",54:"Anti-pollution",55:"Law enforcement",58:"Medical"}


def clean(value):
    return re.sub(r"[\x00-\x1f\x7f]", "", str(value or "")).strip(" @")[:80]


def category(code):
    if type(code) is not int:
        return "Unknown"
    for low, high, name in ((60,69,"Passenger"),(70,79,"Cargo"),(80,89,"Tanker"),(40,49,"High-speed craft")):
        if low <= code <= high:
            return name
    return TYPES.get(code, "Unknown" if code == 0 else "Other")


def message_time(metadata, received):
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
        if not isinstance(envelope, dict) or envelope.get("MessageType") not in MESSAGE_TYPES:
            return
        kind, metadata, message = envelope["MessageType"], envelope.get("MetaData"), envelope.get("Message")
        if not isinstance(metadata, dict) or not isinstance(message, dict):
            return
        body = message.get(kind)
        if not isinstance(body, dict) or body.get("Valid") is False:
            return
        mmsi = str(metadata.get("MMSI") or body.get("UserID", ""))
        if not re.fullmatch(r"[0-9]{9}", mmsi):
            return
        ship = self.ships.get(mmsi, dict(mmsi=mmsi, name="", type="Unknown", destination="", lastSeen=None)).copy()
        name, kind_code = clean(body.get("Name")) or clean(metadata.get("ShipName")), body.get("Type")
        if kind == "StaticDataReport":
            a, b = body.get("ReportA") or {}, body.get("ReportB") or {}
            if not isinstance(a, dict) or not isinstance(b, dict):
                return
            if a.get("Valid") is True:
                name = clean(a.get("Name")) or name
            if b.get("Valid") is True:
                kind_code = b.get("ShipType")
        self.last_signal, ship["touched"] = now, now
        if name:
            ship["name"] = name
        if type(kind_code) is int and kind_code > 0:
            ship["type"] = category(kind_code)
        if clean(body.get("Destination")):
            ship["destination"] = clean(body["Destination"])
        if kind in POSITION_TYPES:
            self.update_position(ship, body, metadata, now)
        self.ships[mmsi] = ship
        if len(self.ships) > 2000:
            del self.ships[min(self.ships, key=lambda key: self.ships[key]["touched"])]

    def update_position(self, ship, body, metadata, now):
        lat, lon = body.get("Latitude"), body.get("Longitude")
        if not coordinates(lat, lon):
            return
        stamp, source = message_time(metadata, now)
        if ship["lastSeen"] is not None and stamp < ship["lastSeen"]:
            return
        distance, bearing = distance_bearing(self.lat, self.lon, lat, lon)
        ship.update(latitude=lat, longitude=lon, distance=distance, bearing=bearing,
                    lastSeen=stamp, timeSource=source,
                    speed=body.get("Sog") if number(body.get("Sog"),0,102.2) else None,
                    course=body.get("Cog") if number(body.get("Cog"),0,359.9) else None)

    def snapshot(self, now):
        self.ships = {key: ship for key,ship in self.ships.items()
                      if now-(ship["lastSeen"] if ship["lastSeen"] is not None else ship["touched"]) < MAX_AGE}
        visible = [ship | {"stale": now-ship["lastSeen"] > STALE_AGE} for ship in self.ships.values()
                   if ship["lastSeen"] is not None and ship["distance"] <= self.radius]
        visible.sort(key=lambda ship: (ship["distance"],ship["mmsi"]))
        return dict(ships=visible[:200], total=len(visible), lastSignal=self.last_signal)


class Receiver:
    URL = "wss://stream.aisstream.io/v0/stream"

    def __init__(self, fleet, state, key, output, *, url=URL, retry_delay=2):
        self.fleet, self.state, self.key, self.output = fleet, state, key, output
        self.url, self.retry_delay = url, retry_delay
        self.confirmed, self.last_message = False, time.monotonic()

    def emit(self):
        self.output(self.state | self.fleet.snapshot(time.time()))
        self.state.pop("basemap", None)

    def handle_message(self, raw):
        try:
            envelope = json.loads(raw)
        except (ValueError, UnicodeError):
            return True
        if not isinstance(envelope, dict):
            return True
        if "error" in envelope or "Error" in envelope:
            self.state.update(status="REJECTED", error="AISStream rejected the subscription. Check your key and account connection limit.")
            self.emit()
            return False
        kind = envelope.get("MessageType")
        if kind == "SubscriptionConfirmation" or kind in MESSAGE_TYPES:
            self.confirmed, self.last_message = True, time.monotonic()
            self.state.update(status="LISTENING" if kind == "SubscriptionConfirmation" else "LIVE", error="")
            if kind != "SubscriptionConfirmation":
                self.fleet.ingest(envelope, time.time())
        return True

    async def publish(self):
        while True:
            self.emit()
            await asyncio.sleep(1)

    async def run(self):
        # The library owns TLS, framing, compression, ping/pong and cancellation.
        # A private logger prevents server error text or payloads leaking a key.
        from websockets.asyncio.client import connect
        from websockets.exceptions import WebSocketException
        logger = logging.Logger("vessel.websocket", level=logging.CRITICAL + 1)
        logger.addHandler(logging.NullHandler())
        publisher = asyncio.create_task(self.publish())
        delay = self.retry_delay
        try:
            while True:
                self.state.update(status="CONNECTING", error="")
                self.emit()
                opened = time.monotonic()
                try:
                    async with connect(self.url, compression="deflate", proxy=None,
                                       open_timeout=15, close_timeout=3, ping_interval=20,
                                       ping_timeout=15, max_size=1_048_576, logger=logger) as socket:
                        opened = time.monotonic()
                        self.confirmed, self.last_message = False, opened
                        # Subscribe immediately, within AISStream's authentication deadline.
                        await socket.send(json.dumps(dict(APIKey=self.key,
                            BoundingBoxes=bounding_boxes(self.fleet.lat,self.fleet.lon,self.fleet.radius),
                            FilterMessageTypes=MESSAGE_TYPES)))
                        while True:
                            now = time.monotonic()
                            if not self.confirmed and now-opened > 20:
                                raise TimeoutError("Subscription deadline")
                            if self.confirmed and now-self.last_message > 60:
                                self.state.update(status="LISTENING", error="No recent AIS messages. Coverage varies by area.")
                            try:
                                raw = await asyncio.wait_for(socket.recv(), timeout=1)
                            except TimeoutError:
                                continue
                            if not self.handle_message(raw):
                                return
                except (OSError, TimeoutError, WebSocketException):
                    # The context manager closes the old socket before backoff:
                    # reconnecting cannot overlap two account subscriptions.
                    self.state.update(status="RECONNECTING", error="Signal lost. Retrying automatically; positions may be old.")
                    self.emit()
                    if time.monotonic()-opened > 60:
                        delay = self.retry_delay
                    await asyncio.sleep(delay + random.uniform(0, min(delay,1)))
                    delay = min(delay*2, 60)
        finally:
            publisher.cancel()
            with suppress(asyncio.CancelledError):
                await publisher


def populate_demo(fleet, tick, now):
    boats = (("HAVEN",37),("NORTH STAR",70),("OUTPOST",30),("BLUE HOUR",60),("LITTLE TERN",36),("BRONZE",52))
    for index, (name, kind) in enumerate(boats):
        # Motion stays offshore, south of Genoa (Italy). Live traffic is never animated.
        bearing = 160+index*12+math.sin(tick*0.005)*5
        lat, lon = destination(fleet.lat,fleet.lon,fleet.radius*(0.18+index*0.125),bearing)
        fleet.ingest(dict(MessageType="ExtendedClassBPositionReport", MetaData=dict(MMSI=999000001+index),
            Message=dict(ExtendedClassBPositionReport=dict(Valid=True, Latitude=lat, Longitude=lon,
                Name="DEMO "+name, Type=kind, Sog=3+index*2,
                Cog=(bearing+(90 if math.cos(tick*0.005) >= 0 else -90)) % 360))), now)


def output(data):
    print(json.dumps(data, allow_nan=False, separators=(",", ":")), flush=True)


def locate():
    request = urllib.request.Request("https://ipwho.is/?fields=success,latitude,longitude,city",
                                     headers={"User-Agent":"omarchy-vessel/0.1"})
    with urllib.request.urlopen(request, timeout=12) as response:
        data = json.loads(response.read(65_536))
    if not isinstance(data,dict) or data.get("success") is not True or not coordinates(data.get("latitude"),data.get("longitude")):
        raise ValueError("Location unavailable")
    return data["latitude"], data["longitude"], (clean(data.get("city")) or "IP location")+" · approximate IP location"


def setup(message, state=None):
    output((state or dict(ships=[],total=0)) | dict(status="SETUP",error=message))
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search-city", metavar="NAME")
    parser.add_argument("--read-settings", action="store_true")
    parser.add_argument("--save-settings", action="store_true")
    parser.add_argument("--saved-settings", action="store_true")
    parser.add_argument("--prepare-runtime", action="store_true", help="Prepare the managed live dependency without connecting")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--auto-location", action="store_true")
    parser.add_argument("--latitude", type=float)
    parser.add_argument("--longitude", type=float)
    parser.add_argument("--radius", type=float, default=25)
    args = parser.parse_args(argv)
    if args.search_city is not None:
        try:
            from geocoding import search
            output(dict(ok=True, query=args.search_city, places=search(args.search_city)))
            return 0
        except (OSError, ValueError, TypeError):
            output(dict(ok=False, query=args.search_city, error="City search unavailable. Check your connection and try again, or use coordinates."))
            return 1
    city_name = ""
    if args.read_settings or args.save_settings:
        try:
            values = settings.save(json.loads(sys.stdin.readline(16_384))) if args.save_settings else settings.public_settings()
            output(dict(ok=True, settings=values))
            return 0
        except (OSError, ValueError, TypeError, AttributeError):
            output(dict(ok=False, error="Could not read or save settings. Check coordinates, range (1–200), and file permissions."))
            return 1
    if sys.version_info < (3,11):
        return setup("Python 3.11 or newer is required.")
    if args.saved_settings:
        try:
            saved = settings.read()
            city_name = saved["cityName"]
            args.radius, args.demo, args.auto_location = saved["radiusNm"], saved["demo"], saved["autoLocation"]
            args.latitude, args.longitude = (None,None) if args.auto_location else (saved["latitude"],saved["longitude"])
        except (OSError, ValueError, KeyError, TypeError):
            return setup("Could not read preferences. Open Settings and save them again.")
    if not number(args.radius,1,200):
        return setup("Radius must be between 1 and 200 nautical miles.")
    if not args.demo:
        try:
            key = settings.api_key()
        except (OSError, ValueError, TypeError, AttributeError):
            return setup("Could not read your API key. Open Settings and save it again.")
        if not key and not args.prepare_runtime:
            return setup("Open Settings to enter your AISStream API key, or try the Genoa (Italy) demo.")
        try:
            from runtime import ensure_runtime
            ensure_runtime(lambda status,error: output(dict(status=status,error=error,ships=[],total=0)))
        except Exception:
            return setup("Could not prepare Python. Check internet access, available disk space and Python venv support, then reconnect.")
        if args.prepare_runtime:
            output(dict(status="READY", error="", ships=[], total=0))
            return 0
    state = dict(status="LOCATING", error="", ships=[], total=0, demo=args.demo, radius=args.radius)
    output(state)
    if args.demo:
        lat, lon = GENOVA
        label = "Genoa (Italy) · simulated traffic"
    elif args.latitude is not None or args.longitude is not None:
        lat, lon = args.latitude, args.longitude
        if not coordinates(lat,lon):
            return setup("Set both latitude and longitude within valid ranges.", state)
        label = city_name or "Fixed position"
    elif args.auto_location:
        try:
            lat, lon, label = locate()
        except (OSError, ValueError):
            return setup("Geolocation unavailable. Configure latitude and longitude.", state)
    else:
        return setup("Set coordinates or enable approximate IP location.", state)
    state.update(latitude=lat, longitude=lon, location=label, status="DEMO" if args.demo else "CONNECTING")
    state["basemap"] = basemap.build(lat,lon,args.radius)
    fleet = Fleet(lat,lon,args.radius)
    if args.demo:
        tick = 0
        while True:
            populate_demo(fleet,tick,time.time())
            output(state | fleet.snapshot(time.time()))
            state.pop("basemap",None)
            tick += 1
            time.sleep(1)
    asyncio.run(Receiver(fleet,state,key,output).run())
    return 0


if __name__ == "__main__":
    def interrupt(_signal, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupt)
    try:
        sys.exit(main())
    except (KeyboardInterrupt, BrokenPipeError):
        sys.exit(0)
