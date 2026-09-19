# Changelog

Notable changes to Vessel, listed in reverse chronological order after Unreleased.

Versions before 0.7.1 were reconstructed from Git history and changes to
`manifest.json`: their links and dates refer to the version-bump commits, not
verified release publications. Each entry covers changes since the previous
version commit. From 0.7.1 onward, version headings link to release tags.

## Unreleased

## [0.8.0](https://github.com/simoz/omarchy-vessel/releases/tag/v0.8.0) — 2026-09-19

### Fixed

- Show a loading state while detailed geography is pending; display the offline
  map only when detail loading fails, avoiding a cartography flash on opening.
- Size the bar button from the boat icon instead of a hidden font glyph, avoiding
  font-dependent extra spacing.

### Added

- Detailed OpenFreeMap vector maps that increase geographic detail as you zoom,
  including coastlines, docks, rivers, roads and local place names.
- Local tile caching, offline fallback and visible map-source attribution.
- Regression tests for tile decoding, nautical alignment, viewport bounds,
  cache behaviour, stale responses and zoom controls.

### Changed

- Match Omastorm's zoom controls: mouse-wheel events use a 0.85 range factor,
  while buttons and keyboard shortcuts use 1.25× steps. Large wheel deltas no
  longer cause larger jumps. Zoom remains bounded between 1× and 64×.
- Load complete map batches after navigation settles, independently of AIS
  reception. Ignore replies for viewports the user has already left.
- Render detailed geography in the radar's theme and nautical coordinate system;
  retain the bundled map when detailed coverage is unavailable.
- Separate offline map drawing and city labels into dedicated QML components.
- Simplify tile selection, vector decoding and QML event handlers, with named
  parameters and comments explaining coordinates, ownership and cache behaviour.
- Document map-network requests, cache storage and the UI's code structure.

### Security

- Refuse WebSocket redirects so AIS subscriptions and credentials reach only the
  explicitly configured provider; confine map redirects to the OpenFreeMap host.
- Enforce geometry limits on polygon closure and on generated projected points.
- Reject out-of-tile labels before projection, evict malformed map catalogs, and
  bound cache reads even if a file changes during the read.
- Repeat and document the security review, with regression coverage and a fresh
  dependency advisory/hash check. See [security review](docs/security-review.md).

## [0.7.3](https://github.com/simoz/omarchy-vessel/releases/tag/v0.7.3) — 2026-09-19

### Changed

- Reduce mouse-wheel sensitivity: four standard wheel notches double the zoom.
- Scale zoom changes proportionally to wheel movement for finer trackpad control.
- Preserve pointer anchoring and the 1×–64× zoom range.

## [0.7.2](https://github.com/simoz/omarchy-vessel/releases/tag/v0.7.2) — 2026-09-19

### Added

- Mouse-wheel zoom over the radar: scroll up to zoom in and down to zoom out.
- Keep the map point under the pointer fixed within loaded coverage.
- Preserve drag continuity when using the wheel during a drag.
- Document the mouse-wheel control.

## [0.7.1](https://github.com/simoz/omarchy-vessel/releases/tag/v0.7.1) — 2026-09-18

### Changed

- Replace the bar icon with a compact side-profile ship.
- Use Omarchy's standard icon slot and margins, with a 16-unit icon instead of 20.
- Make OpenWaters the default AIS provider, with optional tokens and AISStream
  available as an alternative; keep provider credentials separate.
- Load recent OpenWaters positions before streaming updates and preserve source
  attributions in vessel details.
- Remove the demo option from Settings while retaining the command-line demo.
- Distinguish stationary vessels, moving vessels and unknown speed with clearer
  radar markers; simplify moving-vessel icons.
- Refine panel/window navigation and reception controls, and refresh the
  documented security review.

### Fixed

- Prevent vessel markers and list entries from flickering during live updates.

## [0.7.0](https://github.com/simoz/omarchy-vessel/commit/40dc70e2577748ef42ae4db3b18057521f6b22b7) — 2026-09-17

### Added

- Expandable radar window with a responsive layout and preserved zoom/selection.
- Keyboard navigation, vessel selection, reception controls and a shortcut guide.
- Statute miles alongside nautical miles and kilometres in Settings.

### Changed

- Reorganize Settings into location, coverage and connection sections, with
  persistent Save/Cancel controls and a separate demo action.
- Move pause/resume into the status control beside the location.
- Refine the header, expanded-view controls and destination details; animate the
  robot's eyes while listening.
- Refresh previews and installation/removal documentation.

### Fixed

- Keep the radar sweep running across panel/window transitions.
- Center shortcut help in the expanded window and correct the expand button's
  active/focus state when returning to the panel.

