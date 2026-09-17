# Vessel

**A little robot. A wide horizon.**

A marine radar for Omarchy. Put a name to the boats on your horizon, with a little robot keeping watch.

See nearby AIS-equipped vessels, their names, speed and reported destinations on a map with coastlines and coastal cities. Vessel follows your Omarchy palette and lives behind a single boat icon in the bar.

![Vessel expanded view with simulated traffic](docs/demo-preview.png)

## Why I built Vessel

When I'm working by the sea, I see boats passing by and always wonder: What's that boat called? Where has it come from? Where is it going?

I wanted a widget I could glance at while working, connecting the boats on the horizon to the information they broadcast, and fitting naturally into my [Outpost](https://github.com/simoz/omarchy-outpost-theme) and [Haven](https://github.com/simoz/omarchy-haven-theme) themes.

## Install

Requires Omarchy 4 with Quickshell plugin support and Python 3.11+ with `venv`.

```sh
omarchy plugin add https://github.com/simoz/omarchy-vessel.git --enable
```

Accept the plugin trust prompt and click the boat icon to open **Settings**. The live receiver's Python dependency is installed automatically on first use.

### Configure

1. Under **LOCATION**, search for a **CITY** and select a result, or choose **IP LOCATION** or **COORDINATES**. Focusing the city field selects its text so you can replace it immediately.
2. Under **COVERAGE**, set the radius (**1–200 nautical miles**) and distance units: **nm**, **km** or **mi**. Speed is shown in **knots (kn)**.
3. Under **AIS CONNECTION**, keep **OpenWaters** selected. No account or key is required. An optional [personal token](https://openwaters.io/ais/) raises the limits. To use **AISStream** instead, select it, click **GET AN API KEY**, and paste your AISStream key.
4. Click **SAVE & CONNECT**. Save and Cancel stay visible while you scroll.

OpenWaters loads recent positions immediately, then streams updates. Positions retain their original timestamps. Anonymous access allows 20 messages/second, two connections per IP and 100 square degrees of coverage; excess messages are thinned. Large radii at high latitudes may require a personal token or a smaller radius.

Once a credential is saved, use **CHANGE** to enter a replacement.
An empty key field preserves the saved credential for that provider. OpenWaters tokens and AISStream keys are stored separately; existing AISStream keys remain available when you select AISStream. Paste a new key to replace it. Preferences and the key are stored in `~/.config/omarchy-vessel/settings.json` (or `$XDG_CONFIG_HOME/omarchy-vessel/settings.json`), with owner-only file permissions (`0600`). Keep this file out of public dotfile backups.

[View Settings](docs/settings-preview.png) · [OpenWaters availability and limits](https://openwaters.io/ais/) · [AISStream documentation](https://aisstream.io/documentation)

## Use the radar

**Rivers and inland waterways:** Vessel is designed for coastal viewing. The offline map contains generalized land and coastlines, without a dedicated river layer, so riverbanks and narrow channels—such as the Thames through London—may be missing. AIS-equipped vessels can still appear where reception is available, but they may look as if they are on land. Zooming in does not add the missing map detail.

| Control | Action |
| --- | --- |
| Boat icon in the bar | Open or close the panel; return to the panel from the expanded window. |
| Expand icon (diagonal arrows, top right) | Switch between the panel and expanded window, keeping zoom and selection. |
| Zoom buttons (+ and −) | Zoom between 1× and 64×. |
| Map drag | Move around the loaded area after zooming in. |
| Center button (crosshair, beside zoom) | Return to your position and reset zoom to 1×. |
| Vessel on the map or in the list | Select a vessel to see its details. Selecting from the list also brings it into view on the map. |
| Status button beside the location | Click to pause reception; click again when it reads PAUSED to resume. Last positions remain visible while paused. |
| Settings button in the footer | Change location, API key, range and units. |
| Keyboard icon (top right) | Open the shortcut guide. You can also press `?` or `F1`. |

The expanded window places vessel details beside the radar when there is enough room. It can be maximized using your normal window-manager controls. Closing it leaves Vessel running in the bar.

The Settings button stays visible in the footer while you scroll. To restart reception, press `R` in the radar view or middle-click the boat icon in the bar.

### Keyboard controls

With the radar view focused:

| Key | Action |
| --- | --- |
| `W` `A` `S` `D` or arrow keys | Pan after zooming in. |
| `+` / `=` / `−` | Zoom in or out. |
| `0` / `Home` | Return to your position and reset zoom. |
| `,` / `.` | Select and reveal the previous or next vessel. |
| `Space` / `P` | Pause or resume reception. |
| `R` | Restart reception. Enter also reconnects when no control consumes the key. |
| `F` | Switch between the panel and expanded window. |
| `<` | Open Settings. |
| `Page Up` / `Page Down` | Scroll the panel. |
| `Tab` / `Shift+Tab` | Focus the next or previous control. |
| `Enter` / `Space` | Activate the focused control. |
| `?` / `F1` | Open the keyboard guide. |
| `Escape` | Close the guide first, then Settings, then the current view. |

When the vessel list has focus, `Up` / `Down` selects vessels. In Settings,
use `Tab` to reach fields, search results and buttons, type normally, and use
`Space` to activate options. Focused settings controls scroll into view automatically.
Letter shortcuts are inactive while editing Settings, and Ctrl/Alt/Super
combinations are left to the desktop.

Triangles indicate vessel course; dots indicate an unknown course. The selected vessel has a ring. Positions fade after five minutes and expire after thirty minutes of active reception.

**VIEW** shows the visible radius. The contact counter shows visible vessels versus all received vessels in range. The list covers the full configured range.

**LIVE** indicates incoming reports, **LISTENING** an active connection awaiting reports, and **PAUSED** a saved view with reception stopped. Reception continues when you close the panel; click the status next to the location to pause it. Click **PAUSED** again to resume. The same control is reachable with Tab and activates with Enter or Space. **REJECTED** indicates a credential, subscription area or connection limit issue.

[Light palette](docs/demo-preview-light.png) · [Zoomed radar](docs/zoom-preview.png) · [Panned map](docs/pan-preview.png) · [Keyboard guide](docs/keyboard-preview.png)

## Update

```sh
omarchy plugin update simoz.vessel --yes; omarchy-shell shell rescanPlugins
```

## Remove

```sh
omarchy plugin remove simoz.vessel
```

Saved preferences and the API key remain in `~/.config/omarchy-vessel/`, and the
Python runtime remains in `~/.local/share/omarchy-vessel/` (or the corresponding
`$XDG_CONFIG_HOME` and `$XDG_DATA_HOME` locations). Remove these directories if
you also want to delete Vessel's saved data.

## Data and privacy

Vessel is built for watching nearby traffic. Coverage and reported destinations depend on the selected provider, receiver coverage and the vessels transmitting. Destinations appear in vessel details only when reported; the text is shown as received and may contain abbreviations or port codes.

- **OpenWaters** (default) receives the geographic area to monitor and your optional OpenWaters token. It aggregates multiple AIS sources; the original attributions are preserved in vessel details. Source-specific terms apply: see [OpenWaters sources and licensing](https://openwaters.io/ais/).
- **AISStream**, when selected, receives your AISStream API key and the geographic area to monitor. Provider switching is manual; credentials are never shared between services.
- **Photon / OpenStreetMap** provides city search from the name you enter.
- **ipwho.is** provides approximate location from your public IP when enabled.
- **Natural Earth** coastlines and **GeoNames** city labels are bundled with the plugin.

Code is licensed under [MIT](LICENSE). Natural Earth data is public domain; GeoNames data is licensed under [CC BY 4.0](https://www.geonames.org/about.html). See [data sources and attribution](data/README.md).

[Development and troubleshooting](docs/development.md) · [Security review](docs/security-review.md)
