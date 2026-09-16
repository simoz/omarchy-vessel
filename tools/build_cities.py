#!/usr/bin/env python3
"""Extract near-coast settlements from GeoNames cities5000 and Natural Earth."""

import gzip
import hashlib
import io
import json
import math
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COAST_NM = 8


def segment_distance(lon, lat, a, b):
    # Local tangent-plane distance is sufficient for this approximate coastal
    # filter; live radar projection still uses spherical nautical geometry.
    scale = math.cos(math.radians(lat))
    ax, ay = ((a[0] - lon + 180) % 360 - 180) * 60 * scale, (a[1] - lat) * 60
    bx, by = ax + ((b[0] - a[0] + 180) % 360 - 180) * 60 * scale, (b[1] - lat) * 60
    dx, dy = bx - ax, by - ay
    length = dx * dx + dy * dy
    t = max(0, min(1, -(ax * dx + ay * dy) / length)) if length else 0
    return math.hypot(ax + t * dx, ay + t * dy)


def build(source, coastline):
    grid = defaultdict(list)
    # Index segments by one-degree cells. Dateline cells wrap consistently.
    for line in coastline["coast"]:
        for a, b in zip(line["points"], line["points"][1:]):
            east = a[0] + ((b[0] - a[0] + 180) % 360 - 180)
            for x in range(
                math.floor(min(a[0], east)), math.floor(max(a[0], east)) + 1
            ):
                for y in range(
                    math.floor(min(a[1], b[1])), math.floor(max(a[1], b[1])) + 1
                ):
                    grid[((x + 180) % 360 - 180, y)].append((a, b))
    cities = []
    with zipfile.ZipFile(source) as archive, archive.open("cities5000.txt") as raw:
        for line in io.TextIOWrapper(raw, encoding="utf-8"):
            row = line.rstrip("\n").split("\t")
            if row[6] != "P" or row[7] in ("PPLX", "PPLH", "PPLQ", "PPLW"):
                continue
            lat, lon = float(row[4]), float(row[5])
            dy = COAST_NM / 60
            dx = min(180, dy / max(0.001, math.cos(math.radians(lat))))
            near = False
            for x in range(math.floor(lon - dx), math.floor(lon + dx) + 1):
                if near:
                    break
                for y in range(math.floor(lat - dy), math.floor(lat + dy) + 1):
                    if any(
                        segment_distance(lon, lat, a, b) <= COAST_NM
                        for a, b in grid.get(((x + 180) % 360 - 180, y), ())
                    ):
                        near = True
                        break
            if near:
                name = "Genoa" if row[0] == "3176219" else row[1]
                cities.append(
                    dict(
                        id=int(row[0]),
                        name=name,
                        latitude=lat,
                        longitude=lon,
                        population=int(row[14]),
                        country=row[8],
                    )
                )
    cities.sort(key=lambda city: (-city["population"], city["id"]))
    return dict(
        version=1,
        source="GeoNames cities5000",
        sourceSha256=hashlib.sha256(Path(source).read_bytes()).hexdigest(),
        coastNm=COAST_NM,
        cities=cities,
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 tools/build_cities.py cities5000.zip")
    with gzip.open(ROOT / "data/basemap.json.gz", "rt") as source:
        coastline = json.load(source)
    result = build(sys.argv[1], coastline)
    output = ROOT / "data/coastal-cities.json.gz"
    output.write_bytes(
        gzip.compress(
            json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode(),
            mtime=0,
        )
    )
    print(
        f"Wrote {len(result['cities'])} coastal settlements ({output.stat().st_size} bytes)"
    )
    print("Source SHA-256:", result["sourceSha256"])
