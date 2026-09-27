# Security review

Reviewed on **2026-09-27** for **0.9.0**, starting from commit `ed4190c`.
This pass covers changes since the 0.8.3 release at `805746a`: vessel details,
recent tracks, the recent-contact cache, type colors and filters, the widget
split, the Python 3.11 cancellation fix, CI and preview tooling. Exact reviewed
files are identified in [security-review-evidence.json](security-review-evidence.json).
This identifies reviewed contents, not publication of a release tag.

## Scope and result

The review inspected the new AIS parsing, track bounds, cache storage and
re-validation, theme-file reading, QML rendering of new fields, receiver
cancellation, the CI workflow and the preview renderer. Checks combined source
inspection, adversarial inputs, local WebSocket servers, the regression suite on
Python 3.11 and 3.14, and a live Omarchy shell load.
**One low-severity privacy finding (SR-07) was fixed; no other actionable
security findings were identified in the reviewed changes.** SR-01 through SR-06
remain fixed and their regression tests pass. No production credentials were used;
external requests were limited to package metadata/advisories, pinned CI tool
metadata, and anonymous AIS/map captures at public Genoa and Copenhagen
coordinates. This was not a penetration test of providers.

## Changes rechecked

- **Vessel details:** navigational status, heading, call sign, dimensions,
  draught and ETA are accepted only as exact types within AIS ranges; unavailable
  sentinels (heading 511, status 15, ETA hour 24/minute 60, zero dimensions) and
  malformed values are ignored. Text is cleaned and length-limited like names and
  destinations, and all fields render as plain text.
- **Recent tracks:** at most 20 points per vessel from the last thirty minutes,
  one per 90 seconds; implausible jumps restart the track. Snapshots emit only
  rounded distance/bearing pairs; the fleet caps (2,000 tracked, 200 shown) apply.
- **Recent-contact cache:** the receiver saves the fleet every 30 seconds and on
  exit to `$XDG_CACHE_HOME/omarchy-vessel/fleet.json`, written atomically through
  a private temporary file (`0600`, new directories `0700`); failures never stop
  reception. On load the read is bounded to 8 MiB, JSON errors and deep nesting are
  rejected, and every entry is re-validated as untrusted input: text is cleaned,
  numbers are range-checked, attributions are rebuilt, distances and bearings are
  recomputed for the current observer, and entries older than thirty minutes or
  more than twice the radius away are dropped. See SR-07 for stale-file removal.
- **Type colors and filters:** hues are read from the active theme's
  `colors.toml`, the same file the Omarchy shell already reads; only `#rrggbb`
  values are extracted, and nothing is evaluated. Filters change presentation only.
- **Widget split:** `VesselDetails`, `ContactList` and `TypeFilters` receive data as
  properties and report actions through signals. The VesselFinder link keeps its
  fixed HTTPS host and numeric IMO/MMSI and still requires explicit activation.
- **Receiver cancellation:** on Python 3.11, cancelling the receiver during
  `asyncio.wait_for(socket.recv())` left the inner task pending, so the reconnect
  test hung. `asyncio.timeout` now runs `recv` in the receiver task. A real receiver
  stopped with `SIGTERM` exited in 0.1–0.16 s on 3.11 before and after the change;
  the hang was reproduced only with direct task cancellation.
- **CI and tooling:** GitHub Actions run with `contents: read`, without persisted
  checkout credentials, and use Actions pinned to full commit SHAs. Ruff, a
  development-only tool, is installed with `--require-hashes`. `tests/run` executes
  only repository tests and local validators. The preview renderer now wraps
  injected JSON in parentheses and uses unique placeholders; it still reads trusted
  local captures only. Launch videos and audio are ignored by Git.

## Findings in this review

| ID | Finding and impact | Resolution and evidence |
| --- | --- | --- |
| SR-07 | **Stale position history — low-severity privacy.** Entries older than thirty minutes were discarded when the cache was read, but the file itself kept the last received positions near the monitored location indefinitely if Vessel was not reopened, or after a location change. | A cache with nothing restorable (expired, corrupt, oversized or saved for another location) is deleted when reception next starts. Regressions cover expiry, corrupt and oversized files, and a different observer. A file written at the last exit still remains until the next start; the README documents its location and how to delete it. |

