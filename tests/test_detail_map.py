"""Vector parsing, nautical alignment, viewport bounds and offline cache behaviour."""

import json
import math
import os
import random
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import detail_map as detail
import vector_tiles as mvt
from geometry import destination, distance_bearing


def integer(n):
    out = bytearray()
    while n > 127:
        out.append((n & 127) | 128)
        n >>= 7
    return bytes(out + bytes([n]))


def field(tag, value):
    if isinstance(value, int):
        return integer(tag << 3) + integer(value)
    return integer((tag << 3) | 2) + integer(len(value)) + value


def fixture(commands, kind=3, tags=b"", keys=(), values=()):
    feature = (
        field(3, kind)
        + field(4, b"".join(integer(n) for n in commands))
        + field(2, tags)
    )
    layer = field(15, 2) + field(1, b"water") + field(5, 4096) + field(2, feature)
    layer += b"".join(field(3, key) for key in keys)
    layer += b"".join(field(4, field(1, v)) for v in values)
    return field(3, layer)


def query(**changes):
    return (
        dict(lat=44.4056, lon=8.9463, radius=25, zoom=8, size=600, x=0, y=0) | changes
    )


class VectorTest(unittest.TestCase):
    def test_mutated_vector_inputs_fail_closed(self):
        generator = random.Random(20260919)
        seed = fixture([9, 0, 0, 26, 8192, 0, 0, 8192, 8191, 0, 15])
        for _ in range(1024):
            raw = bytearray(seed)
            for _ in range(generator.randint(1, 5)):
                operation = generator.randrange(3)
                index = generator.randrange(len(raw))
                if operation == 0:
                    raw[index] ^= 1 << generator.randrange(8)
                elif operation == 1:
                    del raw[index:]
                    if not raw:
                        break
                else:
                    raw[index:index] = generator.randbytes(generator.randint(1, 8))
            try:
                list(mvt.decode(bytes(raw)))
            except ValueError:
                pass  # Invalid bytes are expected; unexpected exception types fail.

    def test_closing_points_are_counted_and_repeated_closures_rejected(self):
        triangle = [9, 0, 0, 18, 2, 0, 0, 2]
        with patch.object(mvt, "MAX_POINTS", 3), self.assertRaises(ValueError):
            list(mvt.decode(fixture(triangle + [15])))
        with self.assertRaises(ValueError):
            list(mvt.decode(fixture(triangle + [15, 15])))
        self.assertEqual(len(list(mvt.decode(fixture(triangle + [15])))[0][-1][0]), 4)

    def test_polygon_commands_and_attributes(self):
        # Clockwise exterior; closure is preserved for the nonzero Canvas fill.
        data = fixture(
            [9, 0, 0, 26, 8192, 0, 0, 8192, 8191, 0, 15],
            tags=b"\0\0",
            keys=[b"class"],
            values=[b"ocean"],
        )
        layer, props, kind, extent, paths = list(mvt.decode(data))[0]
        self.assertEqual(
            (layer, props, kind, extent), ("water", {"class": "ocean"}, 3, 4096)
        )
        self.assertEqual(paths[0], [[0, 0], [4096, 0], [4096, 4096], [0, 4096], [0, 0]])

    def test_bad_network_data_is_rejected(self):
        for data in [
            b"\x1a\x7f",
            b"\x80" * 12,
            fixture([9, 0]),
            fixture([10, 0, 0]),
            fixture([0]),
            fixture([9, 0, 0], tags=b"\0"),
            fixture([9, 0, 0], tags=b"\0\0"),
        ]:
            with self.subTest(data=data[:20]), self.assertRaises(ValueError):
                list(mvt.decode(data))

    def test_geometry_budget_prevents_expansion(self):
        with patch.object(mvt, "MAX_POINTS", 2), self.assertRaises(ValueError):
            list(mvt.decode(fixture([9, 0, 0, 26, 2, 0, 0, 2, 1, 0, 15])))


