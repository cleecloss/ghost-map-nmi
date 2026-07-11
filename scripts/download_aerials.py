"""Download 1943 UFDC aerial frames at full resolution (stitched 1024px IIIF
regions), georeference from the citation-API bbox, and mosaic into
data/derived/aerial1943.tif (RGBA, EPSG:4326) ready for tiling.
"""
import io, math, os, re, time
import numpy as np
import requests
from PIL import Image
import rasterio
from rasterio.transform import from_bounds
from rasterio.merge import merge

Image.MAX_IMAGE_PIXELS = None
BASE = os.path.join(os.path.dirname(__file__), "..")
RAW = os.path.join(BASE, "data", "aerials_1943")
OUT = os.path.join(BASE, "data", "derived")
os.makedirs(RAW, exist_ok=True)

ZOOM = "https://api.patron.uflib.ufl.edu/zoom"
RES_ROOT = "/home/anubis/resources"
SESSION = requests.Session()

# frame: (bibpath, vid, jp2 basename)
FRAMES = {
    "6C_102": ("UF/00/07/17/30", "00006", "12009_1943_6C_102"),  # Allenhurst S
    "6C_103": ("UF/00/07/17/30", "00006", "12009_1943_6C_103"),  # Allenhurst N
    "2C_47":  ("UF/00/07/17/89", "00002", "12127_1943_2C_47"),   # Shiloh S
    "2C_48":  ("UF/00/07/17/89", "00002", "12127_1943_2C_48"),   # Shiloh N
}
# bbox corners from citation API: NE NW SW SE -> (minlon, minlat, maxlon, maxlat)
BBOX = {
    "6C_102": (-80.7606842406581, 28.7048856702236, -80.7138, 28.746),
    "6C_103": (-80.7597517377843, 28.7215956702236, -80.71286, 28.76271),
    "2C_47":  (-80.8338511643722, 28.8314056702236, -80.78691, 28.87252),
    "2C_48":  (-80.8422271109069, 28.8445756702236, -80.79528, 28.88569),
}
def fetch_dzi(bibpath, vid, name):
    url = f"{ZOOM}?DeepZoom={RES_ROOT}/{bibpath}/{vid}/{name}.jp2.dzi"
    r = SESSION.get(url, timeout=60)
    r.raise_for_status()
    xml = r.text
    def attr(k):
        m = re.search(rf'{k}="(\d+)"', xml)
        return int(m.group(1)) if m else None
    return attr("Width"), attr("Height"), attr("TileSize") or 256, attr("Overlap") or 0

def fetch_dz_tile(bibpath, vid, name, level, col, row, tries=5):
    url = f"{ZOOM}?DeepZoom={RES_ROOT}/{bibpath}/{vid}/{name}.jp2_files/{level}/{col}_{row}.jpg"
    for a in range(tries):
        try:
            r = SESSION.get(url, timeout=60)
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content))
            img.load()  # forces full decode; raises on truncation
            return img
        except Exception:
            if a == tries - 1:
                raise
            time.sleep(1.5 * (a + 1))

def stitch(key):
    bibpath, vid, name = FRAMES[key]
    dest = os.path.join(RAW, f"{name}.png")
    if os.path.exists(dest):
        print(key, "already stitched", flush=True)
        return dest
    W, H, ts, ov = fetch_dzi(bibpath, vid, name)
    level = math.ceil(math.log2(max(W, H)))
    cols, rows = -(-W // ts), -(-H // ts)
    print(f"{key}: {W}x{H} ts={ts} ov={ov} level={level} -> {cols}x{rows} tiles", flush=True)
    canvas = Image.new("L", (W, H))
    for row in range(rows):
        for col in range(cols):
            img = fetch_dz_tile(bibpath, vid, name, level, col, row).convert("L")
            # DeepZoom tiles carry `ov` extra pixels on non-edge sides
            x0 = 0 if col == 0 else ov
            y0 = 0 if row == 0 else ov
            canvas.paste(img.crop((x0, y0, img.width, img.height)),
                         (col * ts, row * ts))
        print(f"  {key}: row {row + 1}/{rows}", flush=True)
    canvas.save(dest)
    print(key, "stitched ->", dest, flush=True)
    return dest

def georef(key, png_path):
    tif = os.path.join(RAW, f"{key}_geo.tif")
    # scans are north-up as archived (verified by edge cross-correlation
    # against modern imagery across all 8 dihedral orientations)
    img = Image.open(png_path)
    a = np.asarray(img, dtype=np.uint8)
    H, W = a.shape
    minlon, minlat, maxlon, maxlat = BBOX[key]
    transform = from_bounds(minlon, minlat, maxlon, maxlat, W, H)
    with rasterio.open(tif, "w", driver="GTiff", width=W, height=H, count=4,
                       dtype="uint8", crs="EPSG:4326", transform=transform,
                       compress="deflate", tiled=True, photometric="RGB") as dst:
        for b in (1, 2, 3):
            dst.write(a, b)
        dst.write(np.full_like(a, 255), 4)
    print(key, "georeferenced ->", tif, flush=True)
    return tif

def main():
    tifs = [georef(k, stitch(k)) for k in FRAMES]
    print("merging ...", flush=True)
    srcs = [rasterio.open(t) for t in tifs]
    # ~0.83 m native; merge at ~1e-5 deg (~1.1 m) to keep size sane
    arr, transform = merge(srcs, res=1e-5)
    prof = srcs[0].profile.copy()
    for s in srcs:
        s.close()
    # alpha: 0 where no frame contributed (merge fills 0)
    alpha = np.where(arr[3] > 0, 255, 0).astype(np.uint8)
    arr[3] = alpha
    prof.update(width=arr.shape[2], height=arr.shape[1], transform=transform,
                BIGTIFF="IF_SAFER")
    with rasterio.open(os.path.join(OUT, "aerial1943.tif"), "w", **prof) as dst:
        dst.write(arr)
    print("DONE: aerial1943.tif", arr.shape, flush=True)

if __name__ == "__main__":
    main()
