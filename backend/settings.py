"""Validate local preferences and keep credentials out of public responses."""

import json
import math
import os
import tempfile
from pathlib import Path

DEFAULTS = dict(
    radiusNm=25,
    autoLocation=True,
    demo=False,
    unit="nm",
    latitude=None,
    longitude=None,
    cityName="",
)
MAX_SETTINGS_BYTES = 65_536


def path():
    return (
        Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
        / "omarchy-vessel"
        / "settings.json"
    )


def read_file():
    """Read a bounded JSON object; validation happens after merging defaults."""
    try:
        with path().open("rb") as source:
            raw = source.read(MAX_SETTINGS_BYTES + 1)
    except FileNotFoundError:
        return {}
    if len(raw) > MAX_SETTINGS_BYTES:
        raise ValueError("Settings file is too large")
    try:
        saved = json.loads(raw)
    except RecursionError as error:
        raise ValueError("Invalid settings") from error
    if not isinstance(saved, dict):
        raise ValueError("Invalid settings")
    return saved


def bounded_number(value, low, high):
    """Accept numeric form fields, but reject booleans, infinities and overflow."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("Invalid number")
    try:
        result = float(value)
    except (ValueError, OverflowError) as error:
        raise ValueError("Invalid number") from error
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError("Number out of range")
    return result


def validate_preferences(values):
    """Return only known fields, with the same rules for saved files and edits."""
    result = {key: values.get(key, default) for key, default in DEFAULTS.items()}
    result["radiusNm"] = bounded_number(result["radiusNm"], 1, 200)
    if result["unit"] not in ("nm", "km", "mi") or any(
        type(result[key]) is not bool for key in ("demo", "autoLocation")
    ):
        raise ValueError("Invalid preferences")
    for key, limit in (("latitude", 90), ("longitude", 180)):
        value = result[key]
        result[key] = (
            None if value in (None, "") else bounded_number(value, -limit, limit)
        )
    if (
        not result["demo"]
        and not result["autoLocation"]
        and any(result[key] is None for key in ("latitude", "longitude"))
    ):
        raise ValueError("Both coordinates are required")
    city = result["cityName"]
    if (
        not isinstance(city, str)
        or len(city) > 250
        or any(ord(char) < 32 for char in city)
    ):
        raise ValueError("Invalid city name")
    result["cityName"] = city.strip()
    return result


def validate_key(value):
    if (
        not isinstance(value, str)
        or len(value) > 4096
        or any(char in value for char in "\r\n\0")
    ):
        raise ValueError("Invalid key")
    return value.strip()


def read():
    saved = read_file()
    return validate_preferences(saved) | {
        "apiKey": validate_key(saved.get("apiKey", ""))
    }


def effective_key(saved):
    # Validate the legacy environment fallback with the same rules as the editor.
    return saved["apiKey"] or validate_key(os.environ.get("AISSTREAM_API_KEY", ""))


def api_key():
    return effective_key(read())


def public_settings(saved=None):
    saved = read() if saved is None else saved
    # An explicit allowlist prevents future private fields from being echoed to QML.
    return {key: saved[key] for key in DEFAULTS} | {
        "hasApiKey": bool(effective_key(saved))
    }


def save(values):
    if not isinstance(values, dict):
        raise ValueError("Invalid settings")
    saved = read_file()
    result = validate_preferences(saved | values)
    new_key = validate_key(values.get("apiKey", ""))
    # A blank password field preserves the credential; a replacement can also
    # repair an invalid old key without first needing to validate that old value.
    result["apiKey"] = new_key or validate_key(saved.get("apiKey", ""))
    public = public_settings(result)
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
    return public
