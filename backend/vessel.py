#!/usr/bin/env python3
"""Vessel's JSON-lines receiver. Only live mode needs the managed WebSocket dependency."""

import argparse
import asyncio
import json
import math
import signal
import sys
import time

import basemap
import settings
from ais import Fleet, clean
from geometry import GENOA, coordinates, destination, number
from network import fetch_json
from receiver import Receiver


def populate_demo(fleet, tick, now):
    boats = (
        ("HAVEN", 37),
        ("NORTH STAR", 70),
        ("OUTPOST", 30),
        ("BLUE HOUR", 60),
        ("LITTLE TERN", 36),
        ("BRONZE", 52),
    )
    for index, (name, kind) in enumerate(boats):
        # Motion stays offshore, south of Genoa (Italy). Live traffic is never animated.
        bearing = 160 + index * 12 + math.sin(tick * 0.005) * 5
        lat, lon = destination(
            fleet.lat, fleet.lon, fleet.radius * (0.18 + index * 0.125), bearing
        )
        fleet.ingest(
            dict(
                MessageType="ExtendedClassBPositionReport",
                MetaData=dict(MMSI=999000001 + index),
                Message=dict(
                    ExtendedClassBPositionReport=dict(
                        Valid=True,
                        Latitude=lat,
                        Longitude=lon,
                        Name="DEMO " + name,
                        Type=kind,
                        Sog=3 + index * 2,
                        Cog=(bearing + (90 if math.cos(tick * 0.005) >= 0 else -90))
                        % 360,
                    )
                ),
            ),
            now,
        )


def output(data):
    print(json.dumps(data, allow_nan=False, separators=(",", ":")), flush=True)


def locate():
    data = fetch_json(
        "https://ipwho.is/?fields=success,latitude,longitude,city", max_bytes=65_536
    )
    if (
        not isinstance(data, dict)
        or data.get("success") is not True
        or not coordinates(data.get("latitude"), data.get("longitude"))
    ):
        raise ValueError("Location unavailable")
    return (
        data["latitude"],
        data["longitude"],
        (clean(data.get("city")) or "IP location") + " · approximate IP location",
    )


def setup(message, state=None):
    output((state or dict(ships=[], total=0)) | dict(status="SETUP", error=message))
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search-city", metavar="NAME")
    parser.add_argument("--read-settings", action="store_true")
    parser.add_argument("--save-settings", action="store_true")
    parser.add_argument("--saved-settings", action="store_true")
    parser.add_argument(
        "--prepare-runtime",
        action="store_true",
        help="Prepare the managed live dependency without connecting",
    )
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--auto-location", action="store_true")
    parser.add_argument("--latitude", type=float)
    parser.add_argument("--longitude", type=float)
    parser.add_argument("--radius", type=float, default=25)
    args = parser.parse_args(argv)
    if args.search_city is not None:
        try:
            from geocoding import search

            output(
                dict(ok=True, query=args.search_city, places=search(args.search_city))
            )
            return 0
        except (OSError, ValueError, TypeError, RecursionError):
            output(
                dict(
                    ok=False,
                    query=args.search_city,
                    error="City search unavailable. Check your connection and try again, or use coordinates.",
                )
            )
            return 1
    city_name = ""
    if args.read_settings or args.save_settings:
        try:
            values = (
                settings.save(
                    json.loads(sys.stdin.readline(settings.MAX_SETTINGS_BYTES + 1))
                )
                if args.save_settings
                else settings.public_settings()
            )
            output(dict(ok=True, settings=values))
            return 0
        except (OSError, ValueError, TypeError, AttributeError, RecursionError):
            output(
                dict(
                    ok=False,
                    error="Could not read or save settings. Check coordinates, range (1–200), and file permissions.",
                )
            )
            return 1
    if sys.version_info < (3, 11):
        return setup("Python 3.11 or newer is required.")
    if args.saved_settings:
        try:
            saved = settings.read()
            city_name = saved["cityName"]
            args.radius, args.demo, args.auto_location = (
                saved["radiusNm"],
                saved["demo"],
                saved["autoLocation"],
            )
            args.latitude, args.longitude = (
                (None, None)
                if args.auto_location
                else (saved["latitude"], saved["longitude"])
            )
        except (OSError, ValueError, KeyError, TypeError):
            return setup(
                "Could not read preferences. Open Settings and save them again."
            )
    if not number(args.radius, 1, 200):
        return setup("Radius must be between 1 and 200 nautical miles.")
    if not args.demo:
        try:
            key = settings.api_key()
        except (OSError, ValueError, TypeError, AttributeError, RecursionError):
            return setup(
                "Could not read your API key. Open Settings and save it again."
            )
        if not key and not args.prepare_runtime:
            return setup(
                "Open Settings to enter your AISStream API key, or try the Genoa (Italy) demo."
            )
        try:
            from runtime import ensure_runtime

            ensure_runtime(
                lambda status, error: output(
                    dict(status=status, error=error, ships=[], total=0)
                )
            )
        except Exception:
            # Installer failures must use a stable, credential-free UI message.
            return setup(
                "Could not prepare Python. Check internet access, available disk space and Python venv support, then reconnect."
            )
        if args.prepare_runtime:
            output(dict(status="READY", error="", ships=[], total=0))
            return 0
    state = dict(
        status="LOCATING",
        error="",
        ships=[],
        total=0,
        demo=args.demo,
        radius=args.radius,
    )
    output(state)
    if args.demo:
        lat, lon = GENOA
        label = "Genoa (Italy) · simulated traffic"
    elif args.latitude is not None or args.longitude is not None:
        lat, lon = args.latitude, args.longitude
        if not coordinates(lat, lon):
            return setup("Set both latitude and longitude within valid ranges.", state)
        label = city_name or "Fixed position"
    elif args.auto_location:
        try:
            lat, lon, label = locate()
        except (OSError, ValueError):
            return setup(
                "Geolocation unavailable. Choose a city or enter coordinates in Settings.",
                state,
            )
    else:
        return setup("Set coordinates or enable approximate IP location.", state)
    state.update(
        latitude=lat,
        longitude=lon,
        location=label,
        status="DEMO" if args.demo else "CONNECTING",
    )
    state["basemap"] = basemap.build(lat, lon, args.radius)
    fleet = Fleet(lat, lon, args.radius)
    if args.demo:
        tick = 0
        while True:
            populate_demo(fleet, tick, time.time())
            output(state | fleet.snapshot(time.time()))
            state.pop("basemap", None)
            tick += 1
            time.sleep(1)
    asyncio.run(Receiver(fleet, state, key, output).run())
    return 0


if __name__ == "__main__":

    def interrupt(_signal, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    try:
        sys.exit(main())
    except (KeyboardInterrupt, BrokenPipeError):
        sys.exit(0)
