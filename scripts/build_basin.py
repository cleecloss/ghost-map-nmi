"""Stream-build a 2m DEM canvas for the whole northern lagoon basin
(all Brevard + S Volusia). Downloads each USGS 1m cell, warps it into the
canvas, deletes the raw file. Resumable (data/basin_done.json).
Disk-friendly: never holds more than one raw cell (~400 MB) at a time.
"""
import json, os, tempfile
import numpy as np
import requests
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from rasterio.transform import from_origin, rowcol
from rasterio.windows import Window

BASE = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(BASE, "data")
CANVAS = os.path.join(DATA, "basin_dem_2m.tif")
DONE = os.path.join(DATA, "basin_done.json")
CELLS = os.path.join(DATA, "basin_cells.json")
BBOX = "-81.05,27.80,-80.45,29.05"
CRS = "EPSG:26917"
RES = 2.0
# canvas grid: easting 495000-555000, northing 3075000-3214000
LEFT, TOP, W, H = 495000.0, 3214000.0, 30000, 69500

def get_cells():
    if os.path.exists(CELLS):
        return json.load(open(CELLS))
    items, start = [], 0
    while True:
        r = requests.get("https://tnmaccess.nationalmap.gov/api/v1/products", params={
            "datasets": "Digital Elevation Model (DEM) 1 meter", "bbox": BBOX,
            "max": 100, "offset": start, "outputFormat": "JSON"}, timeout=90).json()
        items += r.get("items", [])
        if len(items) >= r.get("total", 0) or not r.get("items"):
            break
        start += 100
    best = {}
    for it in items:
        parts = it["title"].split()
        cell = parts[3] if "x" in parts[3] else parts[4]
        proj = it["downloadURL"].split("/Projects/")[1].split("/")[0]
        pref = 0 if "FDEM_2018" in proj else (1 if "2018" in proj else 2)
        if cell not in best or pref < best[cell][0]:
            best[cell] = (pref, it["downloadURL"])
    cells = {c: u for c, (p, u) in sorted(best.items())}
    json.dump(cells, open(CELLS, "w"), indent=1)
    return cells

def ensure_canvas():
    if os.path.exists(CANVAS):
        return
    profile = dict(driver="GTiff", width=W, height=H, count=1, dtype="float32",
                   crs=CRS, transform=from_origin(LEFT, TOP, RES, RES),
                   nodata=np.nan, tiled=True, blockxsize=512, blockysize=512,
                   compress="deflate", BIGTIFF="YES", SPARSE_OK=True)
    with rasterio.open(CANVAS, "w", **profile):
        pass
    print("canvas created", flush=True)

def main():
    cells = get_cells()
    done = set(json.load(open(DONE))) if os.path.exists(DONE) else set()
    ensure_canvas()
    todo = [c for c in cells if c not in done]
    print(f"{len(todo)} cells to ingest ({len(done)} already done)", flush=True)
    dst = rasterio.open(CANVAS, "r+")
    for i, cell in enumerate(todo):
        url = cells[cell]
        tmp = os.path.join(tempfile.gettempdir(), f"cell_{cell}.tif")
        try:
            for attempt in range(10):   # storm-tolerant: waits up to ~3 min between tries
                try:
                    with requests.get(url, stream=True, timeout=120) as r:
                        r.raise_for_status()
                        with open(tmp, "wb") as f:
                            for chunk in r.iter_content(1 << 20):
                                f.write(chunk)
                    break
                except (requests.exceptions.RequestException, OSError):
                    if attempt == 9:
                        raise
                    import time
                    time.sleep(min(180, 10 * 2 ** attempt))
                    print(f"  retry {attempt + 1} for {cell}", flush=True)
            with rasterio.open(tmp) as src, WarpedVRT(
                    src, crs=CRS, resampling=Resampling.average,
                    transform=from_origin(LEFT, TOP, RES, RES),
                    width=W, height=H) as vrt:
                # window of this cell inside the canvas grid
                sb = src.bounds
                (r0, c0) = rowcol(vrt.transform, sb.left, sb.top)
                (r1, c1) = rowcol(vrt.transform, sb.right, sb.bottom)
                r0, c0 = max(0, r0 - 2), max(0, c0 - 2)
                r1, c1 = min(H, r1 + 2), min(W, c1 + 2)
                if r1 <= r0 or c1 <= c0:
                    raise ValueError("cell outside canvas")
                win = Window(c0, r0, c1 - c0, r1 - r0)
                a = vrt.read(1, window=win)
                have = dst.read(1, window=win)
                # nodata like -999999 is finite — must be excluded explicitly
                put = np.isfinite(a) & (a > -9998)
                have[put] = a[put]
                dst.write(have, 1, window=win)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        done.add(cell)
        json.dump(sorted(done), open(DONE, "w"))
        print(f"[{len(done)}/{len(cells)}] {cell} ingested", flush=True)
    dst.close()
    print("CANVAS COMPLETE", flush=True)

if __name__ == "__main__":
    main()
