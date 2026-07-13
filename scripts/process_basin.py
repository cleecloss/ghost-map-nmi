"""Block-wise processing of the basin canvas into hillshade/LRM/SVF web tiles.

Reads data/basin_dem_2m.tif in N-S blocks (with kernel padding), computes the
three visualizations strip-by-strip inside each block, writes per-block RGBA
GeoTIFFs, tiles them (compositing over existing tiles at block seams), then
deletes the block intermediates. Resumable via data/basin_blocks_done.json.
"""
import json, os, shutil
import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.transform import from_origin

from process_dem import hillshade_multi, svf, lrm, gray_rgb, diverging_rgb
from make_tiles import tile_raster

BASE = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(BASE, "data")
CANVAS = os.path.join(DATA, "basin_dem_2m.tif")
DONE = os.path.join(DATA, "basin_blocks_done.json")
TMP = os.path.join(DATA, "tmp_block")
RES = 2.0
BLOCK = 8000       # core rows per block
PAD = 64           # kernel padding rows
STRIP = 800        # strip rows within a block (RAM safety at 30k cols)
F32 = np.float32

def process_block(src, row0, rows):
    """Compute the three RGBA layers for canvas rows [row0, row0+rows)."""
    os.makedirs(TMP, exist_ok=True)
    W = src.width
    tr = src.transform
    block_tr = from_origin(tr.c, tr.f + tr.e * row0, RES, RES)
    prof = dict(driver="GTiff", width=W, height=rows, count=4, dtype="uint8",
                crs=src.crs, transform=block_tr, compress="deflate",
                tiled=True, BIGTIFF="IF_SAFER", photometric="RGB")
    paths = {n: os.path.join(TMP, f"{n}.tif") for n in ("hillshade", "lrm", "svf")}
    outs = {n: rasterio.open(p, "w", **prof) for n, p in paths.items()}
    any_land = False

    for s0 in range(0, rows, STRIP):
        core_rows = min(STRIP, rows - s0)
        a_lo = max(0, row0 + s0 - PAD)
        a_hi = min(src.height, row0 + s0 + core_rows + PAD)
        z = src.read(1, window=Window(0, a_lo, W, a_hi - a_lo)).astype(F32)
        land = np.isfinite(z) & (z > -0.2)
        z = np.nan_to_num(z, nan=0.0)
        core = slice(row0 + s0 - a_lo, row0 + s0 - a_lo + core_rows)
        win = Window(0, s0, W, core_rows)
        alpha = np.where(land[core], 255, 0).astype(np.uint8)
        if alpha.max() == 0:
            for o in outs.values():
                o.write(np.zeros((4, core_rows, W), dtype=np.uint8), window=win)
            continue
        any_land = True
        results = {
            "hillshade": gray_rgb(hillshade_multi(z)[core], 0.35, 1.0),
            "lrm": diverging_rgb(lrm(z)[core], 0.5),
            "svf": gray_rgb(svf(z)[core], 0.80, 1.0),
        }
        for name, rgb in results.items():
            for band in range(3):
                outs[name].write(rgb[band], band + 1, window=win)
            outs[name].write(alpha, 4, window=win)
        print(f"  strip {s0 + core_rows}/{rows}", flush=True)
    for o in outs.values():
        o.close()
    return paths if any_land else None

def main():
    done = set(json.load(open(DONE))) if os.path.exists(DONE) else set()
    src = rasterio.open(CANVAS)
    blocks = list(range(0, src.height, BLOCK))
    print(f"{len(blocks)} blocks, {len(done)} done", flush=True)
    for row0 in blocks:
        if str(row0) in done:
            continue
        rows = min(BLOCK, src.height - row0)
        print(f"block @row {row0} ({rows} rows)", flush=True)
        paths = process_block(src, row0, rows)
        if paths:
            for name, p in paths.items():
                tile_raster(p, name, 11, 16, composite=True)
        shutil.rmtree(TMP, ignore_errors=True)
        done.add(str(row0))
        json.dump(sorted(done), open(DONE, "w"))
        print(f"block @row {row0} DONE", flush=True)
    src.close()
    print("BASIN PROCESSING COMPLETE", flush=True)

if __name__ == "__main__":
    main()
