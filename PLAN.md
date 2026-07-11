# Ghost Map: North Merritt Island

Overlay pre-NASA archival aerials (1943–1970) and LiDAR bare-earth on the modern
landscape to map the displaced communities of North Merritt Island / KSC /
Merritt Island NWR / Canaveral National Seashore.

## Targets

Communities bought out 1962–63 (and Seashore holdouts into the ~1980s):

- **Allenhurst** — at the Haulover Canal; fishing camp/hotel community
- **Shiloh** — northernmost, citrus town straddling the Volusia line; Shiloh Cemetery survives
- **Clifton** — Black homesteader community (1890s–), Clifton Cemetery
- **Wilson** — between Shiloh and Allenhurst
- **Orsino** — central north island, along the old Courtenay–Shiloh road (pre-SR 3)
- **Audubon / Heath / other place names** — verify against 1943 flight + old plats
- Ft. Ann (already located) — use as a georeferencing control/validation site

## Data sources (verified 2026-07-10)

| Source | What | Access |
|---|---|---|
| UF Digital Collections "Aerial Photography: Florida" | Brevard flights **1943, 1951, 1953, 1954, 1958, 1969, 1970**, 1975+ | https://ufdc.ufl.edu/collections/aerials (index: uflib.ufl.edu/aerials) |
| USGS EarthExplorer → Aerial Photo Single Frames | Federal/military single frames, free medium-res scans | https://earthexplorer.usgs.gov/ |
| FDEP GeoPlan "Historic Aerials in Florida (1937–1985)" | Possibly already-georeferenced mosaics | mapdirect-fdep.opendata.arcgis.com |
| NOAA Digital Coast DAV | LiDAR point clouds + DEMs for the island | https://coast.noaa.gov/dataviewer |
| USGS topoView | Historical topo quads (1949+ show the towns) | https://ngmdb.usgs.gov/topoview/ |
| KSC ICRMP / cultural resources | 465 arch. sites, 31 cemeteries documented on KSC land | public.ksc.nasa.gov/environmental/culturalresources |
| GLO / county plats, LABINS | Original survey plats, section corners for georeferencing | labins.org |

## Pipeline

1. **acquire/** — download aerial frames per epoch (1943, 1958, 1969) + LiDAR DEM tiles
2. **georef/** — GCP-based warping (rasterio/GDAL): pick control points that survive
   (Haulover Canal, road intersections, shorelines, section lines) → GeoTIFFs in EPSG:3857
3. **lidar/** — bare-earth visualizations tuned for flat Florida: multidirectional
   hillshade, **Sky-View Factor**, **Local Relief Model**, slope — not plain hillshade
4. **viewer/** — Leaflet web map: opacity/swipe slider between epochs, modern imagery,
   LiDAR derivatives, and a vector layer of digitized features (buildings, roads,
   groves, cemeteries) with citations
5. **gazetteer/** — every structure visible in 1943 gets a point + what's at that
   spot in LiDAR today (foundation? clearing? nothing?)

## Status

- [x] Sources verified, flight years confirmed
- [x] Python env (rasterio 1.5)
- [x] LiDAR DEM downloaded: six 1m USGS tiles, mosaicked at 2m (15006x10006, EPSG:26917)
- [x] Hillshade / LRM / SVF computed (strip-based, memory-safe) → data/derived/*.tif
- [x] Web tiles z11-16 (2,616 tiles) + Leaflet viewer (viewer/index.html, serve on :8471)
- [x] 1943 frames downloaded: 6C_102/103 (Allenhurst), 2C_47/48 (Shiloh, Volusia collection)
      via UFDC DeepZoom tiles; georeferenced from citation-API bboxes (scans are north-up —
      verified by 8-orientation edge cross-correlation vs modern imagery)
- [x] aerial1943 layer tiled z11-17 (1,305 tiles) + swipe control in viewer — WORKING
- [ ] Add remaining 1943 corridor frames (6C 104-115, 4C 76-81, Volusia 2C 29-49) + 1951/1969 epochs
- [x] Auto-GCP refinement (scripts/auto_gcp.py): patch NCC vs modern imagery ->
      affine per frame. Archive bbox errors found: 6C_102 +136/-72 m, 6C_103 +282/-287 m,
      2C_48 +12/+98 m. Post-fit residuals 14-36 m (remainder = camera tilt; TPS would improve).
      2C_47 could not lock (marsh too changed) — kept archive placement, review manually.
- [ ] Trim film borders (black margins) from frames before merging
- [ ] Fix DEM project seam at easting 520000; refine town pins; build gazetteer layer

## Data-access notes (UFDC)
- Frame footprints: https://api.patron.uflib.ufl.edu/{bibid}/{vid}/citation -> aerial_tiles{} bbox corners
- Images: DeepZoom tiles {ZOOM}?DeepZoom=/home/anubis/resources/{BIBPATH}/{VID}/{file}.jp2_files/{level}/{col}_{row}.jpg
  (BIBPATH = bibid split in 2-char pairs; large IIIF region requests get truncated ~97KB — use DeepZoom)
- Map search: api.patron.uflib.ufl.edu/mapsearch?mapsearchtype=box&... (item-level only)
- LiDAR prospecting note: island's natural grain (relict dunes) bears ~141 deg — cultural
  features often cut across it
