# Development

## Local checkout and troubleshooting

For development, place this checkout at
`~/.config/omarchy/plugins/simoz.vessel/`, keeping `manifest.json` at its root, then:

```sh
omarchy plugin validate ~/.config/omarchy/plugins/simoz.vessel
omarchy-shell shell rescanPlugins
omarchy plugin enable simoz.vessel
```

If Python is not available in the shell's PATH, set the widget's `pythonExecutable`
option in `~/.config/omarchy/shell.json` to its absolute path and reload the shell
configuration. This is the only advanced setting kept in the manifest schema.

If migrating from Airlock, disable the old plugin with
`omarchy plugin disable simoz.airlock`.

## Tests

Prepare the managed dependency once, then run the standard-library tests:

```sh
python3 backend/vessel.py --prepare-runtime
python3 -B -m unittest discover -s tests -p 'test_backend.py'
node --test tests/*.test.cjs
omarchy plugin validate .
```

Run the full suite, including local WebSocket peers, with the prepared interpreter:

```sh
VENV_PYTHON="$(python3 -B -c 'import sys; sys.path.insert(0, "backend"); import runtime; print(runtime.location() / "bin/python")')"
"$VENV_PYTHON" -B -m unittest discover -s tests -p 'test_*.py'
```

The tests cover AIS normalization, Class A/B merging, timestamps and expiry,
dateline/polar geometry, offshore demo placement, settings validation and private
file permissions. Local WebSocket tests exercise compressed binary messages,
subscription rejection, reconnection, cancellation and rejection of untrusted TLS certificates without an AIS account. Bootstrap tests cover failed installation, cancellation and path aliases.
Security regression tests cover oversized numeric values, malformed inputs,
HTTPS redirects, public settings fields and interrupted credential writes.

QML syntax and a Qt rendering harness are checked on macOS. Actual Quickshell
integration, Hyprland popout behaviour and an authenticated AISStream session
still require testing on Omarchy. The host API targets the `quattro` branch.

## Code layout

Code comments are in English. Python formatting and import checks use
`ruff.toml`; Ruff is an optional development tool, not a plugin dependency:

```sh
ruff check backend tools tests
ruff format --check backend tools tests
```

Modules:

- `backend/vessel.py`: command-line entry point, location selection and offline demo.
- `backend/ais.py`: AIS validation, Class A/B merging and bounded fleet snapshots.
- `backend/receiver.py`: WebSocket subscription, status updates, cancellation and reconnection.
- `backend/geometry.py`, `backend/basemap.py`: nautical calculations and the offline map.
- `backend/runtime.py`: private virtualenv setup, dependency verification and process replacement.
- `backend/settings.py`: validated settings and atomic, owner-only credential storage.
- `backend/geocoding.py`: explicit Photon city searches, response validation and location labels.
- `backend/network.py`: bounded HTTPS JSON requests and HTTPS-only redirects for location services.
- `VesselService.qml`, `SettingsForm.qml`: shared receiver lifecycle and graphical configuration.
- `Widget.qml`, `Radar.qml`, `Model.js`: panel layout, map rendering and shared view geometry.
- `BoatIcon.qml`, `Robot.qml`: themed artwork; panel controls live in `Widget.qml`.
- `tools/build_basemap.py`: rebuilds the bundled Natural Earth geometry.
- `tools/build_cities.py`: filters GeoNames settlements against the coastline for offline labels.
- `requirements.txt`: the single pinned, hash-verified live dependency.

The helper emits JSON snapshots; the first located snapshot also includes a static
basemap. Position timestamps use Unix seconds, while the QML display clock uses
milliseconds. Live positions are never extrapolated or stored on disk.

