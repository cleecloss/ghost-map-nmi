"""Compute archaeology visualizations from data/derived/dem_2m.tif in
memory-safe overlapping strips: multidirectional hillshade, Sky-View Factor,
Local Relief Model. Outputs 8-bit RGBA GeoTIFFs ready for tiling.
Run download_dem.py + the mosaic step first (dem_2m.tif must exist).
"""
import os
import numpy as np
import rasterio
from rasterio.windows import Window
from scipy.ndimage import uniform_filter

BASE = os.path.join(os.path.dirname(__file__), "..")
OUT_DIR = os.path.join(BASE, "data", "derived")
DEM = os.path.join(OUT_DIR, "dem_2m.tif")
RES = 2.0
STRIP = 1500      # rows per strip
PAD = 64          # overlap rows (covers SVF 20px + LRM 13px kernels)
F32 = np.float32

def hillshade_multi(z):
    gy, gx = np.gradient(z, F32(RES))
    slope = np.arctan(np.hypot(gx, gy), dtype=F32)
    aspect = np.arctan2(-gx, gy, dtype=F32)
    del gx, gy
    alt = F32(np.radians(45.0))
    hs = np.zeros_like(z)
    for az_deg in (225, 270, 315, 360):
        az = F32(np.radians(az_deg))
        h = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
        hs += np.clip(h, 0, 1, out=h)
    hs /= F32(4.0)
    return hs

def svf(z):
    n_dir, max_dist_m = 16, 40.0
    steps = np.unique(np.clip(np.round(
        np.geomspace(1, max_dist_m / RES, 8)).astype(int), 1, None))
    out = np.zeros_like(z)
    for i in range(n_dir):
        ang = 2 * np.pi * i / n_dir
        dy, dx = -np.cos(ang), np.sin(ang)
        max_tan = np.full_like(z, -np.inf)
        for s in steps:
            oy, ox = int(round(dy * s)), int(round(dx * s))
            shifted = np.zeros_like(z)
            sy = slice(max(0, -oy), z.shape[0] - max(0, oy))
            sx = slice(max(0, -ox), z.shape[1] - max(0, ox))
            ty = slice(max(0, oy), z.shape[0] - max(0, -oy))
            tx = slice(max(0, ox), z.shape[1] - max(0, -ox))
            shifted[ty, tx] = z[sy, sx]
            shifted -= z
            shifted /= F32(np.hypot(oy, ox) * RES)
            np.fmax(max_tan, shifted, out=max_tan)
        np.clip(max_tan, 0, None, out=max_tan)
        np.arctan(max_tan, out=max_tan)
        np.sin(max_tan, out=max_tan)
        out += F32(1.0) - max_tan
    out /= F32(n_dir)
    return out

def lrm(z):
    size = max(3, int(round(2 * 25.0 / RES)) | 1)  # 25 m radius
    return z - uniform_filter(z, size=size)

def gray_rgb(a, lo, hi):
    g = np.clip((a - lo) / (hi - lo), 0, 1)
    g = (g * 255).astype(np.uint8)
    return np.stack([g, g, g])

def diverging_rgb(a, span):
    t = np.clip(a / span, -1, 1)
    r = np.where(t > 0, 255, 255 * (1 + t * 0.75)).astype(np.uint8)
    g = (255 * (1 - np.abs(t) * 0.75)).astype(np.uint8)
    b = np.where(t < 0, 255, 255 * (1 - t * 0.75)).astype(np.uint8)
    return np.stack([r, g, b])

def main():
    src = rasterio.open(DEM)
    H, W = src.height, src.width
    prof = src.profile.copy()
    prof.update(count=4, dtype="uint8", nodata=None, compress="deflate",
                tiled=True, BIGTIFF="IF_SAFER")
    outs = {name: rasterio.open(os.path.join(OUT_DIR, f"{name}.tif"), "w", **prof)
            for name in ("hillshade", "lrm", "svf")}

    for row0 in range(0, H, STRIP):
        r_lo = max(0, row0 - PAD)
        r_hi = min(H, row0 + STRIP + PAD)
        z = src.read(1, window=Window(0, r_lo, W, r_hi - r_lo)).astype(F32)
        land = np.isfinite(z) & (z > -0.2)
        z = np.nan_to_num(z, nan=0.0)

        core = slice(row0 - r_lo, row0 - r_lo + min(STRIP, H - row0))
        win = Window(0, row0, W, min(STRIP, H - row0))
        alpha = np.where(land[core], 255, 0).astype(np.uint8)

        results = {
            "hillshade": gray_rgb(hillshade_multi(z)[core], 0.35, 1.0),
            "lrm": diverging_rgb(lrm(z)[core], 0.5),
            "svf": gray_rgb(svf(z)[core], 0.80, 1.0),
        }
        for name, rgb in results.items():
            for band in range(3):
                outs[name].write(rgb[band], band + 1, window=win)
            outs[name].write(alpha, 4, window=win)
        print(f"rows {row0}-{row0 + win.height} / {H} done", flush=True)

    for o in outs.values():
        o.close()
    src.close()
    print("DONE")

if __name__ == "__main__":
    main()