class ViewportTest(unittest.TestCase):
    def test_projection_expansion_obeys_a_shared_point_budget(self):
        water = [("water", {}, 3, 1, [[[0, 0], [1, 0], [1, 1], [0, 1]]])]
        with patch.object(detail, "MAX_VIEW_POINTS", 8), self.assertRaises(ValueError):
            detail.project_tile((10, 537, 370), water, query())
        point = [("place", {"class": "city", "name": "City"}, 1, 4096, [[[0, 0]]])]
        budget = [1]
        detail.project_tile((10, 537, 370), point, query(), budget)
        with self.assertRaises(ValueError):
            detail.project_tile((10, 537, 370), point, query(), budget)

    def test_out_of_tile_labels_cannot_overflow_projection(self):
        point = [
            ("place", {"class": "city", "name": "Hostile"}, 1, 1, [[[0, 1_000_000]]])
        ]
        tile = detail.project_tile((7, 64, 64), point, query())
        self.assertEqual(tile["cities"], [])

    def test_more_zoom_requests_more_detailed_tiles(self):
        levels = [detail.tile_keys(query(zoom=z))[0][0] for z in (1, 2, 8, 64)]
        self.assertEqual(levels, sorted(set(levels)))
        self.assertLessEqual(levels[-1], 14)

    def test_visible_circle_covered_at_dateline_and_high_latitudes(self):
        for lat, lon in [(44.4, 8.9), (70, 179.99), (-70, -179.99), (0, 0)]:
            q = query(lat=lat, lon=lon, x=0.3, y=0.2)
            keys = set(detail.tile_keys(q))
            self.assertTrue(keys)
            self.assertLessEqual(len(keys), detail.MAX_TILES)
            z = next(iter(keys))[0]
            for angle in range(0, 360, 5):
                x = q["x"] + math.sin(math.radians(angle)) / q["zoom"]
                y = q["y"] - math.cos(math.radians(angle)) / q["zoom"]
                phi, lng = destination(
                    lat,
                    lon,
                    math.hypot(x, y) * q["radius"],
                    math.degrees(math.atan2(x, -y)),
                )
                col = int((lng + 180) / 360 * 2**z)
                row = int(detail.mercator_y(phi) * 2**z)
                self.assertIn((z, col, row), keys)
        self.assertEqual(detail.tile_keys(query(lat=89)), [])

    def test_invalid_requests_never_reach_network(self):
        for q in [
            None,
            {},
            query(lat=True),
            query(zoom=0),
            query(size=10**900),
            query(x=0.99, y=0.99),
            query(radius=float("nan")),
        ]:
            with patch.object(detail, "fetch") as fetch, self.assertRaises(ValueError):
                detail.build(q)
            fetch.assert_not_called()

    def test_vector_points_use_exactly_the_ais_projection(self):
        q = query()
        key = detail.tile_keys(q)[0]
        features = [("waterway", {}, 2, 4096, [[[100, 200], [300, 400]]])]
        result = detail.project_tile(key, features, q)
        for pixel, actual in zip(features[0][-1][0], result["waterways"][0]):
            lng, phi = detail.tile_lonlat(
                key[0], key[1] + pixel[0] / 4096, key[2] + pixel[1] / 4096
            )
            distance, bearing = distance_bearing(q["lat"], q["lon"], phi, lng)
            self.assertAlmostEqual(
                actual[0],
                math.sin(math.radians(bearing)) * distance / q["radius"],
                places=7,
            )
            self.assertAlmostEqual(
                actual[1],
                -math.cos(math.radians(bearing)) * distance / q["radius"],
                places=7,
            )


