"""Cut XYZ web tiles (EPSG:3857) from the derived RGBA GeoTIFFs.
Usage: make_tiles.py [layer ...] [zmin zmax]   (defaults: all LiDAR layers, 11-16)
"""
import os, sys, math
import numpy as np
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from rasterio.windows import from_bounds, Window
from PIL import Image

BASE = os.path.join(os.path.dirname(__file__), "..")
DERIVED = os.path.join(BASE, "data", "derived")
TILE_ROOT = os.path.join(BASE, "viewer", "tiles")
args = sys.argv[1:]
zooms = [a for a in args if a.isdigit()]
LAYERS = [a for a in args if not a.isdigit()] or ["hillshade", "lrm", "svf"]
ZMIN, ZMAX = (int(zooms[0]), int(zooms[1])) if len(zooms) == 2 else (11, 16)
COMPOSITE = False  # merge new content over existing tiles (block-seam support)
WEB = "EPSG:3857"
ORIGIN = 20037508.342789244

def tile_bounds(z, x, y):
    n = 2 ** z
    size = 2 * ORIGIN / n
    minx = -ORIGIN + x * size
    maxy = ORIGIN - y * size
    return minx, maxy - size, minx + size, maxy

def tiles_for_bounds(z, b):
    n = 2 ** z
    size = 2 * ORIGIN / n
    x0 = max(0, int((b[0] + ORIGIN) // size))
    x1 = min(n - 1, int((b[2] + ORIGIN) // size))
    y0 = max(0, int((ORIGIN - b[3]) // size))
    y1 = min(n - 1, int((ORIGIN - b[1]) // size))
    return range(x0, x1 + 1), range(y0, y1 + 1)

def tile_raster(src_path, layer, zmin=ZMIN, zmax=ZMAX, composite=False):
    """Cut XYZ tiles for one RGBA raster; optionally composite over existing."""
    global ZMIN, ZMAX
    ZMIN, ZMAX = zmin, zmax
    with rasterio.open(src_path) as src, WarpedVRT(
            src, crs=WEB, resampling=Resampling.bilinear, add_alpha=False) as vrt:
        b = vrt.bounds
        count = 0
        for z in range(ZMIN, ZMAX + 1):
            xs, ys = tiles_for_bounds(z, b)
            for x in xs:
                for y in ys:
                    tb = tile_bounds(z, x, y)
                    win = from_bounds(*tb, transform=vrt.transform)
                    # clip to raster extent; WarpedVRT forbids boundless reads
                    full = Window(0, 0, vrt.width, vrt.height)
                    try:
                        clip = win.intersection(full)
                    except Exception:
                        continue
                    if clip.width < 1 or clip.height < 1:
                        continue
                    oh = max(1, round(clip.height / win.height * 256))
                    ow = max(1, round(clip.width / win.width * 256))
                    part = vrt.read(window=clip, out_shape=(4, oh, ow))
                    data = np.zeros((4, 256, 256), dtype=np.uint8)
                    ry = round((clip.row_off - win.row_off) / win.height * 256)
                    rx = round((clip.col_off - win.col_off) / win.width * 256)
                    ry, rx = max(0, min(ry, 256 - oh)), max(0, min(rx, 256 - ow))
                    data[:, ry:ry + oh, rx:rx + ow] = part
                    if data[3].max() == 0:
                        continue
                    img = Image.fromarray(np.moveaxis(data, 0, -1), "RGBA")
                    d = os.path.join(TILE_ROOT, layer, str(z), str(x))
                    os.makedirs(d, exist_ok=True)
                    path = os.path.join(d, f"{y}.png")
                    if composite and os.path.exists(path):
                        old = Image.open(path).convert("RGBA")
                        old.paste(img, (0, 0), img)   # new content over old
                        img = old
                    img.save(path, optimize=False)
                    count += 1
            print(f"{layer} z{z} done ({count} tiles cumulative)", flush=True)
    print(layer, "COMPLETE:", count, "tiles", flush=True)
    return count

if __name__ == "__main__":
    for _layer in LAYERS:
        _src = os.path.join(DERIVED, f"{_layer}.tif")
        if not os.path.exists(_src):
            print("skip", _layer)
            continue
        tile_raster(_src, _layer, ZMIN, ZMAX, composite=COMPOSITE)
    print("ALL TILES DONE")
