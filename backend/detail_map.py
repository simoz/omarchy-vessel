"""On-demand OpenFreeMap vectors, cached and projected like AIS contacts.

A request describes only the current viewport. Complete batches replace the
previous map atomically; network/cache failures leave the offline map available.
"""

import hashlib
import json
import math
import os
import re
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from basemap import clip_line, clip_ring
from geometry import (
    EARTH_NM,
    bounding_boxes,
    coordinates,
    destination,
    distance_bearing,
    number,
)
from network import USER_AGENT, HTTPSRedirectHandler, require_https
from vector_tiles import MAX_BYTES, decode

CATALOG = "https://tiles.openfreemap.org/planet"
# Keep map work bounded independently of the AIS receiver process.
MAX_TILES = 36
DOWNLOAD_WORKERS = 4
MAX_VIEW_POINTS = 300_000
FETCH_TIMEOUT_SECONDS = 10
RETRY_DELAY_SECONDS = 30
MIN_TILE_ZOOM = 7
MAX_TILE_ZOOM = 14
TILE_SIZE_PIXELS = 512
CHART_MARGIN_PIXELS = 24
VIEW_PADDING = 1.15
MERCATOR_MAX_LATITUDE = 85.05112878
CACHE_LIMIT = 128 << 20
CACHE_TARGET = 96 << 20
CACHE_TTL_SECONDS = 7 * 86400
TEMPLATE = re.compile(
    r"https://tiles\.openfreemap\.org/planet/[a-zA-Z0-9_-]+/\{z\}/\{x\}/\{y\}\.pbf"
)


def cache_root():
    base = Path(os.environ.get("XDG_CACHE_HOME", ""))
    if not base.is_absolute():
        base = Path.home() / ".cache"
    return base / "omarchy-vessel" / "tiles"


def require_map_url(url):
    """Tile metadata and redirects cannot move requests to another service."""
    require_https(url)
    parts = urlsplit(url)
    if parts.hostname != "tiles.openfreemap.org" or parts.port not in (None, 443):
        raise ValueError("Unexpected map host")