## Findings and fixes from earlier assessments

The following findings were fixed before this pass. Their tests were rerun for
this review; the original vulnerable implementations were not reintroduced or retested.

| ID | Finding and impact | Resolution and evidence |
| --- | --- | --- |
| SR-01 | **Credential destination — high impact if a provider handshake redirects to an attacker-controlled endpoint.** The WebSocket library follows redirects. Although websockets 17.1 strips cross-origin authorization headers, AISStream's key is sent later in the subscription body. A local two-server test received the synthetic key at the redirected destination before the fix. | The receiver now refuses WebSocket redirects, for both providers. The same regression now confirms that the redirected endpoint receives no subscription. This is an application-level destination restriction, not a claim of a new websockets vulnerability. |
| SR-02 | **Availability — geometry caps could be bypassed.** ClosePath appended points without charging the decoder budget: a reduced-limit reproduction accepted 23 points with a limit of 3. Separately, clipping and curved-edge sampling could expand geometry after the input-point check. | Count closing points, reject repeated closures and line continuation after closure, and enforce a shared generated-point budget across the whole viewport. Tests cover valid closures, malformed repeats, densification and budget sharing between tiles. |
| SR-03 | **Request-destination hardening.** The TileJSON template was restricted to OpenFreeMap, but the generic redirect handler still permitted another HTTPS host or port. This could move map requests outside the declared provider boundary. No live malicious redirect was observed. | Validate both the initial map URL and every redirect: HTTPS, no URL credentials, `tiles.openfreemap.org`, and default/443 port only. Tests reject other hosts, localhost, alternate ports, plaintext and file URLs before opening a connection; same-provider redirects remain supported. |
| SR-04 | **Map-helper availability.** Place points lacked the clipping applied to polygon and line layers. Extreme coordinates accepted by the vector reader could overflow the Mercator inverse instead of producing a controlled result. | Discard out-of-tile labels before projection. A synthetic extent-1 label with a coordinate of 1,000,000 is rejected without overflow. Buffered labels outside their owning tile are intentionally omitted. |
| SR-05 | **Cache recovery — low impact.** A malformed TileJSON response was cached before validation and could disable detailed maps for the seven-day freshness interval. The `tiles` field also lacked an explicit list-type check. | Validate the container and template, remove invalid catalog entries, and allow the next retry to obtain a valid catalog. Tests cover malformed JSON, a dictionary instead of a list, and an empty tile list. |
| SR-06 | **Bounded-read hardening.** Cache size was checked with stat(), followed by an unbounded read; the file could change between those operations. Cache files are within the trusted local-user boundary. | Bound the read itself to the limit plus one byte and reject oversized contents. Atomic-write regression also verifies owner-only files/directories, preservation of the old file after replacement failure, and temporary-file cleanup. |

Implementation: [receiver.py](../backend/receiver.py),
[vector_tiles.py](../backend/vector_tiles.py), [detail_map.py](../backend/detail_map.py).
Regressions: [test_receiver.py](../tests/test_receiver.py),
[test_detail_map.py](../tests/test_detail_map.py), [test_security.py](../tests/test_security.py).

## Protections rechecked

- **Credential storage:** settings are replaced atomically with a `0600` file;
  newly created settings directories use `0700`. Invalid edits and interrupted
  replacement preserve the existing key. Blank password fields preserve saved
  credentials, and public preferences expose only key-presence flags.
- **Credential transport:** the editor sends settings through stdin, not process
  arguments. The password field is cleared on save, cancel and hiding. OpenWaters
  and AISStream use separate saved keys; the former uses a bearer header and the
  latter a subscription field. Subscription errors and WebSocket logs do not echo
  credentials to the UI.
- **TLS and reception:** provider endpoints use WSS with certificate verification.
  Local TLS rejection tests confirm that an untrusted certificate cannot receive
  a subscription. Messages are limited to 1 MiB; the fleet tracks at most 2,000
  records, each with at most 20 track points, and exposes at most 200 contacts.
  Pause, reconnect and cancellation tests pass on Python 3.11 and 3.14.
