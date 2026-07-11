# Ghost Map: North Merritt Island (Shiloh–Allenhurst corridor)

An interactive overlay of **1943 classified wartime aerial photography** and
**LiDAR bare-earth visualizations** on the modern landscape of north Merritt
Island, Florida — the communities of Allenhurst, Shiloh, Clifton, Wilson, and
Orsino that were bought out for the space program in 1962–63.

**[Open the viewer](viewer/)** — toggle LiDAR layers (multidirectional
hillshade, Local Relief Model, Sky-View Factor), drag the swipe slider to
sweep the 1943 world across today's satellite imagery.

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
3. `download_aerials.py` — fetch archival frames from UF Digital Collections
   (DeepZoom tiles), georeference from UFDC's citation-API footprints
4. `make_tiles.py` — cut XYZ web tiles for the Leaflet viewer

See [PLAN.md](PLAN.md) for data-source notes (UFDC API endpoints, USGS,
NOAA Digital Coast) and the project roadmap.

## Data sources & credits

- Aerials: University of Florida Digital Collections, *Aerial Photography:
  Florida* (USDA 1943 flights, Brevard 6C / Volusia 2C)
- Elevation: USGS 3DEP 1 m DEM (FL Peninsular 2018, Upper St. Johns 2017)
- Basemaps in viewer: Esri World Imagery, OpenStreetMap
- Historical context: NASA KSC Integrated Cultural Resources Management Plan
