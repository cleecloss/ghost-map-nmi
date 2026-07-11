"""Auto-GCP refinement of the 1943 frames.

For each bbox-placed frame: warp to the EPSG:3857 z16 grid, find the global
NCC peak offset vs modern ESRI imagery (edge images), then patch-grid NCC for
local control points, fit an affine with iterative outlier rejection, and
rewrite the frame via GCP warp. Finally re-merge into aerial1943.tif (3857).
"""
import io, math, os
import numpy as np
import requests
from PIL import Image
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from rasterio.control import GroundControlPoint
from rasterio.warp import reproject, calculate_default_transform
from rasterio.transform import from_bounds, Affine
from rasterio.merge import merge
from scipy.signal import fftconvolve
from scipy.ndimage import sobel, gaussian_filter

Image.MAX_IMAGE_PIXELS = None
BASE = os.path.join(os.path.dirname(__file__), "..")
RAW = os.path.join(BASE, "data", "aerials_1943")
OUT = os.path.join(BASE, "data", "derived")
WEB = "EPSG:3857"
ORIGIN = 20037508.342789244
Z = 16
RES = 2 * ORIGIN / (2 ** Z) / 256          # meters/pixel of z16 tiles
FRAME_KEYS = ["6C_102", "6C_103", "2C_47", "2C_48"]

def edge(a):
    a = gaussian_filter(a.astype(np.float64), 1.5)
    g = np.hypot(sobel(a, 0), sobel(a, 1))
    g -= g.mean()
    s = g.std()
    return g / s if s else g

def esri_mosaic(x0, y0, x1, y1):
    m = Image.new("L", ((x1 - x0 + 1) * 256, (y1 - y0 + 1) * 256))
    for ty in range(y0, y1 + 1):
        for tx in range(x0, x1 + 1):
            url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{Z}/{ty}/{tx}"
            for a in range(3):
                try:
                    r = requests.get(url, timeout=30)
                    m.paste(Image.open(io.BytesIO(r.content)).convert("L"),
                            ((tx - x0) * 256, (ty - y0) * 256))
                    break
                except Exception:
                    if a == 2: raise
    return np.asarray(m, dtype=np.float64)

def ncc_peak(ref_e, img_e, max_shift):
    c = fftconvolve(ref_e, img_e[::-1, ::-1], mode="same") / img_e.size
    my, mx = c.shape[0] // 2, c.shape[1] // 2
    win = c[my - max_shift:my + max_shift + 1, mx - max_shift:mx + max_shift + 1]
    iy, ix = np.unravel_index(np.argmax(win), win.shape)
    return win[iy, ix], iy - max_shift, ix - max_shift   # score, dy, dx

