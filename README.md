# Ghost Map: Northern Indian River Lagoon Basin

**LiDAR bare-earth visualizations** of the Space Coast — all of Brevard County
plus southern Volusia at 2 m resolution — tuned for finding what the landscape
remembers: the displaced communities of Allenhurst, Shiloh, Clifton, Wilson,
and Orsino (bought out for the space program in 1962–63), WWII bombing-range
craters, shell middens, ghost roads, and relict grove grades.

**[Open the viewer](viewer/)** — toggle LiDAR layers (multidirectional
hillshade, Local Relief Model, Sky-View Factor) over modern satellite imagery.
Georeferenced historical aerials are planned as a future layer.

## Reading the LiDAR layers

- **Local Relief Model** — red = locally raised (house pads, causeways, spoil,
  mounds); blue = locally cut (ditches, borrow pits, canals). 25 m kernel.
- **Sky-View Factor** — dark = enclosed/dug features; azimuth-unbiased.
- **Hillshade** — multidirectional (4 azimuths), for general context.
- The island's natural grain (relict dune ridges) bears ~141°. Linear features
  that cut *across* that grain are good cultural-feature candidates.

## Reproduce it / adapt it to your area

Everything is built by the scripts in `scripts/` (Python: rasterio, scipy, PIL):

1. `download_dem.py` — fetch USGS 3DEP 1 m DEM tiles (TNM API)
2. `process_dem.py` — mosaic + hillshade/LRM/SVF, memory-safe strip processing
3. `build_basin.py` / `repair_canvas.py` / `process_basin.py` — county-scale
   streaming build (downloads ~20 GB of DEM within a ~4 GB disk budget)
4. `make_tiles.py` / `make_pmtiles.py` — cut XYZ web tiles / pack PMTiles
5. `download_aerials.py` — archival aerials from UF Digital Collections
   (kept for the future historical-overlay layer; not in the current build)

See [PLAN.md](PLAN.md) for data-source notes (UFDC API endpoints, USGS,
NOAA Digital Coast) and the project roadmap.

## Data sources & credits

- Aerials: University of Florida Digital Collections, *Aerial Photography:
  Florida* (USDA 1943 flights, Brevard 6C / Volusia 2C)
- Elevation: USGS 3DEP 1 m DEM (FL Peninsular 2018, Upper St. Johns 2017)
- Basemaps in viewer: Esri World Imagery, OpenStreetMap
- Historical context: NASA KSC Integrated Cultural Resources Management Plan
