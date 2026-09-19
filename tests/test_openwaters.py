"""OpenWaters protocol, credential isolation and snapshot-age regressions."""

import asyncio
import json
import os
import sys
import tempfile
import time
import unittest
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import settings
from ais import Fleet, attribution_text
from geometry import bounding_boxes
from receiver import Receiver
from websockets.asyncio.server import serve


def event(kind="PositionReport", age=0, source="aishub", attribution="AISHub", **body):
    return dict(
        type="event",
        msg_type=kind,
        mmsi=123456789,
        time=datetime.fromtimestamp(time.time() - age, timezone.utc).isoformat(),
        source=source,
        attribution=attribution,
        message=dict(Valid=True, Latitude=0, Longitude=0.1, Sog=4, Cog=90) | body,
    )


class OpenWatersTest(unittest.IsolatedAsyncioTestCase):
    def test_overlapping_attributions_keep_full_credit_in_either_arrival_order(self):
        provider = "Open Waters AIS (https://openwaters.io/ais/)"
        combined = provider + ". AISHub (https://www.aishub.net)"
        for credits in ([provider, combined], [combined, provider]):
            with self.subTest(credits=credits):
                fleet = Fleet(0, 0, 25)
                receiver = Receiver(fleet, {}, "", lambda _: None)
                for index, credit in enumerate(credits):
                    receiver.handle_message(
                        json.dumps(event(source=f"source{index}", attribution=credit))
                    )
                self.assertEqual(
                    fleet.snapshot(time.time())["ships"][0]["attribution"], combined
                )

    def test_distinct_licenses_and_similar_source_names_are_preserved(self):
        credits = [
            "Source",
            "Source extended",
            "Source. License A",
            "Source. License B",
        ]
        self.assertEqual(
            attribution_text(credits),
            "Source extended · Source. License A · Source. License B",
        )
        self.assertEqual(attribution_text(["AISHub", "AISHub"]), "AISHub")

    async def test_snapshot_subscription_anonymous_and_authenticated(self):
        for token in ("", "openwaters-test-token"):
            with self.subTest(token=bool(token)):
                observed, snapshots = {}, []
                arrived = asyncio.Event()

                async def peer(socket):
                    observed["auth"] = socket.request.headers.get("Authorization")
                    observed["subscription"] = json.loads(await socket.recv())
                    await socket.send(
                        json.dumps(dict(type="welcome", role="anonymous"))
                    )
                    await socket.send(json.dumps(event(age=400)))
                    await socket.send(
                        json.dumps(event("ShipStaticData", Name="OLD CONTACT"))
                    )
                    await socket.wait_closed()

                def output(snapshot):
                    snapshots.append(snapshot)
                    if snapshot["ships"]:
                        arrived.set()

                async with serve(peer, "127.0.0.1", 0) as server:
                    receiver = Receiver(
                        Fleet(0, 0, 25),
                        {},
                        token,
                        output,
                        url=f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}",
                    )
                    task = asyncio.create_task(receiver.run())
                    try:
                        await asyncio.wait_for(arrived.wait(), 5)
                        sub = observed["subscription"]
                        self.assertEqual(
                            sub,
                            dict(
                                type="subscribe",
                                snapshot=True,
                                bbox=[a + b for a, b in bounding_boxes(0, 0, 25)],
                            ),
                        )
                        self.assertEqual(
                            observed["auth"], "Bearer " + token if token else None
                        )
                        ship = snapshots[-1]["ships"][0]
                        self.assertTrue(ship["stale"])
                        self.assertEqual(ship["name"], "OLD CONTACT")
                        self.assertEqual(ship["attribution"], "AISHub")
                        self.assertNotIn("openwaters-test-token", json.dumps(snapshots))
                    finally:
                        task.cancel()
                        with suppress(asyncio.CancelledError):
                            await task

    async def test_http_authentication_rejection_is_terminal_and_redacted(self):
        attempts = []
        snapshots = []

        def reject(connection, request):
            attempts.append(request.headers.get("Authorization"))
            return connection.respond(401, "invalid private-token")

        async def peer(socket):
            self.fail("Rejected handshake must not open a stream")

        async with serve(peer, "127.0.0.1", 0, process_request=reject) as server:
            receiver = Receiver(
                Fleet(0, 0, 25),
                {},
                "private-token",
                snapshots.append,
                url=f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}",
            )
            await asyncio.wait_for(receiver.run(), 3)
        self.assertEqual(attempts, ["Bearer private-token"])
        self.assertEqual(snapshots[-1]["status"], "REJECTED")
        self.assertNotIn("private-token", json.dumps(snapshots))

    def test_replay_does_not_overwrite_new_position_or_revive_expired_position(self):
        fleet = Fleet(0, 0, 25)
        receiver = Receiver(fleet, {}, "", lambda _: None)
        receiver.handle_message(json.dumps(event(Longitude=0.2)))
        receiver.handle_message(json.dumps(event(age=400, Longitude=0.1)))
        self.assertEqual(fleet.snapshot(time.time())["ships"][0]["longitude"], 0.2)
        fleet.ships.clear()
        receiver.handle_message(json.dumps(event(age=1801)))
        receiver.handle_message(json.dumps(event("ShipStaticData", Name="EXPIRED")))
        self.assertEqual(fleet.snapshot(time.time())["ships"], [])

    def test_attribution_retains_both_static_and_position_sources(self):
        fleet = Fleet(0, 0, 25)
        receiver = Receiver(fleet, {}, "", lambda _: None)
        receiver.handle_message(json.dumps(event()))
        receiver.handle_message(
            json.dumps(
                event(
                    "ShipStaticData",
                    Name="BOAT",
                    source="digitraffic",
                    attribution="Source: Fintraffic / digitraffic.fi, license CC 4.0 BY.",
                )
            )
        )
        credit = fleet.snapshot(time.time())["ships"][0]["attribution"]
        self.assertIn("AISHub", credit)
        self.assertIn("Fintraffic", credit)

    def test_welcome_without_traffic_and_safe_terminal_rejection(self):
        receiver = Receiver(Fleet(0, 0, 25), {}, "private-token", lambda _: None)
        receiver.handle_message('{"type":"welcome"}')
        self.assertEqual(receiver.state["status"], "LISTENING")
        for value in (None, [], {}, "AidsToNavigationReport"):
            receiver.handle_message(json.dumps(dict(type="event", msg_type=value)))
        self.assertFalse(
            receiver.handle_message('{"type":"error","error":"private-token invalid"}')
        )
        self.assertEqual(receiver.state["status"], "REJECTED")
        self.assertNotIn("private-token", json.dumps(receiver.state))


