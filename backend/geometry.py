"""Shared nautical geometry for the AIS filter and offline map."""

import math

EARTH_NM = 3440.065
GENOA = (44.4056, 8.9463)


def number(value, low, high):
    # Compare bounds before converting to float: JSON integers can exceed the
    # float range, and math.isfinite(huge_int) would otherwise raise OverflowError.
    return type(value) in (int, float) and low <= value <= high and math.isfinite(value)


def coordinates(lat, lon):
    return number(lat, -90, 90) and number(lon, -180, 180)


def distance_bearing(lat, lon, other_lat, other_lon):
    """Haversine distance and bearing clockwise from north, in nm/degrees."""
    a, b = math.radians(lat), math.radians(other_lat)
    delta = math.radians(other_lon - lon)
    h = (
        math.sin((b - a) / 2) ** 2
        + math.cos(a) * math.cos(b) * math.sin(delta / 2) ** 2
    )
    distance = 2 * EARTH_NM * math.asin(math.sqrt(max(0, min(1, h))))
    bearing = (
        math.degrees(
            math.atan2(
                math.sin(delta) * math.cos(b),
                math.cos(a) * math.sin(b) - math.sin(a) * math.cos(b) * math.cos(delta),
            )
        )
        % 360
    )
    return distance, bearing


def bounding_boxes(lat, lon, radius):
    """Enclose a circle; split subscriptions that cross the antimeridian."""
    angle = radius / EARTH_NM
    south, north = (
        max(lat - math.degrees(angle), -90),
        min(lat + math.degrees(angle), 90),
    )
    if south == -90 or north == 90:
        return [[[south, -180], [north, 180]]]
    delta = math.degrees(
        math.asin(min(math.sin(angle) / math.cos(math.radians(lat)), 1))
    )
    west, east = lon - delta, lon + delta
    if west < -180:
        return [[[south, west + 360], [north, 180]], [[south, -180], [north, east]]]
    if east > 180:
        return [[[south, west], [north, 180]], [[south, -180], [north, east - 360]]]
    return [[[south, west], [north, east]]]


def destination(lat, lon, distance, bearing):
    angle, direction = distance / EARTH_NM, math.radians(bearing)
    phi, lam = math.radians(lat), math.radians(lon)
    other_phi = math.asin(
        math.sin(phi) * math.cos(angle)
        + math.cos(phi) * math.sin(angle) * math.cos(direction)
    )
    other_lam = lam + math.atan2(
        math.sin(direction) * math.sin(angle) * math.cos(phi),
        math.cos(angle) - math.sin(phi) * math.sin(other_phi),
    )
    return math.degrees(other_phi), (math.degrees(other_lam) + 180) % 360 - 180
