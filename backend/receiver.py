"""Own one AIS connection, with bounded messages and cancellable retries."""

import asyncio
import json
import logging
import random
import time
from contextlib import suppress

from ais import MESSAGE_TYPES
from geometry import bounding_boxes


class Receiver:
    URLS = {
        "openwaters": "wss://ais.openwaters.io/v1/stream",
        "aisstream": "wss://stream.aisstream.io/v0/stream",
    }

    def __init__(
        self,
        fleet,
        state,
        key,
        output,
        *,
        provider="openwaters",
        url=None,
        retry_delay=2,
    ):
        self.fleet, self.state, self.key, self.output = fleet, state, key, output
        self.provider = provider
        self.url, self.retry_delay = url or self.URLS[provider], retry_delay
        self.confirmed, self.last_message = False, time.monotonic()

    def emit(self):
        self.output(self.state | self.fleet.snapshot(time.time()))
        self.state.pop("basemap", None)

    def handle_message(self, raw):
        try:
            envelope = json.loads(raw)
        except (ValueError, UnicodeError, RecursionError):
            return True
        if not isinstance(envelope, dict):
            return True
        # Provider error text may include the submitted key. Never forward it.
        if "error" in envelope or "Error" in envelope:
            self.state.update(
                status="REJECTED",
                error=(
                    "OpenWaters rejected the subscription. Check your token, coverage radius and connection limits."
                    if self.provider == "openwaters"
                    else "AISStream rejected the subscription. Check your key and account connection limit."
                ),
            )
            self.emit()
            return False
        if self.provider == "openwaters":
            if envelope.get("type") == "welcome":
                self.confirmed, self.last_message = True, time.monotonic()
                self.state.update(status="LISTENING", error="")
                return True
            if envelope.get("type") != "event":
                return True
            kind = envelope.get("msg_type")
            if not isinstance(kind, str) or kind not in MESSAGE_TYPES:
                return True
            envelope = dict(
                MessageType=kind,
                MetaData=dict(MMSI=envelope.get("mmsi"), time_utc=envelope.get("time")),
                Message={kind: envelope.get("message")},
                source=envelope.get("source"),
                attribution=envelope.get("attribution"),
            )
        kind = envelope.get("MessageType")
        if kind == "SubscriptionConfirmation" or kind in MESSAGE_TYPES:
            self.confirmed, self.last_message = True, time.monotonic()
            self.state.update(
                status="LISTENING" if kind == "SubscriptionConfirmation" else "LIVE",
                error="",
            )
            if kind != "SubscriptionConfirmation":
                self.fleet.ingest(envelope, time.time())
        return True

    async def publish(self):
        while True:
            self.emit()
            await asyncio.sleep(1)

    async def listen(self, socket):
        """Subscribe immediately, then consume reports until rejected or disconnected."""
        opened = time.monotonic()
        self.confirmed, self.last_message = False, opened
        boxes = bounding_boxes(self.fleet.lat, self.fleet.lon, self.fleet.radius)
        subscription = dict(
            APIKey=self.key,
            BoundingBoxes=boxes,
            FilterMessageTypes=MESSAGE_TYPES,
        )
        if self.provider == "openwaters":
            subscription = dict(
                type="subscribe", bbox=[a + b for a, b in boxes], snapshot=True
            )
        await socket.send(json.dumps(subscription))
        while True:
            now = time.monotonic()
            if not self.confirmed and now - opened > 20:
                raise TimeoutError("Subscription deadline")
            if self.confirmed and now - self.last_message > 60:
                self.state.update(
                    status="LISTENING",
                    error="No recent AIS messages. Coverage varies by area.",
                )
            try:
                raw = await asyncio.wait_for(socket.recv(), timeout=1)
            except TimeoutError:
                continue
            if not self.handle_message(raw):
                return False

    async def run(self):
        # The library owns TLS, framing, compression, ping/pong and cancellation.
        # A private logger prevents server error text or payloads leaking a key.
        from websockets.asyncio.client import connect
        from websockets.exceptions import InvalidStatus, WebSocketException

        class DirectConnection(connect):
            def process_redirect(self, error):
                # AISStream's key is in the first message, not an HTTP header.
                # Header stripping alone cannot protect it after a redirect.
                # Only the explicitly configured provider may receive a subscription.
                return error

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
                    async with DirectConnection(
                        self.url,
                        additional_headers={"Authorization": "Bearer " + self.key}
                        if self.provider == "openwaters" and self.key
                        else None,
                        compression="deflate",
                        proxy=None,
                        open_timeout=15,
                        close_timeout=3,
                        ping_interval=20,
                        ping_timeout=15,
                        max_size=1_048_576,
                        logger=logger,
                    ) as socket:
                        opened = time.monotonic()
                        if not await self.listen(socket):
                            return
                except (OSError, TimeoutError, WebSocketException) as error:
                    if isinstance(
                        error, InvalidStatus
                    ) and error.response.status_code in (401, 403):
                        # Authentication can fail before a WebSocket exists.
                        # Reuse the redacted, terminal subscription error.
                        self.handle_message('{"error":true}')
                        return
                    # The context manager closes the old socket before backoff:
                    # reconnecting cannot overlap two account subscriptions.
                    self.state.update(
                        status="RECONNECTING",
                        error="Signal lost. Retrying automatically; positions may be old.",
                    )
                    self.emit()
                    if time.monotonic() - opened > 60:
                        delay = self.retry_delay
                    await asyncio.sleep(delay + random.uniform(0, min(delay, 1)))
                    delay = min(delay * 2, 60)
        finally:
            publisher.cancel()
            with suppress(asyncio.CancelledError):
                await publisher
