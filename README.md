# Vessel

**A little robot. A wide horizon.**

A marine radar for Omarchy. Put a name to the boats on your horizon, with a little robot keeping watch.

See nearby AIS-equipped vessels, their names, speed and reported destinations on a map with coastlines and coastal cities. Vessel follows your Omarchy palette and lives behind a single boat icon in the bar.

![Vessel with simulated traffic](docs/demo-preview.png)

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

1. Click **GET AN API KEY** to open [AISStream Account](https://aisstream.io/account).
2. Sign in with GitHub, create a key and paste it into **AISStream API key** in the widget.
3. Choose approximate IP location, search for a city, or enter coordinates.
4. Set the coverage radius (**1–200 nautical miles**) and distance units: **nm**, **km** or **mi**. Speed is shown in **knots (kn)**.
5. Click **SAVE & CONNECT**.

An empty key field preserves the saved key. Paste a new key to replace it. Preferences and the key are stored in `~/.config/omarchy-vessel/settings.json` (or `$XDG_CONFIG_HOME/omarchy-vessel/settings.json`), with owner-only file permissions (`0600`). Keep this file out of public dotfile backups.

For a preview, select **Offline demo · Genoa (Italy)** in Settings: six simulated boats appear around Genoa.

[View Settings](docs/settings-preview.png) · [AISStream availability and limits](https://aisstream.io/documentation)

## Use the radar

| Control | Action |
| --- | --- |
| Boat icon | Open or close the panel. |
| **+ / −** | Zoom between 1× and 64×. |
| Drag the map | Explore the loaded area after zooming in. |
| **⌖** | Return to your position and restore the initial 1× zoom. |
| Click a vessel | Show its name, destination and details. Selecting from the list also brings it into view on the radar. |
| **PAUSE / RESUME** | Stop reception while keeping the last positions, or reconnect and receive fresh reports. |
| **RECONNECT** | Restart reception and refresh your location. |
| **SETTINGS** | Change location, API key, range and units. |

The footer controls stay visible while you scroll. **Escape** closes the panel; **Enter** in the radar panel or a middle-click on the boat reconnects.

Triangles indicate vessel course; dots indicate an unknown course. The selected vessel has a ring. Positions fade after five minutes and expire after thirty minutes of active reception.

**VIEW** shows the visible radius. The contact counter shows visible vessels versus all received vessels in range. The list covers the full configured range.

**LIVE** indicates incoming reports, **LISTENING** an active connection awaiting reports, and **PAUSED** a saved view with reception stopped. Reception continues when you close the panel; use **PAUSE** to stop it. **REJECTED** indicates an API key or account connection issue.

[Light palette](docs/demo-preview-light.png) · [Zoomed radar](docs/zoom-preview.png) · [Panned map](docs/pan-preview.png)

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
