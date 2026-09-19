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
dateline/polar geometry, settings validation and private
file permissions. Local WebSocket tests exercise compressed binary messages,
subscription rejection, reconnection, cancellation and rejection of untrusted TLS certificates without an AIS account. OpenWaters checks cover anonymous access, optional authentication, snapshot age, source attribution and isolation from saved AISStream credentials. Bootstrap tests cover failed installation, cancellation and path aliases.
Security regression tests cover oversized numeric values, malformed inputs,
HTTPS redirects, public settings fields and interrupted credential writes.

QML syntax and a Qt rendering harness are checked on macOS. The anonymous OpenWaters receiver has also been checked against live traffic around Genoa. Actual Quickshell
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

- `backend/vessel.py`: command-line entry point and location selection.
- `backend/ais.py`: AIS validation, Class A/B merging and bounded fleet snapshots.
- `backend/receiver.py`: WebSocket subscription, status updates, cancellation and reconnection.
- `backend/geometry.py`, `backend/basemap.py`: nautical calculations and the offline map.
- `backend/detail_map.py`, `backend/vector_tiles.py`: bounded OpenFreeMap tile requests, local cache, MVT decoding and projection into the same nautical coordinates as AIS.
- `Radar.qml`: camera, navigation and layer order; it requests the visible map after a 180 ms pause in navigation, independently of reception.
- `OfflineMap.qml`, `DetailMap.qml`: drawing for the bundled and downloaded geography, respectively. Both receive the same camera scale and pixel offset.
- `RadarLabels.qml`: label measurements and space reserved around visible contacts; collision decisions remain in `Model.js`.
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

`--map-detail` accepts one bounded JSON request on stdin (`lat`, `lon`, `radius`,
`zoom`, `size`, `x`, `y`) and emits a complete projected map. Zoom levels 7–14
come from the same OpenFreeMap TileJSON endpoint as Omastorm. Requests use at
most 36 tiles and four concurrent HTTPS transfers, with a 10-second network
timeout, seven-day cache freshness, stale cache fallback and 30-second retry
backoff. The cache trims from 128 to 96 MiB. Responses are discarded if the
viewport has changed; incomplete batches never replace the displayed map.
No additional runtime dependency is required. The nautical range remains 1×–64×;
at the source's maximum detail, further zoom enlarges the level-14 vectors.

## Reading and editing the UI

Start with `Widget.qml` for panel/window ownership and actions, `Radar.qml` for
the camera and paint order, and `VesselService.qml` for process lifecycles.
The painting components receive data and camera values; they do not fetch data
or change selection. QML coordinates are observer-relative coverage-radius units
until converted to pixels. Geographic degrees and Mercator tiles stay in Python.

Keep comments focused on units, ownership, ordering and reasons a seemingly
simpler implementation would change behaviour. Prefer named intermediate values
to long expressions, and expand handlers that change several pieces of state.
Do not repeat the code in a comment or introduce components without a clear
responsibility. Preserve QML object IDs used by keyboard focus and the preview
harness when moving view code.


## Preview images

All previews use real AIS traffic and a detailed map. With PySide6 installed,
provide a recent receiver JSON snapshot for Genoa (44.4056, 8.9463), radius 25 nm,
and a JSON batch produced by `--map-detail` for the same location and radius,
zoom 8 and center (0, 0):

```sh
QT_QPA_PLATFORM=offscreen QT_SCALE_FACTOR=2 \
  VESSEL_PREVIEW_LIVE=/tmp/vessel-live-preview.json \
  VESSEL_PREVIEW_DETAIL=/tmp/vessel-detail-genoa.json \
  python3 tools/render_previews.py
```

The snapshot must contain received vessels and the selected provider. Capture and
render promptly so the displayed ages remain representative. The renderer uses
the current QML interface and preserves positions, timestamps and attributions;
only the Quickshell host and receiver are stubbed. Rendering itself is offline.
Missing inputs or unavailable detailed coverage stop generation.

The renderer writes `docs/live-detail-preview.png` (dark),
`docs/live-detail-preview-light.png` (light), and copies the light image to
`preview.png` for the catalog (2400 × 1600 pixels). It also writes
`docs/compact-preview-dark.png` and `docs/compact-preview-light.png` (880 × 1700).
The renderer selects a nearby received vessel with IMO and destination when available,
and checks that the expanded robot sits above Contacts, the contact counter ends at
the map credits, and the compact robot stays inside the radar frame. This checks Qt
rendering, not Hyprland integration. The marketplace serves optimized copies of
`preview.png`, so its catalog must refresh after the updated image is pushed.