## [0.6.2](https://github.com/simoz/omarchy-vessel/commit/3f3c5d664a065d8a0ebc49501a2d8c0ed9149332) — 2026-09-16

### Fixed

- Reset zoom to 1× as well as recentering the map when resetting the radar view.

## [0.6.1](https://github.com/simoz/omarchy-vessel/commit/5e81faaea3e93601bd0db81cfe417f55e337687b) — 2026-09-16

### Fixed

- Keep panel controls visible while scrolling.
- Bring a vessel into the radar viewport when selecting it from the list.

## [0.6.0](https://github.com/simoz/omarchy-vessel/commit/bb6f82959047d7f5e76ba3bfa4f00e49c4dcbf2d) — 2026-09-16

### Changed

- Keep only the boat icon in the bar and move pause/resume into the panel footer.

### Fixed

- Continue the radar sweep while the map is panned away from the lookout.

## [0.5.1](https://github.com/simoz/omarchy-vessel/commit/bfcbcde2f41ae3e54f5d544d69c5a520ee31cebf) — 2026-09-16

### Changed

- Separate AIS parsing, WebSocket reception and bounded HTTPS requests into
  dedicated backend modules.
- Add a documented security review and regression tests for untrusted input.

### Security

- Prevent oversized numeric AIS fields from terminating the receiver, validate
  text fields and handle deeply nested JSON safely.
- Validate settings on read and save, and allow only public preference fields in
  responses to the interface.
- Bound settings and location-response reads; reject plaintext redirects and
  credential-bearing URLs in location requests.
- Handle installer shutdown races and verify that its environment excludes the
  AIS credential.

## [0.5.0](https://github.com/simoz/omarchy-vessel/commit/f67b39807add1b3a86b7960ffbccbd6ad5c0f49c) — 2026-09-16

### Added

- Shared pause/resume toggle beside the bar icon, closing the AIS connection
  while retaining the last displayed positions. Resume starts a fresh connection.
- Synchronize reception state across monitors.

## [0.4.3](https://github.com/simoz/omarchy-vessel/commit/d38b5e721f6343c238e46f6b95ff5f365d246b35) — 2026-09-16

### Fixed

- Open Settings links through Omarchy's browser launcher.

## [0.4.2](https://github.com/simoz/omarchy-vessel/commit/fbf2cde99b3c61230f2517db5b55a4f49212eada) — 2026-09-16

### Changed

- Extend the maximum radar zoom from 8× to 64×.

## [0.4.1](https://github.com/simoz/omarchy-vessel/commit/6486ecdb991f03cc864680002c7b8d6c09785c44) — 2026-09-16

### Fixed

- Center the recenter reticle independently of font metrics.

## [0.4.0](https://github.com/simoz/omarchy-vessel/commit/6325db600cb2c72d25ae18b7be18905be5f0f182) — 2026-09-16

### Added

- Drag the zoomed map within loaded coverage without reconnecting AIS.
- Recenter control to return to the lookout position.

## [0.3.1](https://github.com/simoz/omarchy-vessel/commit/caa36f5c0063b9f511f602b66906347cd503d466) — 2026-09-16

### Changed

- Replace pixel-art boats on the radar with compact directional markers.

## [0.3.0](https://github.com/simoz/omarchy-vessel/commit/f461cb474a07afdf5e35cbfab915ac8390a4d88e) — 2026-09-16

### Added

- Radar zoom at 1×, 2×, 4× and 8× without changing the AIS subscription.
- Bundled GeoNames coastal city labels with theme-aware text and collision
  avoidance.
- Visible-range indication and a visible/received contact count; retain contacts
  outside the viewport in the list.

## [0.2.0](https://github.com/simoz/omarchy-vessel/commit/3311af71b3ab1903654144f8ca66a32a4e92b327) — 2026-09-16

### Added

- Explicit Photon city search with selectable results, session caching and saved
  location names; retain manual coordinates as a fallback.
- Subtle radar sweep, paused while the radar is hidden.

### Changed

- Use a compact boat icon in the bar and document plugin updates.

## [0.1.0](https://github.com/simoz/omarchy-vessel/commit/774ddeda5f24b6d6cc19f09fb6b2af3bda2d5084) — 2026-09-16

### Added

- Initial theme-aware marine radar for Omarchy, with vessel selection, a
  distance-sorted contact list and vessel details.
- Shared AISStream reception across monitors, Class A/B reports, static vessel
  information, automatic reconnection and stale-contact expiry.
- Bundled Natural Earth land/coastline map and an offline Genoa traffic demo.
- IP or fixed-coordinate location, a 1–200 nautical mile coverage radius and
  distances in nautical miles or kilometres.
- Graphical settings with owner-only credential storage and a managed Python
  environment using a pinned, hash-verified WebSocket dependency.
- Backend/receiver tests, preview tools and installation documentation.
