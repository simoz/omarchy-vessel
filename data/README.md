# Offline basemap

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
