"""Keep recent fleet state across receiver restarts, in an owner-only cache file."""

import json
import os
import tempfile
from contextlib import suppress
from pathlib import Path

MAX_CACHE_BYTES = 8 << 20


def path():
    base = Path(os.environ.get("XDG_CACHE_HOME", ""))
    if not base.is_absolute():
        base = Path.home() / ".cache"
    return base / "omarchy-vessel" / "fleet.json"


def load(fleet, now, destination=None):
    """Restore saved contacts; a missing, oversized or corrupt cache is ignored."""
    destination = destination or path()
    before = len(fleet.ships)
    try:
        with destination.open("rb") as cached:
            raw = cached.read(MAX_CACHE_BYTES + 1)
        if len(raw) <= MAX_CACHE_BYTES:
            fleet.restore(json.loads(raw), now)
    except FileNotFoundError:
        return
    except (OSError, ValueError, RecursionError):
        pass
    # Do not keep old positions on disk: remove a cache with nothing restorable,
    # whether expired, corrupt, oversized or saved for another location.
    if len(fleet.ships) == before:
        with suppress(OSError):
            destination.unlink(missing_ok=True)


def save(fleet, destination=None):
    """Replace the cache atomically; failing to save never stops reception."""
    destination = destination or path()
    try:
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # mkstemp creates the file with owner-only permissions.
        fd, temporary = tempfile.mkstemp(prefix=".fleet-", dir=destination.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(fleet.export(), output, separators=(",", ":"))
            os.replace(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)
    except (OSError, ValueError):
        pass
