"""Clip the bundled world map once, using the radar's nautical projection."""

import gzip
import json
import math
from pathlib import Path

from geometry import bounding_boxes, distance_bearing

PATH = Path(__file__).resolve().parent.parent / "data" / "basemap.json.gz"
CITIES_PATH = PATH.with_name("coastal-cities.json.gz")


def overlaps(a, b):
    return a[0] <= b[2] and a[2] >= b[0] and a[1] <= b[3] and a[3] >= b[1]


def signed_area(points):
    return (
        sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1]))
        / 2
    )


def clip_ring(ring, box):
    """Sutherland-Hodgman clipping; new boundary edges are used only for fills."""
    points = ring[:-1] if ring and ring[0] == ring[-1] else list(ring)
    for axis, edge, direction in (
        (0, box[0], 1),
        (0, box[2], -1),
        (1, box[1], 1),
        (1, box[3], -1),
    ):
        if not points:
            break
        result, previous = [], points[-1]
        was_inside = (previous[axis] - edge) * direction >= 0
        for point in points:
            inside = (point[axis] - edge) * direction >= 0
            if inside != was_inside:
                t = (edge - previous[axis]) / (point[axis] - previous[axis])
                result.append(
                    [
                        previous[0] + t * (point[0] - previous[0]),
                        previous[1] + t * (point[1] - previous[1]),
                    ]
                )
            if inside:
                result.append(point)
            previous, was_inside = point, inside
        points = result
    return points


def densify(points):
    # Straight geographic edges become curves near the poles after projection.
    result = []
    for a, b in zip(points, points[1:] + points[:1]):
        steps = max(
            math.ceil(abs(b[0] - a[0]) / 0.25), math.ceil(abs(b[1] - a[1]) / 0.25), 1
        )
        result.extend(
            [
                [a[0] + (b[0] - a[0]) * n / steps, a[1] + (b[1] - a[1]) * n / steps]
                for n in range(steps)
            ]
        )
    return result


def clip_segment(a, b, box):
    """Liang-Barsky clipping retains fractional coastline intersections."""
    dx, dy, lo, hi = b[0] - a[0], b[1] - a[1], 0.0, 1.0
    for p, q in (
        (-dx, a[0] - box[0]),
        (dx, box[2] - a[0]),
        (-dy, a[1] - box[1]),
        (dy, box[3] - a[1]),
    ):
        if p == 0:
            if q < 0:
                return None
        elif p < 0:
            lo = max(lo, q / p)
        else:
            hi = min(hi, q / p)
        if lo > hi:
            return None
    return [[a[0] + lo * dx, a[1] + lo * dy], [a[0] + hi * dx, a[1] + hi * dy]]


def clip_line(points, box):
    lines = []
    for a, b in zip(points, points[1:]):
        segment = clip_segment(a, b, box)
        if segment is None:
            continue
        if lines and lines[-1][-1] == segment[0]:
            lines[-1].append(segment[-1])
        else:
            lines.append(segment)
    return lines


def cities_at(lat, lon, radius, path=CITIES_PATH):
    """Project bundled coastal cities once; the UI handles zoom and label density."""
    try:
        with gzip.open(path, "rt") as source:
            dataset = json.load(source)
        if dataset["version"] != 1:
            return []
        cities = []
        for city in dataset["cities"]:
            distance, bearing = distance_bearing(
                lat, lon, city["latitude"], city["longitude"]
            )
            if distance > radius:
                continue
            angle = math.radians(bearing)
            cities.append(
                dict(
                    name=city["name"],
                    population=city["population"],
                    x=math.sin(angle) * distance / radius,
                    y=-math.cos(angle) * distance / radius,
                )
            )
        return sorted(cities, key=lambda city: (-city["population"], city["name"]))
    except (OSError, EOFError, ValueError, KeyError, TypeError):
        return []


def build(lat, lon, radius, path=PATH):
    result = dict(
        key=f"{lat},{lon},{radius}",
        available=False,
        polygons=[],
        coastlines=[],
        cities=cities_at(lat, lon, radius),
    )
    try:
        with gzip.open(path, "rt") as source:
            dataset = json.load(source)
        if dataset["version"] != 1:
            return result
        boxes = [
            [a[1], a[0], b[1], b[0]] for a, b in bounding_boxes(lat, lon, radius * 1.5)
        ]

        def project(point):
            distance, bearing = distance_bearing(lat, lon, point[1], point[0])
            angle = math.radians(bearing)
            return [
                round(math.sin(angle) * distance / radius, 5),
                round(-math.cos(angle) * distance / radius, 5),
            ]

        polygons, coastlines = [], []
        for box in boxes:
            for polygon in dataset["land"]:
                if not overlaps(polygon["bbox"], box):
                    continue
                rings = []
                for index, ring in enumerate(polygon["rings"]):
                    clipped = clip_ring(ring, box)
                    if len(clipped) < 3:
                        continue
                    # Winding preserves lake holes under Canvas's nonzero fill rule.
                    if (signed_area(clipped) > 0) != (index == 0):
                        clipped.reverse()
                    rings.append([project(point) for point in densify(clipped)])
                if rings:
                    polygons.append(rings)
            for line in dataset["coast"]:
                if overlaps(line["bbox"], box):
                    coastlines.extend(
                        [
                            [project(point) for point in part]
                            for part in clip_line(line["points"], box)
                        ]
                    )
        return result | dict(available=True, polygons=polygons, coastlines=coastlines)
    except (OSError, EOFError, ValueError, KeyError, TypeError):
        # Missing/corrupt geography is explicit, never silently interpreted as sea.
        return result
