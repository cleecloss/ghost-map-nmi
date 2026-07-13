"""Repair the basin canvas: convert poisoned nodata (-999999 and kin) to NaN,
then heal thin nodata stripes (cell-boundary overwrite artifacts) by
normalized-convolution fill — only where local valid support is high, so
broad water/void areas stay NaN and no terrain is fabricated.
"""
import numpy as np
import rasterio
from rasterio.windows import Window
from scipy.ndimage import uniform_filter

CANVAS = r"C:\Users\clecl\Experiments\New idea\ghost-map-nmi\data\basin_dem_2m.tif"
STRIP = 2000
PAD = 8            # fill kernel support
KERNEL = 7
SUPPORT = 0.6      # min fraction of valid neighbors to allow filling

src = rasterio.open(CANVAS, "r+")
H, W = src.height, src.width
poisoned_total = healed_total = 0
for row0 in range(0, H, STRIP):
    rows = min(STRIP, H - row0)
    a_lo, a_hi = max(0, row0 - PAD), min(H, row0 + rows + PAD)
    z = src.read(1, window=Window(0, a_lo, W, a_hi - a_lo))
    bad = np.isfinite(z) & (z < -9998)
    poisoned_total += int(bad.sum())
    z[bad] = np.nan
    valid = np.isfinite(z)
    if valid.any():
        zf = np.where(valid, z, 0.0).astype(np.float32)
        num = uniform_filter(zf, size=KERNEL)
        den = uniform_filter(valid.astype(np.float32), size=KERNEL)
        with np.errstate(invalid="ignore"):
            fill = num / den
        heal = (~valid) & (den >= SUPPORT)
        z[heal] = fill[heal]
        healed_total += int(heal[row0 - a_lo:row0 - a_lo + rows].sum())
    core = slice(row0 - a_lo, row0 - a_lo + rows)
    src.write(z[core], 1, window=Window(0, row0, W, rows))
    if (row0 // STRIP) % 5 == 0:
        print(f"rows {row0 + rows}/{H} (poisoned so far {poisoned_total}, healed {healed_total})", flush=True)
src.close()
print(f"REPAIR COMPLETE: poisoned {poisoned_total} px -> NaN, healed {healed_total} px", flush=True)
