"""Validated local preferences; credentials never appear in public responses."""
import json
import math
import os
from pathlib import Path
import tempfile

DEFAULTS = dict(radiusNm=25, autoLocation=True, demo=False, unit="nm", latitude=None, longitude=None, cityName="")


def path():
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home()/".config")/"omarchy-vessel"/"settings.json"


def read():
    saved = json.loads(path().read_text()) if path().exists() else {}
    if not isinstance(saved, dict):
        raise ValueError("Invalid settings")
    return DEFAULTS | saved


def api_key():
    return read().get("apiKey", "").strip() or os.environ.get("AISSTREAM_API_KEY", "").strip()


def public_settings():
    return {k: v for k, v in read().items() if k != "apiKey"} | {"hasApiKey": bool(api_key())}


def save(values):
    if not isinstance(values, dict):
        raise ValueError("Invalid settings")
    result = read() | {k: v for k, v in values.items() if k in DEFAULTS}
    radius = float(result["radiusNm"])
    if isinstance(result["radiusNm"], bool) or not math.isfinite(radius) or not 1 <= radius <= 200:
        raise ValueError("Invalid radius")
    result["radiusNm"] = radius
    if result["unit"] not in ("nm", "km") or any(type(result[k]) is not bool for k in ("demo", "autoLocation")):
        raise ValueError("Invalid preferences")
    for key, limit in (("latitude", 90), ("longitude", 180)):
        value = result[key]
        if isinstance(value, bool):
            raise ValueError("Invalid coordinate")
        value = None if value in (None, "") else float(value)
        if value is not None and (not math.isfinite(value) or not -limit <= value <= limit):
            raise ValueError("Invalid coordinate")
        result[key] = value
    if not result["demo"] and not result["autoLocation"] and any(result[k] is None for k in ("latitude", "longitude")):
        raise ValueError("Both coordinates are required")
    city = result["cityName"]
    if not isinstance(city, str) or len(city) > 250 or any(ord(char) < 32 for char in city):
        raise ValueError("Invalid city name")
    result["cityName"] = city.strip()
    key = values.get("apiKey", "")
    if not isinstance(key, str) or len(key) > 4096 or any(c in key for c in "\r\n\0"):
        raise ValueError("Invalid key")
    if key.strip():
        result["apiKey"] = key.strip()
    destination = path()
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = None
    try:
        # mkstemp is private from creation. Atomic replacement leaves the old
        # credential intact if validation or writing fails.
        fd, temporary = tempfile.mkstemp(prefix=".settings-", dir=destination.parent)
        with os.fdopen(fd, "w") as output:
            os.fchmod(output.fileno(), 0o600)
            json.dump(result, output, allow_nan=False)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    return public_settings()
