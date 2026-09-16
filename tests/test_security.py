"""Adversarial-input and credential-boundary checks; no external network calls."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import ais
import geometry
import network
import settings
from receiver import Receiver


class UntrustedInputTest(unittest.TestCase):
    def test_huge_numbers_cannot_crash_or_poison_the_fleet(self):
        fleet = ais.Fleet(0, 0, 25)
        receiver = Receiver(fleet, {}, "test-key", lambda _: None)
        for field in ("Latitude", "Longitude", "Sog", "Cog"):
            body = dict(Valid=True, Latitude=0, Longitude=0.1, Sog=4, Cog=90)
            body[field] = 10**400
            envelope = dict(
                MessageType="PositionReport",
                MetaData=dict(MMSI=123456789),
                Message=dict(PositionReport=body),
            )
            self.assertTrue(receiver.handle_message(json.dumps(envelope)))
            json.dumps(fleet.snapshot(0), allow_nan=False)
        self.assertFalse(geometry.coordinates(10**400, 0))

    def test_invalid_text_and_deep_json_do_not_break_receiver(self):
        self.assertEqual(ais.clean({"name": "not text"}), "")
        self.assertEqual(ais.clean("  BOAT\x00@@ "), "BOAT")
        receiver = Receiver(ais.Fleet(0, 0, 25), {}, "test", lambda _: None)
        for raw in (b"\xff", "{", "null", "[]", "[" * 3000 + "0" + "]" * 3000):
            self.assertTrue(receiver.handle_message(raw))

    def test_location_http_and_credential_urls_are_rejected_before_network(self):
        with patch.object(network, "build_opener") as opener:
            for url in (
                "http://example.com",
                "file:///etc/passwd",
                "https://user:secret@example.com",
            ):
                with self.assertRaises(ValueError):
                    network.fetch_json(url, max_bytes=1024)
            opener.assert_not_called()

    def test_https_redirect_cannot_downgrade_location_privacy(self):
        handler = network.HTTPSRedirectHandler()
        request = Request("https://example.com/cities?q=Genoa")
        with self.assertRaises(ValueError):
            handler.redirect_request(
                request, None, 302, "Found", {}, "http://example.com/cities"
            )
        redirect = handler.redirect_request(
            request, None, 302, "Found", {}, "https://example.com/new"
        )
        self.assertEqual(redirect.full_url, "https://example.com/new")

    def test_location_response_size_is_bounded(self):
        with patch.object(network, "build_opener") as opener:
            response = opener.return_value.open.return_value.__enter__.return_value
            response.read.return_value = b"x" * 1025
            with self.assertRaises(ValueError):
                network.fetch_json("https://example.com", max_bytes=1024)
            response.read.assert_called_once_with(1025)


class SettingsBoundaryTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.environment = patch.dict(
            os.environ,
            {"XDG_CONFIG_HOME": self.directory.name, "AISSTREAM_API_KEY": ""},
        )
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.directory.cleanup()

    def test_public_settings_allow_only_declared_fields(self):
        settings.save(dict(apiKey="private-key"))
        saved = settings.read() | {"futurePrivateField": "private-value"}
        settings.path().write_text(json.dumps(saved))
        public = settings.public_settings()
        self.assertEqual(set(public), set(settings.DEFAULTS) | {"hasApiKey"})
        self.assertNotIn("private-", json.dumps(public))

    def test_corrupt_saved_values_fail_validation_and_can_be_repaired(self):
        settings.save(dict(apiKey="private-key"))
        saved = settings.read() | {"radiusNm": 10**400}
        settings.path().write_text(json.dumps(saved))
        with self.assertRaises(ValueError):
            settings.read()
        settings.save(dict(radiusNm="25"))
        self.assertEqual(settings.api_key(), "private-key")
        self.assertEqual(settings.read()["radiusNm"], 25)

    def test_huge_edits_and_invalid_types_do_not_replace_credentials(self):
        settings.save(dict(apiKey="original"))
        for values in (
            dict(radiusNm=10**400),
            dict(latitude=True),
            dict(latitude=[]),
            dict(apiKey=None),
        ):
            with self.assertRaises(ValueError):
                settings.save(values)
            self.assertEqual(settings.api_key(), "original")

    def test_settings_file_size_is_bounded(self):
        settings.save({})
        settings.path().write_bytes(b" " * (settings.MAX_SETTINGS_BYTES + 1))
        with self.assertRaises(ValueError):
            settings.read()

    def test_failed_atomic_replacement_preserves_old_key_and_cleans_temp_file(self):
        settings.save(dict(apiKey="original"))
        with patch.object(settings.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                settings.save(dict(apiKey="replacement"))
        self.assertEqual(settings.api_key(), "original")
        self.assertEqual(list(settings.path().parent.glob(".settings-*")), [])
        self.assertEqual(settings.path().stat().st_mode & 0o777, 0o600)

    def test_environment_key_uses_the_same_validation(self):
        with patch.dict(os.environ, {"AISSTREAM_API_KEY": "bad\nkey"}):
            with self.assertRaises(ValueError):
                settings.api_key()


if __name__ == "__main__":
    unittest.main()