class MapRedirectHandler(HTTPSRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        require_map_url(new_url)
        return super().redirect_request(
            request, response, code, message, headers, new_url
        )


def fetch(url, limit=MAX_BYTES):
    require_map_url(url)
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with build_opener(MapRedirectHandler()).open(
        request, timeout=FETCH_TIMEOUT_SECONDS
    ) as response:
        raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Map response too large")
    return raw


def write_atomic(path, data):
    """Publish complete cache entries; readers must never see a partial tile."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".tile-")
    try:
        with os.fdopen(fd, "wb") as target:
            target.write(data)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


class Source:
    """Fetch versioned tiles and retain useful cached data when the network fails.

    Each viewport uses a short-lived helper. The backoff marker shares the retry
    delay across those helpers, while atomic writes protect concurrent readers.
    """

    def __init__(self, root=None):
        self.root = root if root is not None else cache_root()
        self.failed = self.root / "backoff"

    def cached(self, url, name, limit=MAX_BYTES):
        """Prefer a fresh cache entry; reuse a stale one if refresh fails."""
        path = self.root / name
        old = None
        try:
            if path.stat().st_size <= limit:
                # Bound the read itself, even if the file changes after stat().
                with path.open("rb") as cached_file:
                    old = cached_file.read(limit + 1)
                if len(old) > limit:
                    old = None
                    raise ValueError("Cached map response too large")
                if time.time() - path.stat().st_mtime < CACHE_TTL_SECONDS:
                    return old
        except (OSError, ValueError):
            pass
        try:
            if (
                self.failed.exists()
                and time.time() - self.failed.stat().st_mtime < RETRY_DELAY_SECONDS
            ):
                raise OSError("Map service backing off")
            raw = fetch(url, limit)
            write_atomic(path, raw)
            return raw
        except (OSError, ValueError):
            try:
                write_atomic(self.failed, b"")
            except OSError:
                pass
            if old is not None:
                return old
            raise

    def template(self):
        """Accept only the expected provider and versioned tile URL structure."""
        try:
            data = json.loads(self.cached(CATALOG, "catalog.json", 256 << 10))
            templates = data.get("tiles", []) if isinstance(data, dict) else []
            if (
                not isinstance(templates, list)
                or not templates
                or not isinstance(templates[0], str)
                or not TEMPLATE.fullmatch(templates[0])
            ):
                raise ValueError("Unsupported map source")
        except (ValueError, RecursionError):
            # A bad response must not poison map loading for the seven-day TTL.
            (self.root / "catalog.json").unlink(missing_ok=True)
            raise ValueError("Invalid map catalog") from None
        return templates[0]

    def tile(self, template, key):
        """Decode one (zoom, column, row) tile; discard corrupt cache entries."""
        z, x, y = key
        url = template.format(z=z, x=x, y=y)
        # The full URL includes the dataset version, so updates cannot mix tiles.
        name = hashlib.sha256(url.encode()).hexdigest() + ".pbf"
        raw = self.cached(url, name)
        try:
            return list(decode(raw))
        except (ValueError, UnicodeError):
            (self.root / name).unlink(missing_ok=True)
            raise

    def trim(self):
        """Evict oldest downloads down to the target only after crossing the cap."""
        files = sorted(self.root.glob("*.pbf"), key=lambda p: p.stat().st_mtime)
        total = sum(p.stat().st_size for p in files)
        if total > CACHE_LIMIT:
            for path in files:
                total -= path.stat().st_size
                path.unlink(missing_ok=True)
                if total <= CACHE_TARGET:
                    break


def mercator_y(lat):
    """Latitude in degrees to a north-to-south position in the unit world."""
    return (
        1
        - math.asinh(
            math.tan(
                math.radians(
                    max(-MERCATOR_MAX_LATITUDE, min(MERCATOR_MAX_LATITUDE, lat))
                )
            )
        )
        / math.pi
    ) / 2


def tile_lonlat(z, x, y):
    """Fractional tile coordinates to longitude/latitude, both in degrees."""
    n = 2**z
    return x / n * 360 - 180, math.degrees(
        math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    )


def validate(query):
    """Check stdin before arithmetic or I/O; x/y are coverage-radius units."""
    if not isinstance(query, dict) or not coordinates(
        query.get("lat"), query.get("lon")
    ):
        raise ValueError("Invalid map observer")
    for key, lo, hi in (
        ("radius", 1, 200),
        ("zoom", 1, 64),
        ("size", 1, 4096),
        ("x", -1, 1),
        ("y", -1, 1),
    ):
        if not number(query.get(key), lo, hi):
            raise ValueError("Invalid map viewport")
    if math.hypot(query["x"], query["y"]) > 1 - 1 / query["zoom"] + 1e-6:
        raise ValueError("Map viewport outside coverage")


def viewport_center(query):
    """Invert the radar's local x/y projection to find the geographic view centre."""
    distance_nm = math.hypot(query["x"], query["y"]) * query["radius"]
    bearing_degrees = math.degrees(math.atan2(query["x"], -query["y"]))
    return destination(query["lat"], query["lon"], distance_nm, bearing_degrees)


def keys_in_boxes(boxes, level):
    """Collect a bounded tile rectangle for each side of the antimeridian."""
    count = 2**level

    def column(longitude):
        return max(0, min(count - 1, math.floor((longitude + 180) / 360 * count)))

    def row(latitude):
        return max(0, min(count - 1, math.floor(mercator_y(latitude) * count)))

    keys = set()
    for (south, west), (north, east) in boxes:
        first_column, last_column = column(west), column(east)
        first_row, last_row = row(north), row(south)
        tile_count = (last_column - first_column + 1) * (last_row - first_row + 1)
        if tile_count > MAX_TILES:
            return []
        keys.update(
            (level, x, y)
            for x in range(first_column, last_column + 1)
            for y in range(first_row, last_row + 1)
        )
    return sorted(keys) if len(keys) <= MAX_TILES else []


def tile_keys(query):
    """Choose detail near one source pixel per display pixel, subject to a cap."""
    validate(query)
    lat, lon = viewport_center(query)
    view_radius_nm = query["radius"] / query["zoom"]
    # A small margin lets the existing map survive a short pan during the next load.
    boxes = bounding_boxes(lat, lon, view_radius_nm * VIEW_PADDING)
    # Mercator cannot cover the poles: use the spherical offline map there.
    if any(south[0] < -85 or north[0] > 85 for south, north in boxes):
        return []

    diameter_pixels = max(1, query["size"] - 2 * CHART_MARGIN_PIXELS)
    pixels_per_nm = diameter_pixels / (2 * view_radius_nm)
    world_circumference_nm = 2 * math.pi * EARTH_NM * math.cos(math.radians(lat))
    world_pixels = world_circumference_nm * pixels_per_nm
    level = max(
        0, min(MAX_TILE_ZOOM, round(math.log2(world_pixels / TILE_SIZE_PIXELS)))
    )
    # Large viewports step down in detail rather than enqueueing unbounded work.
    while level >= MIN_TILE_ZOOM:
        keys = keys_in_boxes(boxes, level)
        if keys:
            return keys
        level -= 1
    return []


def project_tile(key, features, query, budget=None):
    """Clip tile buffers and project selected layers into observer-relative units.

    Water polygons preserve their ring winding (islands are holes). Line layers
    are clipped independently so tile boundaries never become artificial roads.
    """
    z, col, row = key
    lat, lon, radius = query["lat"], query["lon"], query["radius"]
    if budget is None:
        budget = [MAX_VIEW_POINTS]

    def project(point, extent):
        # Clipping and curved-edge sampling can expand a small input geometry.
        # Cap generated points across the entire viewport, before allocating them.
        budget[0] -= 1
        if budget[0] < 0:
            raise ValueError("Projected map viewport too complex")
        # Tile coordinates -> geographic degrees -> the same range/bearing as AIS.
        lng, phi = tile_lonlat(z, col + point[0] / extent, row + point[1] / extent)
        distance, bearing = distance_bearing(lat, lon, phi, lng)
        angle = math.radians(bearing)
        return [
            round(math.sin(angle) * distance / radius, 8),
            round(-math.cos(angle) * distance / radius, 8),
        ]

    def project_ring(ring, extent):
        # Curved tile edges need the same sampling on neighbouring tiles.
        points = []
        for a, b in zip(ring, ring[1:] + ring[:1]):
            steps = max(
                1, math.ceil(max(abs(b[0] - a[0]), abs(b[1] - a[1])) / extent * 16)
            )
            for i in range(steps):
                points.append(
                    project(
                        [
                            a[0] + (b[0] - a[0]) * i / steps,
                            a[1] + (b[1] - a[1]) * i / steps,
                        ],
                        extent,
                    )
                )
        return points

    tile = dict(water=[], waterways=[], roads=[], cities=[])
    for layer, props, kind, extent, paths in features:
        box = [0, 0, extent, extent]
        if layer == "water" and kind == 3:
            rings = [clip_ring(path, box) for path in paths]
            tile["water"].append(
                [project_ring(ring, extent) for ring in rings if len(ring) >= 3]
            )
        elif kind == 2 and layer in ("waterway", "transportation"):
            if layer == "transportation" and props.get("class") not in (
                "motorway",
                "trunk",
                "primary",
                "secondary",
                "tertiary",
                "minor",
                "service",
                "pier",
            ):
                continue
            if props.get("brunnel") == "tunnel":
                continue
            dest = "waterways" if layer == "waterway" else "roads"
            for path in paths:
                for line in clip_line(path, box):
                    tile[dest].append([project(p, extent) for p in line])
        elif (
            layer == "place"
            and kind == 1
            and props.get("class") in ("city", "town", "village", "suburb")
        ):
            name = props.get("name")
            if not isinstance(name, str) or not name or not paths:
                continue
            label_point = paths[0][0]
            # Unlike lines/polygons, points have no clipping step above. Reject
            # out-of-tile labels before the Mercator inverse can overflow.
            if not all(0 <= coordinate <= extent for coordinate in label_point):
                continue
            x, y = project(label_point, extent)
            rank = props.get("rank", 20)
            tile["cities"].append(
                dict(
                    name=name[:100],
                    x=x,
                    y=y,
                    rank=rank if number(rank, 0, 1000) else 20,
                )
            )
    return tile


def build(query, source=None):
    """Return one complete map snapshot, or let the caller keep its fallback."""
    keys = tile_keys(query)
    if not keys:
        return dict(available=False)
    source = source or Source()
    template = source.template()
    # Limit each batch as well as the total decoded geometry held in memory.
    features, points = [], 0
    try:
        with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
            for start in range(0, len(keys), DOWNLOAD_WORKERS):
                for data in pool.map(
                    lambda key: source.tile(template, key),
                    keys[start : start + DOWNLOAD_WORKERS],
                ):
                    points += sum(
                        len(path) for _, _, _, _, paths in data for path in paths
                    )
                    if points > MAX_VIEW_POINTS:
                        raise ValueError("Map viewport too complex")
                    features.append(data)
    finally:
        # Failed/oversized viewports may have downloaded tiles too.
        try:
            source.trim()
        except OSError:
            pass
    budget = [MAX_VIEW_POINTS]
    tiles = [
        project_tile(key, data, query, budget) for key, data in zip(keys, features)
    ]
    # Adjacent tiles can repeat a place label in their buffered edges.
    cities = {}
    for tile in tiles:
        for city in tile.pop("cities"):
            cities[(city["name"], city["x"], city["y"])] = city
    return dict(
        available=True,
        level=keys[0][0],
        tiles=tiles,
        cities=sorted(cities.values(), key=lambda c: (c["rank"], c["name"])),
        x=query["x"],
        y=query["y"],
        coverRadius=VIEW_PADDING / query["zoom"],
        origin=[query["lat"], query["lon"], query["radius"]],
    )
