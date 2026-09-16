#!/usr/bin/env python3
"""Build the offline map from versioned Natural Earth GeoJSON (see data/README.md)."""
import gzip
import json
from pathlib import Path
import sys


def bounds(points):
    xs, ys = zip(*points)
    return [min(xs), min(ys), max(xs), max(ys)]


def rounded(points):
    return [[round(lon,5), round(lat,5)] for lon,lat in points]


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python3 tools/build_basemap.py LAND.geojson COASTLINE.geojson")
    land, coast = [], []
    for feature in json.loads(Path(sys.argv[1]).read_text())["features"]:
        geometry = feature["geometry"]
        polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
        for polygon in polygons:
            rings = [rounded(ring) for ring in polygon]
            land.append(dict(bbox=bounds(rings[0]), rings=rings))
    for feature in json.loads(Path(sys.argv[2]).read_text())["features"]:
        geometry = feature["geometry"]
        lines = [geometry["coordinates"]] if geometry["type"] == "LineString" else geometry["coordinates"]
        for line in lines:
            points = rounded(line)
            coast.append(dict(bbox=bounds(points), points=points))
    output = Path(__file__).resolve().parent.parent/"data"/"basemap.json.gz"
    data = json.dumps(dict(version=1, land=land, coast=coast), separators=(",", ":")).encode()
    output.write_bytes(gzip.compress(data, mtime=0))
    print(f"Wrote {len(land)} land polygons and {len(coast)} coastlines")


if __name__ == "__main__":
    main()
