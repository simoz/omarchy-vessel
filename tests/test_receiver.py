"""Real local WebSocket integration; no external AIS account is used."""

import asyncio
import json
import shutil
import ssl
import subprocess
import sys
import tempfile
import unittest
from contextlib import suppress
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from ais import Fleet
from receiver import Receiver
from websockets.asyncio.server import serve


class ReceiverTest(unittest.IsolatedAsyncioTestCase):
    async def test_binary_compression_subscription_and_clean_cancellation(self):
        observed = {}
        arrived = asyncio.Event()
        closed = asyncio.Event()

        async def peer(socket):
            observed["compression"] = socket.response.headers.get(
                "Sec-WebSocket-Extensions", ""
            )
            observed["subscription"] = json.loads(await socket.recv())
            await socket.send(
                json.dumps(dict(MessageType="SubscriptionConfirmation")).encode()
            )
            await socket.send(
                json.dumps(
                    dict(
                        MessageType="PositionReport",
                        MetaData=dict(MMSI=123456789, ShipName="LOCAL TEST"),
                        Message=dict(
                            PositionReport=dict(
                                Valid=True, Latitude=0, Longitude=0.1, Sog=4, Cog=90
                            )
                        ),
                    )
                ).encode()
            )
            await socket.wait_closed()
            closed.set()

        snapshots = []

        def output(snapshot):
            snapshots.append(snapshot)
            if snapshot["ships"]:
                arrived.set()

        async with serve(peer, "127.0.0.1", 0, compression="deflate") as server:
            url = f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}"
            receiver = Receiver(
                Fleet(0, 0, 25),
                {},
                "local-test-key",
                output,
                url=url,
                provider="aisstream",
            )
            task = asyncio.create_task(receiver.run())
            try:
                await asyncio.wait_for(arrived.wait(), 5)
                self.assertIn("permessage-deflate", observed["compression"])
                self.assertEqual(observed["subscription"]["APIKey"], "local-test-key")
                self.assertEqual(snapshots[-1]["ships"][0]["name"], "LOCAL TEST")
                self.assertEqual(snapshots[-1]["status"], "LIVE")
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            await asyncio.wait_for(closed.wait(), 3)

    async def test_rejection_is_terminal_and_redacts_server_message(self):
        count = 0

        async def peer(socket):
            nonlocal count
            count += 1
            await socket.recv()
            await socket.send(json.dumps(dict(error="invalid secret-key")))

        snapshots = []
        async with serve(peer, "127.0.0.1", 0) as server:
            receiver = Receiver(
                Fleet(0, 0, 25),
                {},
                "secret-key",
                snapshots.append,
                url=f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}",
                provider="aisstream",
            )
            await asyncio.wait_for(receiver.run(), 3)
        self.assertEqual(count, 1)
        self.assertEqual(snapshots[-1]["status"], "REJECTED")
        self.assertNotIn("secret-key", json.dumps(snapshots))

    async def test_reconnect_after_closed_transport(self):
        connections = 0
        active = 0
        peak = 0
        ready = asyncio.Event()

        async def peer(socket):
            nonlocal connections, active, peak
            connections += 1
            active += 1
            peak = max(active, peak)
            try:
                await socket.recv()
                if connections == 1:
                    await socket.close()
                else:
                    await socket.send(
                        json.dumps(dict(MessageType="SubscriptionConfirmation"))
                    )
                    ready.set()
                    await socket.wait_closed()
            finally:
                active -= 1

        snapshots = []
        async with serve(peer, "127.0.0.1", 0) as server:
            receiver = Receiver(
                Fleet(0, 0, 25),
                {},
                "test",
                snapshots.append,
                retry_delay=0.02,
                url=f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}",
                provider="aisstream",
            )
            task = asyncio.create_task(receiver.run())
            try:
                await asyncio.wait_for(ready.wait(), 3)
                self.assertEqual(connections, 2)
                self.assertEqual(peak, 1)
                self.assertTrue(
                    any(s.get("status") == "RECONNECTING" for s in snapshots)
                )
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    @unittest.skipUnless(
        shutil.which("openssl"), "openssl required for temporary TLS certificate"
    )
    async def test_untrusted_tls_certificate_cannot_receive_subscription(self):
        with tempfile.TemporaryDirectory() as directory:
            certificate, key = (
                Path(directory) / "certificate.pem",
                Path(directory) / "key.pem",
            )
            subprocess.run(
                [
                    "openssl",
                    "req",
                    "-x509",
                    "-newkey",
                    "rsa:2048",
                    "-nodes",
                    "-keyout",
                    str(key),
                    "-out",
                    str(certificate),
                    "-days",
                    "1",
                    "-subj",
                    "/CN=localhost",
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certificate, key)
            accepted = []
            retried = asyncio.Event()

            async def peer(socket):
                accepted.append(True)
                await socket.wait_closed()

            def output(snapshot):
                if snapshot.get("status") == "RECONNECTING":
                    retried.set()

            async with serve(peer, "127.0.0.1", 0, ssl=context) as server:
                receiver = Receiver(
                    Fleet(0, 0, 25),
                    {},
                    "never-send-this",
                    output,
                    url=f"wss://127.0.0.1:{server.sockets[0].getsockname()[1]}",
                )
                task = asyncio.create_task(receiver.run())
                try:
                    await asyncio.wait_for(retried.wait(), 5)
                    self.assertEqual(accepted, [])
                finally:
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task


if __name__ == "__main__":
    unittest.main()
