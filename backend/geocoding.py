"""Explicit city searches via Photon; no API key or extra dependency needed."""

import os
import re
from urllib.parse import urlencode, urlsplit

from geometry import coordinates
from network import fetch_json

ENDPOINT = "https://photon.komoot.io/api/"


def text(value, limit=120):
    return (
        re.sub(r"[\x00-\x1f\x7f]", "", value).strip()[:limit]
        if isinstance(value, str)
        else ""
    )


def places(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
        raise ValueError("Invalid city response")
    result, seen = [], set()
    for feature in payload["features"][:30]:
        if not isinstance(feature, dict):
            continue
        properties, point = feature.get("properties"), feature.get("geometry")
        if (
            not isinstance(properties, dict)
            or not isinstance(point, dict)
            or point.get("type") != "Point"
        ):
            continue
        position = point.get("coordinates")
        if (
            not isinstance(position, list)
            or len(position) != 2
            or not coordinates(position[1], position[0])
        ):
            continue
        name, country = text(properties.get("name")), text(properties.get("country"))
        if not name:
            continue
        # Request English upstream; normalize this familiar local spelling too.
        if (
            name.casefold() == "genova"
            and text(properties.get("countrycode")).upper() == "IT"
        ):
            name = "Genoa"
        label = f"{name} ({country})" if country else name
        identity = (label, round(position[1], 4), round(position[0], 4))
        if identity in seen:
            continue
        seen.add(identity)
        result.append(
            dict(
                label=label,
                detail=text(properties.get("state")),
                latitude=position[1],
                longitude=position[0],
            )
        )
        if len(result) == 6:
            break
    return result


def search(query):
    query = text(query)
    if len(query) < 2:
        raise ValueError("Enter at least two characters")
    # A compatible self-hosted service can replace the public endpoint without
    # changing source. Only city names are sent, never credentials or settings.
    endpoint = os.environ.get("VESSEL_GEOCODER_URL", ENDPOINT)
    parsed = urlsplit(endpoint)
    if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("Geocoder URL must be an HTTPS endpoint")
    url = endpoint + "?" + urlencode(dict(q=query, lang="en", limit=6, layer="city"))
    return places(fetch_json(url, max_bytes=262_144))