def refine_frame(key):
    src = rasterio.open(os.path.join(RAW, f"{key}_geo.tif"))
    with WarpedVRT(src, crs=WEB, resampling=Resampling.bilinear) as vrt:
        b = vrt.bounds
        tx0 = int((b.left + ORIGIN) / (RES * 256)); tx1 = int((b.right + ORIGIN) / (RES * 256))
        ty0 = int((ORIGIN - b.top) / (RES * 256)); ty1 = int((ORIGIN - b.bottom) / (RES * 256))
        ref = esri_mosaic(tx0, ty0, tx1, ty1)
        H, W = ref.shape
        ref_left = tx0 * RES * 256 - ORIGIN
        ref_top = ORIGIN - ty0 * RES * 256
        grid_tr = from_bounds(ref_left, ref_top - H * RES, ref_left + W * RES, ref_top, W, H)
        img = np.zeros((H, W), dtype=np.float64)
        alpha = np.zeros((H, W), dtype=np.uint8)
        reproject(rasterio.band(vrt, 1), img, dst_transform=grid_tr, dst_crs=WEB,
                  resampling=Resampling.bilinear)
        reproject(rasterio.band(vrt, 4), alpha, dst_transform=grid_tr, dst_crs=WEB,
                  resampling=Resampling.nearest)
    ref_e, img_e = edge(ref), edge(np.where(alpha > 0, img, 0))
    ref_e[alpha == 0] = 0   # only compare where the frame has content

    gs, gdy, gdx = ncc_peak(ref_e, img_e, max_shift=120)
    print(f"{key}: global shift dx={gdx*RES:+.0f}m dy={gdy*RES:+.0f}m (score {gs:.3f})", flush=True)

    P, STRIDE, LOC = 384, 256, 28   # patch px, stride px, local search px
    pairs = []
    for py in range(0, H - P, STRIDE):
        for px in range(0, W - P, STRIDE):
            ie = img_e[py:py + P, px:px + P]
            if (alpha[py:py + P, px:px + P] > 0).mean() < 0.9 or ie.std() < 0.5:
                continue
            ry0, rx0 = py + gdy, px + gdx
            if ry0 < 0 or rx0 < 0 or ry0 + P > H or rx0 + P > W:
                continue
            re_ = ref_e[ry0:ry0 + P, rx0:rx0 + P]
            s, dy, dx = ncc_peak(re_, ie, max_shift=LOC)
            if s < 0.08 or abs(dy) == LOC or abs(dx) == LOC:
                continue
            cx, cy = px + P / 2, py + P / 2
            pairs.append((cx, cy, cx + gdx + dx, cy + gdy + dy, s))
    print(f"{key}: {len(pairs)} candidate patches", flush=True)

    # affine fit src(px)->dst(px) with iterative 2-sigma rejection
    use = list(pairs)
    A_fit = None
    for _ in range(5):
        if len(use) < 4:
            break
        S = np.array([[p[0], p[1], 1] for p in use])
        DX = np.array([p[2] for p in use]); DY = np.array([p[3] for p in use])
        cx_, *_ = np.linalg.lstsq(S, DX, rcond=None)
        cy_, *_ = np.linalg.lstsq(S, DY, rcond=None)
        rx = S @ cx_ - DX; ry = S @ cy_ - DY
        r = np.hypot(rx, ry)
        keep = r < max(2.0, 2.0 * r.std() + r.mean())
        A_fit = (cx_, cy_, float(np.hypot(rx, ry).mean()))
        if keep.all():
            break
        use = [p for p, k in zip(use, keep) if k]

    if A_fit and len(use) >= 4:
        cx_, cy_, resid = A_fit
        print(f"{key}: affine from {len(use)} GCPs, mean residual {resid*RES:.1f} m", flush=True)
        def dst_px(x, y): return (cx_[0]*x + cx_[1]*y + cx_[2], cy_[0]*x + cy_[1]*y + cy_[2])
    else:
        print(f"{key}: falling back to global shift only", flush=True)
        def dst_px(x, y): return (x + gdx, y + gdy)

    # corrected source->world mapping: fit affine through 5 anchor points
    sh, sw = src.height, src.width
    spts, wpts = [], []
    for fx, fy in [(0, 0), (sw, 0), (sw, sh), (0, sh), (sw/2, sh/2)]:
        wx, wy = src.transform * (fx, fy)                       # 4326 lonlat
        gx = (wx * math.pi / 180 * 6378137 - ref_left) / RES     # to grid px
        gy = (ref_top - 6378137 * math.log(math.tan(math.pi/4 + wy*math.pi/360))) / RES
        nx, ny = dst_px(gx, gy)
        spts.append((fx, fy))
        wpts.append((ref_left + nx * RES, ref_top - ny * RES))
    S = np.array([[x, y, 1] for x, y in spts])
    ax, *_ = np.linalg.lstsq(S, np.array([w[0] for w in wpts]), rcond=None)
    ay, *_ = np.linalg.lstsq(S, np.array([w[1] for w in wpts]), rcond=None)
    M = Affine(ax[0], ax[1], ax[2], ay[0], ay[1], ay[2])

    xs = [w[0] for w in wpts[:4]]; ys = [w[1] for w in wpts[:4]]
    dw, dh = int(math.ceil(max(xs) - min(xs))), int(math.ceil(max(ys) - min(ys)))
    dst_tr = Affine(1.0, 0, min(xs), 0, -1.0, max(ys))
    prof = src.profile.copy()
    prof.update(crs=WEB, transform=dst_tr, width=dw, height=dh, BIGTIFF="IF_SAFER")
    out_path = os.path.join(RAW, f"{key}_gcp.tif")
    with rasterio.open(out_path, "w", **prof) as dst:
        for band in range(1, 5):
            arr = np.zeros((dh, dw), dtype=np.uint8)
            reproject(rasterio.band(src, band), arr, src_transform=M, src_crs=WEB,
                      dst_transform=dst_tr, dst_crs=WEB,
                      resampling=Resampling.bilinear if band < 4 else Resampling.nearest)
            dst.write(arr, band)
    src.close()
    print(f"{key}: wrote {out_path}", flush=True)
    return out_path

def main():
    tifs = [refine_frame(k) for k in FRAME_KEYS]
    print("merging ...", flush=True)
    srcs = [rasterio.open(t) for t in tifs]
    arr, tr = merge(srcs, res=1.0)
    prof = srcs[0].profile.copy()
    for s in srcs: s.close()
    arr[3] = np.where(arr[3] > 0, 255, 0).astype(np.uint8)
    prof.update(width=arr.shape[2], height=arr.shape[1], transform=tr)
    with rasterio.open(os.path.join(OUT, "aerial1943.tif"), "w", **prof) as dst:
        dst.write(arr)
    print("DONE", arr.shape, flush=True)

if __name__ == "__main__":
    main()