class ProviderSettingsTest(unittest.TestCase):
    def test_legacy_key_is_retained_but_never_used_for_openwaters(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                XDG_CONFIG_HOME=directory,
                AISSTREAM_API_KEY="environment-aisstream",
            ),
        ):
            self.assertEqual(settings.read()["provider"], "openwaters")
            self.assertEqual(settings.api_key("openwaters"), "")
            settings.path().parent.mkdir()
            settings.path().write_text(json.dumps(dict(apiKey="legacy-aisstream")))
            self.assertEqual(settings.read()["provider"], "openwaters")
            settings.save(dict(provider="openwaters", openwatersKey="ow-token"))
            settings.save(dict(provider="aisstream", apiKey=""))
            self.assertEqual(settings.api_key("aisstream"), "legacy-aisstream")
            self.assertEqual(settings.api_key("openwaters"), "ow-token")
            settings.save(dict(provider="openwaters", openwatersKey=""))
            self.assertEqual(settings.api_key("openwaters"), "ow-token")
            self.assertNotIn("ow-token", json.dumps(settings.public_settings()))
            self.assertNotIn("legacy-aisstream", json.dumps(settings.public_settings()))
            for invalid in (dict(provider="other"), dict(openwatersKey="bad\nvalue")):
                with self.assertRaises(ValueError):
                    settings.save(invalid)
