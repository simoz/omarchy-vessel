# Offline basemap

`basemap.json.gz` is the offline fallback. Detailed views load OpenFreeMap's
OpenMapTiles-schema vector tiles on demand, with attribution to OpenFreeMap,
OpenMapTiles and OpenStreetMap below the radar. These tiles are cached in the
user's cache directory and are not bundled here. See [OpenFreeMap](https://openfreemap.org/)
and [OpenStreetMap's data licence](https://www.openstreetmap.org/copyright).

`basemap.json.gz` contains global land polygons and coastlines from **Natural Earth**, sourced from the `v5.1.2` release of its vector repository:

- [ne_10m_land.geojson](https://github.com/nvkelso/natural-earth-vector/blob/v5.1.2/geojson/ne_10m_land.geojson)
- [ne_10m_coastline.geojson](https://github.com/nvkelso/natural-earth-vector/blob/v5.1.2/geojson/ne_10m_coastline.geojson)

Natural Earth data is **public domain**, independently of Vessel's MIT code license. See [Natural Earth's terms](https://www.naturalearthdata.com/about/terms-of-use/).

The `10m` in the dataset name means **1:10 million map scale**, not ten-metre accuracy. This is a generalized coastline for orientation: it does not resolve docks, narrow channels, every island or every inland water body. It is not a nautical chart.

## Rebuild

Download the two versioned GeoJSON files, then run:

```sh
python3 tools/build_basemap.py /path/to/ne_10m_land.geojson /path/to/ne_10m_coastline.geojson
```

The builder flattens multipart features, records bounding boxes, rounds coordinates to five decimal places and uses deterministic gzip output. It preserves polygon holes. No runtime download, map token, external tiles or extra Python package is needed.

At startup, Python clips nearby geometry to geographic bounding boxes and projects it with the same distance/bearing functions used for vessels. QML receives only this local view once. Land fills and coastline strokes remain separate so clipping edges and polygon partition seams are not mistaken for shores.


## Coastal city labels

`coastal-cities.json.gz` is derived from [GeoNames cities5000.zip](https://download.geonames.org/export/dump/cities5000.zip),
downloaded on 2026-09-16. Attribution: **GeoNames**, licensed under
[Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/).
See the [dataset description](https://download.geonames.org/export/dump/readme.txt).
This license applies to city data; application code remains MIT and Natural Earth
geometry remains public domain.

Source archive SHA-256:
`7f0e5c501823a24bf4c3cc7bc0bd9cd3f88247427964b6047e4acddf72604fc4`

The extract contains 14,274 populated places within approximately 8 nautical miles
of the bundled Natural Earth coastline. The source mainly includes settlements
with population over 5,000, plus selected administrative seats. City sections,
historical and abandoned settlements are excluded. Fields are reduced to name,
identifier, coordinates, population and country. Genoa's name is normalized to
English. Coast proximity is calculated against a generalized map, so this is an
orientation layer rather than an authoritative classification of coastal towns.

To rebuild with a downloaded source archive:

```sh
python3 tools/build_cities.py /path/to/cities5000.zip
```

The builder uses only Python's standard library and includes the source hash in
the output. Population determines label priority; the UI hides colliding labels
and projects them with the same coordinates and zoom as the map. Missing city data
does not prevent vessel tracking or the basemap from working. No online geocoding
is used to draw these labels.
