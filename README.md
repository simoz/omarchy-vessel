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

### Get an API key and configure

1. Under **LOCATION**, search for a **CITY** and select a result, or choose **IP LOCATION** or **COORDINATES**. Focusing the city field selects its text so you can replace it immediately.
2. Under **COVERAGE**, set the radius (**1–200 nautical miles**) and distance units: **nm**, **km** or **mi**. Speed is shown in **knots (kn)**.
3. Under **AIS CONNECTION**, click **GET AN API KEY** to open [AISStream Account](https://aisstream.io/account). Sign in with GitHub, create a key and paste it into the field.
4. Click **SAVE & CONNECT**. Save and Cancel stay visible while you scroll.

Once a key is saved, use **CHANGE** to enter a replacement.
An empty key field preserves the saved key. Paste a new key to replace it. Preferences and the key are stored in `~/.config/omarchy-vessel/settings.json` (or `$XDG_CONFIG_HOME/omarchy-vessel/settings.json`), with owner-only file permissions (`0600`). Keep this file out of public dotfile backups.

For a preview, click **TRY DEMO · GENOA** at the bottom of Settings: six simulated boats appear around Genoa. This preserves the saved live location and API key; unsaved form edits are not applied. Save the settings to return to live reception.

[View Settings](docs/settings-preview.png) · [AISStream availability and limits](https://aisstream.io/documentation)

## Use the radar

**Rivers and inland waterways:** Vessel is designed for coastal viewing. The offline map contains generalized land and coastlines, without a dedicated river layer, so riverbanks and narrow channels—such as the Thames through London—may be missing. AIS-equipped vessels can still appear where reception is available, but they may look as if they are on land. Zooming in does not add the missing map detail.

| Control | Action |
| --- | --- |
| Boat icon | Open or close the panel. |
| **⤢ Expand toggle** | Toggle the expanded view from the header, preserving zoom and selection. The icon highlights only on hover. |
| **+ / −** | Zoom between 1× and 64×. |
| Drag the map | Explore the loaded area after zooming in. |
| **⌖** | Return to your position and restore the initial 1× zoom. |
| Click a vessel | Show its name, destination and details. Selecting from the list also brings it into view on the radar. |
| **Reception status next to the location** | Click LIVE, LISTENING or the current status to pause, then PAUSED to resume. Last positions remain visible while paused. |
| **RECONNECT** | Restart reception and refresh your location. |
| **SETTINGS** | Change location, API key, range and units. |
| Keyboard icon / **? / F1** | Open the keyboard shortcut sheet. |

The expanded window places vessel details beside the radar when there is enough room. It can be maximized using your normal window-manager controls. Closing it leaves Vessel running in the bar.

The footer controls stay visible while you scroll. **Escape** closes the panel; **Enter** in the radar panel or a middle-click on the boat reconnects.

### Keyboard controls

With the radar view focused, use **F** to expand or return to the widget,
**W A S D / arrows / H J K L** to pan after zooming, **+ / = / −** to zoom and
**0 / Home** to reset the view. **, / .** selects the previous or next vessel
and brings it into view. **Space / P** pauses or resumes reception,
**R** reconnects, and **<** opens Settings. **Page Up / Page Down** scrolls the panel.

**Tab / Shift+Tab** moves between controls, with a visible focus border.
**Enter / Space** activates the focused radar control; when the vessel list
has focus, **Up / Down** selects vessels. In Settings, use Tab to reach fields,
search results and buttons, type normally, and use Space to toggle options.
Focused settings controls scroll into view automatically.

**? / F1** opens the shortcut sheet in either radar view. **Escape** closes
help first, then Settings, then the current view. Letter shortcuts are inactive
while editing Settings, and Ctrl/Alt/Super combinations are left to the desktop.

Triangles indicate vessel course; dots indicate an unknown course. The selected vessel has a ring. Positions fade after five minutes and expire after thirty minutes of active reception.

**VIEW** shows the visible radius. The contact counter shows visible vessels versus all received vessels in range. The list covers the full configured range.

**LIVE** indicates incoming reports, **LISTENING** an active connection awaiting reports, and **PAUSED** a saved view with reception stopped. Reception continues when you close the panel; click the status next to the location to pause it. Click **PAUSED** again to resume. The same control is reachable with Tab and activates with Enter or Space. **REJECTED** indicates an API key or account connection issue.

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

Vessel is built for watching nearby traffic. Coverage and reported destinations depend on AISStream and the vessels transmitting.

- **AISStream** receives your API key and the geographic area to monitor.
- **Photon / OpenStreetMap** provides city search from the name you enter.
- **ipwho.is** provides approximate location from your public IP when enabled.
- **Natural Earth** coastlines and **GeoNames** city labels are bundled with the plugin.

Code is licensed under [MIT](LICENSE). Natural Earth data is public domain; GeoNames data is licensed under [CC BY 4.0](https://www.geonames.org/about.html). See [data sources and attribution](data/README.md).

[Development and troubleshooting](docs/development.md) · [Security review](docs/security-review.md)