class CacheTest(unittest.TestCase):
    def test_invalid_catalog_is_evicted_instead_of_poisoning_future_requests(self):
        for raw in (b"{", b'{"tiles": {"0":"wrong"}}', b'{"tiles":[]}'):
            with tempfile.TemporaryDirectory() as tmp:
                source = detail.Source(Path(tmp))
                (Path(tmp) / "catalog.json").write_bytes(raw)
                with (
                    patch.object(detail, "fetch") as fetch,
                    self.assertRaises(ValueError),
                ):
                    source.template()
                fetch.assert_not_called()
                self.assertFalse((Path(tmp) / "catalog.json").exists())

    def test_failed_cache_write_preserves_prior_entry_and_private_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tiles" / "one.pbf"
            detail.write_atomic(path, b"old")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
            with (
                patch.object(detail.os, "replace", side_effect=OSError("disk full")),
                self.assertRaises(OSError),
            ):
                detail.write_atomic(path, b"new")
            self.assertEqual(path.read_bytes(), b"old")
            self.assertEqual(list(path.parent.glob(".tile-*")), [])

    def test_cached_tiles_and_stale_offline_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = detail.Source(Path(tmp))
            with patch.object(detail, "fetch", return_value=b"tile") as fetch:
                self.assertEqual(
                    source.cached("https://example.org/tile", "one.pbf"), b"tile"
                )
                self.assertEqual(
                    source.cached("https://example.org/tile", "one.pbf"), b"tile"
                )
                self.assertEqual(fetch.call_count, 1)
            os.utime(Path(tmp) / "one.pbf", (0, 0))
            with patch.object(detail, "fetch", side_effect=OSError("offline")) as fetch:
                self.assertEqual(
                    source.cached("https://example.org/tile", "one.pbf"), b"tile"
                )
                with self.assertRaises(OSError):
                    source.cached("https://example.org/other", "two.pbf")
                self.assertEqual(fetch.call_count, 1)

    def test_untrusted_catalog_cannot_choose_a_host_or_path(self):
        for url in [
            "http://tiles.openfreemap.org/{z}/{x}/{y}.pbf",
            "https://example.org/{z}/{x}/{y}.pbf",
            "https://tiles.openfreemap.org/planet/../../{z}/{x}/{y}.pbf",
        ]:
            source = detail.Source(Path("/unused"))
            with (
                patch.object(
                    source, "cached", return_value=json.dumps({"tiles": [url]}).encode()
                ),
                self.assertRaises(ValueError),
            ):
                source.template()

    def test_cache_eviction_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = detail.Source(Path(tmp))
            for i in range(4):
                p = Path(tmp) / f"{i}.pbf"
                p.write_bytes(b"1234")
                os.utime(p, (time.time() + i, time.time() + i))
            with (
                patch.object(detail, "CACHE_LIMIT", 12),
                patch.object(detail, "CACHE_TARGET", 8),
            ):
                source.trim()
            self.assertEqual(
                {p.name for p in Path(tmp).glob("*.pbf")}, {"2.pbf", "3.pbf"}
            )


class MapNetworkTest(unittest.TestCase):
    def test_initial_and_redirect_urls_are_confined_to_map_provider(self):
        handler = detail.MapRedirectHandler()
        request = Request(detail.CATALOG)
        for url in (
            "http://tiles.openfreemap.org/planet",
            "file:///etc/passwd",
            "https://localhost/",
            "https://tiles.openfreemap.org:444/planet",
            "https://user:password@tiles.openfreemap.org/planet",
        ):
            with (
                patch.object(detail, "build_opener") as opener,
                self.assertRaises(ValueError),
            ):
                detail.fetch(url)
            opener.assert_not_called()
            with self.assertRaises(ValueError):
                handler.redirect_request(request, None, 302, "Found", {}, url)
        same_host = "https://tiles.openfreemap.org/planet/new"
        redirect = handler.redirect_request(request, None, 302, "Found", {}, same_host)
        self.assertEqual(redirect.full_url, same_host)

    def test_map_response_read_is_bounded_and_identifies_the_application(self):
        with patch.object(detail, "build_opener") as opener:
            response = opener.return_value.open.return_value.__enter__.return_value
            response.read.return_value = b"x" * 1025
            with self.assertRaises(ValueError):
                detail.fetch(detail.CATALOG, limit=1024)
            response.read.assert_called_once_with(1025)
            request = opener.return_value.open.call_args.args[0]
            self.assertIn("omarchy-vessel", request.get_header("User-agent"))
            self.assertIsNone(request.get_header("Authorization"))


if __name__ == "__main__":
    unittest.main()
