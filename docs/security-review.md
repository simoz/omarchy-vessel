# Security review

Reviewed on 2026-09-16 for Vessel 0.5.1.

## Scope and result

This review covered all runtime Python, QML and JavaScript sources, the offline
asset builders, settings storage, subprocess execution, dependency installation,
and existing tests. It combined source inspection with regression tests and local
WebSocket peers. It is not a penetration test of Omarchy or AISStream, nor a
security certification.

A malformed numeric AIS field could terminate the receiver. That reproducible
availability bug is fixed. The review also tightened settings and HTTPS boundaries
without adding production dependencies or changing the normal UI workflow.

## Changes made

| Area | Finding | Resolution |
| --- | --- | --- |
| AIS parsing | `math.isfinite()` raised `OverflowError` for a JSON integer larger than the floating-point range. | Check numeric bounds first. Invalid coordinates are ignored; invalid speed/course become unknown. Regression tests pass a 401-digit integer through the receiver. |
| Text and JSON | Structured values were converted into display strings; deeply nested JSON can raise `RecursionError` on supported Python versions. | Accept strings for AIS names/destinations and handle parser recursion failures. |
| Settings | Saved files bypassed the editor's validation, and public responses excluded only the current `apiKey` field. | Share validation between reading and saving; explicitly allow only public preference fields in responses. A corrected edit can repair invalid saved values. |
| File and HTTP sizes | Settings files had no read limit; location services used separate request code. | Limit settings to 64 KiB, IP responses to 64 KiB and city responses to 256 KiB. |
| HTTPS redirects | The default HTTP client permits an HTTPS request to redirect to HTTP. No malicious redirect was observed. | Reject plaintext redirects and URLs containing credentials in the shared location-request helper. |
| Installer shutdown | A child can exit between checking its state and terminating its process group. | Tolerate that race while still reaping the child; test that installer environments exclude the AIS key. |

The last four entries include defensive improvements; they do not establish that
credentials were previously exposed or that an attacker exploited the plugin.

## Existing protections retained and checked

- Credentials travel from the editor to Python over stdin, not command arguments.
  Settings use an atomic replacement and a `0600` file, with a `0700` directory
  when first created. Failed writes preserve the old credential and remove the
  temporary file. An empty editor field preserves the saved key.
- Public settings expose only whether a key exists. AIS subscription errors use
  fixed messages rather than echoing server text, and the WebSocket logger is
  isolated from application logging.
- Commands are argument arrays, without shell interpolation. Browser links are
  fixed URLs. Provider text in the settings/panel is rendered as plain text or
  Canvas text, not executable markup.
- The receiver uses TLS verification. Tests confirm that a peer with an untrusted
  certificate cannot receive the subscription/key. WebSocket messages are limited
  to 1 MiB; the fleet is limited to 2,000 records and 200 displayed contacts.
- Pause terminates the receiver and cancels scheduled restarts. Resume creates a
  fresh connection. Cancellation and reconnect tests check that old connections
  close and subscriptions do not overlap.
- The single live dependency is a specific portable `websockets` 17.1 wheel with
  a SHA-256 pin, installed with `--require-hashes`, `--no-deps`, `--only-binary`
  and pip's isolated mode. No elevated privileges or compilation are needed.
  Dependency installation has timeouts, a process-group cleanup path and a lock.
- City/IP services receive location-related requests, never the AIS key. Demo mode
  makes no network requests. No persistent vessel-position history is written.

## Dependency check

The [OSV API](https://google.github.io/osv.dev/api/#tag/vulnerability/operation/OSV_Query)
query for PyPI `websockets` version `17.1` returned no matching advisories on the
review date. The pinned wheel URL and hash also matched the
[official PyPI release metadata](https://pypi.org/pypi/websockets/17.1/json).
This is a point-in-time check, not proof that the dependency has no vulnerabilities.
Python, OpenSSL, Qt and Omarchy are supplied by the operating system and were not
included in that package advisory query.

## Verification and limits

The automated suite (38 Python tests and 13 JavaScript tests) covers malformed AIS data, private settings, atomic-write
failure, HTTPS redirects, TLS rejection, binary/compressed messages, reconnection,
cancellation, geometry, demo startup and installer failures. Qt checks exercise
settings, zoom, drag, recenter and pause/resume with a mock Omarchy host.

Remaining trust boundaries:

- The API key is stored in plaintext with restricted file permissions, not in an
  encrypted keychain. Code running as the same user or as root can read it.
  Public dotfile backups must exclude the settings file.
- Omarchy plugins execute with the user's privileges. The checkout, configured
  Python executable, bundled assets and user-selected directories are trusted.
  Hash-pinning the wheel does not authenticate future plugin Git updates.
- AISStream receives the API key and the selected geographic bounding boxes.
  Photon receives city searches, and IP geolocation reveals the caller's public
  IP to its provider. HTTPS protects transport, not the provider's use of data.
- AIS content and reported destinations are not authenticated by Vessel and may
  be wrong or stale. The plugin is not a navigation instrument.
- An authenticated AISStream session and the real Quickshell/Hyprland integration
  still need testing on Omarchy; the local tests cannot establish those results.