- **Process execution:** helpers and browser launchers use argument arrays, not
  shell interpolation. Map requests run separately from AIS reception and do not
  load saved credentials or bootstrap the WebSocket dependency. Superseded map
  replies are discarded; failed map batches retain the last complete result.
- **QML rendering:** AIS fields use plain Text or Canvas drawing. The styled
  attribution links are fixed source literals, not provider-supplied markup.
  Vector data is interpreted only as coordinates, paths and text; it is not
  evaluated as QML or JavaScript.
- **Map requests and memory:** at most 36 tiles per viewport and four concurrent
  downloads, with 4 MiB per tile response and 256 KiB for TileJSON. The decoder
  allows at most 250,000 materialized points per tile. A viewport is limited to
  300,000 decoded points and, separately, 300,000 generated projected points.
  These are point/response limits, not an exact cap on Python or Qt memory usage.
- **Tile cache:** versioned URLs are hashed into filenames; provider strings are
  not used as local paths. Writes use private temporary files and atomic replacement.
  Freshness is seven days; stale data may be reused after a refresh failure.
  A persisted 30-second backoff reduces repeated failed requests. Eviction is
  triggered above 128 MiB and trims to 96 MiB, including after failed batches;
  downloads can temporarily exceed the threshold before cleanup.
- **Runtime installation:** the sole live dependency remains the exact portable
  websockets 17.1 wheel, installed with its SHA-256 hash, `--require-hashes`,
  `--no-deps`, `--only-binary` and pip isolation. Installer output is suppressed,
  the legacy AIS key is excluded from its environment, and cancellation cleans
  up its process group. The new map code adds no runtime package dependency.

## Data destinations

| Service | Data sent |
| --- | --- |
| OpenWaters | Selected bounding boxes and an optional OpenWaters bearer token. |
| AISStream | Selected bounding boxes, message filters and the AISStream key. |
| OpenFreeMap | Tile coordinates/zoom and the client's IP address; no AIS key, subscription or vessel-position payload. The requested tiles reveal the viewed area. |
| VesselFinder (explicit browser action) | Numeric IMO or MMSI and the browser connection/IP; browser cookies and site policies apply. |
| Photon or a configured HTTPS geocoder | Explicit city search terms and the client's IP address; no AIS key. |
| ipwho.is | IP-geolocation request; the provider observes the client's IP. |
| PyPI/files.pythonhosted.org | Dependency installation requests; no saved AIS key is passed by the installer. |

