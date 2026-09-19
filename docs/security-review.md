# Security review

Reviewed on **2026-09-19**. The reviewed runtime and tests are now recorded in
commit `a6c3e8b74d8d3ae1c2b99cb986024d788fe4e7ba`, including the unreleased vector
maps, zoom changes, QML refactor and the fixes described below. This documentation
update follows that commit. The preceding release is 0.7.3 at
`87d544ae2d8fbc0be4a08107422171a784b49fef`.
The manifest still reads 0.7.3; this report does **not** claim that these fixes are
in the published 0.7.3 release. File hashes and dependency-check results are recorded
in [security-review-evidence.json](security-review-evidence.json).

## Scope and result

The review inspected the receiver and credential paths, settings storage,
subprocess/runtime setup, HTTPS requests and redirects, vector parsing,
projection, tile caching, and QML data/rendering boundaries. Checks combined source
inspection, adversarial inputs, local WebSocket servers and the regression suite.
No production credentials were used, and no third-party service was penetration-tested.

The pass identified and fixed a credential-destination issue in redirected
AISStream connections, two geometry-budget gaps, and several map-input/cache
hardening issues. The credential redirect and polygon-closure issue were reproduced
before the fixes. There is no evidence from this review of exploitation in a deployed
installation. Remaining trust boundaries and availability limits are listed below;
this is not a security certification.

## Findings and fixes

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
  records and exposes at most 200 contacts. Pause, reconnect and cancellation
  tests continue to pass.
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
| Photon or a configured HTTPS geocoder | Explicit city search terms and the client's IP address; no AIS key. |
| ipwho.is | IP-geolocation request; the provider observes the client's IP. |
| PyPI/files.pythonhosted.org | Dependency installation requests; no saved AIS key is passed by the installer. |

Pausing AIS reception does not disable map requests while the map is open. No persistent vessel-position history is written;
cached tile filenames/data can reveal areas previously viewed to someone with local
access. These behaviours are documented in the [README](../README.md#data-and-privacy).

## Dependency check

On 2026-09-19, the [OSV query API](https://google.github.io/osv.dev/api/) returned
no matching advisories for PyPI `websockets` version `17.1`. The pinned portable
wheel URL and SHA-256 matched the
[official PyPI metadata](https://pypi.org/pypi/websockets/17.1/json).
This is a point-in-time package lookup, not proof of absence of vulnerabilities.

The installed websockets 17.1 redirect implementation was also inspected: it strips
sensitive headers across origins, which does not protect a key subsequently placed
in an application message. SR-01 therefore restricts the receiver itself.

Python, OpenSSL, Qt/PySide, Quickshell, Hyprland and the operating system were not
covered by that package advisory query. PySide and Ruff were temporary review tools,
not new plugin dependencies.

## Verification

- **64 Python tests and 33 JavaScript tests pass.** Python checks include private
  settings, TLS rejection, provider credential isolation, redirects, cache errors,
  invalid geometry and resource limits. JavaScript checks include map-response
  ordering, closed views, retry behaviour, mouse/keyboard zoom and settings submission.
- One parser regression runs **1,024 deterministic mutations** of a small valid MVT
  fixture (seed `20260919`). Accepted inputs decode; rejected inputs fail with the
  controlled exception type. This is targeted robustness testing, not exhaustive fuzzing.
- The local redirect regression first failed because the second server received the
  synthetic AISStream key, then passed after redirects were disabled. Those two peers
  use loopback WS; certificate verification is covered by the separate TLS test.
- A cached real Genoa viewport still completes after the fixes: four level-11 tiles,
  a 464,053-byte JSON response. It uses public fixture coordinates, no user location
  or credentials, and no fresh map download during this pass.
- Ruff lint/format checks and Git whitespace checks pass. The negative TLS test may
  emit a local handshake-reset diagnostic while its security assertions pass.

Test environment: macOS, Python 3.14.5, websockets 17.1, OpenSSL 3.6.4.
The full suite needs permission to bind local loopback test servers. Reproduce with
an interpreter containing the dependency pinned in `requirements.txt`:

```sh
python -B -m unittest discover -s tests -p 'test_*.py'
node --test tests/*.test.cjs
ruff check backend tools tests
ruff format --check backend tools tests
```

Qt rendering, pointer anchoring and the refactored service were checked earlier
in this session with a mocked Omarchy host. They were not repeated as part of this
security pass, which makes no QML changes. Real Quickshell/Hyprland operation and
an authenticated production AISStream connection remain unverified here.

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
- AIS content may be false, stale or incomplete. Vessel is not a navigation instrument.

## Previous review

The 2026-09-17 report covered 0.7.0 at commit
`73d801fb89b6743286fceac20b1fc9ba89adad9e` and reported 39 Python/22 JavaScript tests.
Earlier fixes for huge numbers, invalid text/deep JSON, public-settings allowlists,
file/HTTP size limits, HTTPS downgrade rejection and installer shutdown races remain
covered by the current tests. This report supersedes the earlier snapshot and adds
OpenWaters, detailed maps and the findings above.
