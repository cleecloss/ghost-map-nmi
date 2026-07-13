"""Pack each XYZ tile tree into a single .pmtiles archive (data/pmtiles/).
One archive per layer; tiles written in tileid order for spatial clustering.
"""
import os, sys
from pmtiles.writer import Writer
from pmtiles.tile import zxy_to_tileid, TileType, Compression

BASE = os.path.join(os.path.dirname(__file__), "..")
TILE_ROOT = os.path.join(BASE, "viewer", "tiles")
OUT_DIR = os.path.join(BASE, "data", "pmtiles")
os.makedirs(OUT_DIR, exist_ok=True)

# basin bounds (lon/lat e7) and sensible center
BOUNDS = dict(min_lon_e7=int(-81.06e7), min_lat_e7=int(27.79e7),
              max_lon_e7=int(-80.44e7), max_lat_e7=int(29.06e7))
CENTER = dict(center_zoom=11, center_lon_e7=int(-80.75e7), center_lat_e7=int(28.55e7))

layers = sys.argv[1:] or ["hillshade", "lrm", "svf", "aerial1943"]
for layer in layers:
    root = os.path.join(TILE_ROOT, layer)
    if not os.path.isdir(root):
        print("skip", layer); continue
    entries = []
    zooms = []
    for zdir in os.listdir(root):
        z = int(zdir)
        zooms.append(z)
        for xdir in os.listdir(os.path.join(root, zdir)):
            x = int(xdir)
            for yfile in os.listdir(os.path.join(root, zdir, xdir)):
                y = int(os.path.splitext(yfile)[0])
                entries.append((zxy_to_tileid(z, x, y), z, x, y))
    entries.sort()
    out_path = os.path.join(OUT_DIR, f"{layer}.pmtiles")
    with open(out_path, "wb") as f:
        w = Writer(f)
        for tid, z, x, y in entries:
            with open(os.path.join(root, str(z), str(x), f"{y}.png"), "rb") as t:
                w.write_tile(tid, t.read())
        header = dict(tile_type=TileType.PNG, tile_compression=Compression.NONE,
                      min_zoom=min(zooms), max_zoom=max(zooms), **BOUNDS, **CENTER)
        w.finalize(header, {"name": f"ghost-map {layer}", "format": "png"})
    print(f"{layer}: {len(entries)} tiles -> {out_path} "
          f"({os.path.getsize(out_path)/1e6:.0f} MB)", flush=True)
print("PMTILES COMPLETE", flush=True)
