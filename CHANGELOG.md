# Changelog

Notable changes to Vessel. Unreleased changes are listed first; published
versions are listed in reverse chronological order.

## Unreleased

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
