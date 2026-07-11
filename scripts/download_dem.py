"""Download USGS 3DEP 1m DEM tiles for the Shiloh-Allenhurst corridor."""
import os, requests

TILES = {
    # tile_id: (url, note)
    "x51y318": ("https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/FL_Peninsular_FDEM_2018_D19_DRRA/TIFF/USGS_1M_17_x51y318_FL_Peninsular_FDEM_2018_D19_DRRA.tif", "SW - lagoon west of Haulover"),
    "x52y318": ("https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/FL_Peninsular_FDEM_2018_D19_DRRA/TIFF/USGS_1M_17_x52y318_FL_Peninsular_FDEM_2018_D19_DRRA.tif", "Allenhurst / Haulover Canal"),
    "x51y319": ("https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/FL_Peninsular_FDEM_2018_D19_DRRA/TIFF/USGS_1M_17_x51y319_FL_Peninsular_FDEM_2018_D19_DRRA.tif", "Shiloh / west corridor"),
    "x52y319": ("https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/FL_Peninsular_FDEM_2018_D19_DRRA/TIFF/USGS_1M_17_x52y319_FL_Peninsular_FDEM_2018_D19_DRRA.tif", "Wilson / east corridor"),
    "x51y320": ("https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/FL_Upper_Saint_Johns_2017/TIFF/USGS_one_meter_x51y320_FL_Upper_Saint_Johns_2017.tif", "N tip west (Volusia line)"),
    "x52y320": ("https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/FL_Peninsular_2018_D18/TIFF/USGS_1M_17_x52y320_FL_Peninsular_2018_D18.tif", "N tip east"),
}

out_dir = os.path.join(os.path.dirname(__file__), "..", "data", "dem")
os.makedirs(out_dir, exist_ok=True)

for tid, (url, note) in TILES.items():
    dest = os.path.join(out_dir, f"{tid}.tif")
    if os.path.exists(dest) and os.path.getsize(dest) > 1e6:
        print(f"{tid}: already present, skipping")
        continue
    print(f"{tid}: downloading ({note}) ...", flush=True)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest + ".part", "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    os.replace(dest + ".part", dest)
    print(f"{tid}: done, {os.path.getsize(dest)/1e6:.1f} MB", flush=True)

print("ALL DOWNLOADS COMPLETE")