Pausing AIS reception does not disable map requests while the map is open.
The recent-contact cache is local and never transmitted. It holds up to thirty
minutes of received vessel data and tracks near the monitored location, so it and
cached tile filenames/data can reveal the monitored and viewed areas to someone
with local access. These behaviours are documented in the [README](../README.md#data-and-privacy).

## Dependency check

Rechecked on 2026-09-27 at 00:42 UTC: the [OSV query API](https://google.github.io/osv.dev/api/) returned
no matching advisories for PyPI `websockets` version `17.1`. The pinned portable
wheel URL and SHA-256 matched the
[official PyPI metadata](https://pypi.org/pypi/websockets/17.1/json).
This is a point-in-time package lookup, not proof of absence of vulnerabilities.
The new code adds no runtime dependency. CI pins `actions/checkout` v7.0.1,
`actions/setup-python` v7.0.0 and `actions/setup-node` v7.0.0 to the full commit
SHAs of those tags, and Ruff 0.16.9 to its PyPI wheel hashes; this binds the
reviewed versions but does not establish upstream provenance.

The prior assessment inspected the websockets 17.1 redirect implementation: it strips
sensitive headers across origins, which does not protect a key subsequently placed
in an application message. SR-01 therefore restricts the receiver itself.

Python, OpenSSL, Qt/PySide, Quickshell, Hyprland and the operating system were not
covered by that package advisory query. PySide and Ruff were temporary review tools,
not new plugin dependencies.

## Verification

- **75 Python tests and 48 JavaScript tests pass** through `tests/run`, with the
  managed runtime on Python 3.14.7 and 3.11.16; CI runs the same suite on both
  versions. New checks cover AIS details and sentinels, track bounds and jumps,
  cache round trips, malformed/expired/distant entries, stale-file removal,
  `0600` permissions, type grouping and filters, theme-hue parsing and shortcuts.
- The deterministic MVT mutation regression (1,024 mutations, seed `20260919`)
  still passes. This is targeted robustness testing, not exhaustive fuzzing.
- A real receiver stopped with `SIGTERM` after 8 seconds wrote the cache with
  `0600` permissions; the next start showed 140 restored vessels before connecting.
- A fresh anonymous Genoa capture produced 200 displayed vessel records (104 with
  IMO) and a 1,354,268-byte detailed-map response, using fixed public coordinates
  and no saved user credentials. Timestamps were shifted to render time for the
  screenshots; relative report ages are unchanged.
- Ruff 0.16.9 lint/format checks and the release preflight's structural checks
  pass; its remaining warnings are reviewed above and in earlier assessments.

Test environment: Omarchy on Linux aarch64, Python 3.14.7 and 3.11.16,
websockets 17.1, OpenSSL 3.6.4, Node 26.10, PySide6 6.11.2. Reproduce with:

```sh
python3 backend/vessel.py --prepare-runtime
./tests/run
```

Expanded and compact views were rendered in both palettes with PySide6 and real
local AIS/map captures; layout assertions pass and the four published screenshots
and catalog preview were refreshed. The plugin was loaded in the live Omarchy
shell with no Vessel warnings in its log. Rendering uses a mocked Omarchy host;
an authenticated production AISStream connection remains unverified.

## Remaining trust boundaries and limitations

- Credentials are plaintext with restricted permissions, not encrypted keychain
  entries. Processes running as the same user or root can read them. The checkout,
  Python executable, environment-selected directories and local assets are trusted.
- A compromised upstream or validly authenticated TLS endpoint can still supply
  false map/AIS data. The bounds reduce some denial-of-service risks; this review
  does not prove all inputs have acceptable time/memory cost or audit Qt's native renderer.
- Map/location requests use socket timeouts (10/12 seconds), not an independent
  end-to-end deadline. A slowly streaming peer can keep a helper occupied longer;
  map operations are isolated from the receiver, but updated map views may wait.
- The cache threshold is not a hard disk quota, and coordinate limits are not a
  strict RAM budget. Concurrent helpers and filesystem failures can delay cleanup.
- Legitimate provider redirects are now refused. If a provider requires a new
  endpoint, the configured source must be updated rather than silently forwarding
  credentials or subscriptions.
- Hash-pinning the dependency does not authenticate future plugin Git updates.
  Providers' retention policies, operating-system components, production accounts
  and the actual Omarchy host were not audited.
- The recent-contact cache is plaintext JSON protected by file permissions, within
  the same local-user trust boundary as settings. Reads follow a symlink placed by
  that user; replacement writes do not. The cache written at exit remains until the
  next start, or until the user deletes it.
- Theme `colors.toml` files are read whole, as the Omarchy shell does; a theme is
  trusted local configuration.
- AIS content may be false, stale or incomplete. Vessel is not a navigation instrument.

## Previous reviews

The 2026-09-19 review covered 0.8.2 from commit `cf101ba` (70 Python/41 JavaScript
tests): closed-view cancellation, VesselFinder links and previews, with no new
findings. The earlier 2026-09-19 assessment at `a6c3e8b` added OpenWaters, detailed
maps and SR-01 through SR-06 (64 Python/33 JavaScript tests). The 2026-09-17 report
covered 0.7.0 at commit `73d801fb89b6743286fceac20b1fc9ba89adad9e` (39 Python/22
JavaScript tests). Earlier fixes for huge numbers, invalid text/deep JSON,
public-settings allowlists, file/HTTP size limits, HTTPS downgrade rejection and
installer shutdown races remain covered by the current tests.
