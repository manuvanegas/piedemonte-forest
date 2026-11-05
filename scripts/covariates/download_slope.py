"""
Slope from SRTM (USGS/SRTMGL1_003, 1 arc-second, 2000), computed in Earth Engine on the native
MapBiomas grid and downloaded directly in tiles. The DEM is resampled bilinearly to that grid, then
ee.Terrain.slope gives degrees. Stored as uint16 tenths of a degree; NODATA outside the study area.

Out: data.nosync/processed/slope/slope.tif (COG). Tiles are cached while it runs, so an interrupted
run resumes; they are deleted once the file is written. Cost (EECU-s) goes to download_log.csv.
--tiles N fetches only the first N tiles and stops (cost test).

Usage: python scripts/covariates/download_slope.py [--tiles N] [--workers N]
"""
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import ee
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from dotenv import load_dotenv

from piedemonte_forest import loss_rule as lr
from piedemonte_forest.gee_tiles import Grid

OUT = Path("data.nosync/processed/slope/slope.tif")
LOG = OUT.parent / "download_log.csv"
TMP = OUT.parent / "tiles"
DEM = "USGS/SRTMGL1_003"
TILE = 4096  # px; uint16 -> 33.5 MB, under the 48 MB request limit
NODATA = 65535

args = sys.argv[1:]
workers = int(args[args.index("--workers") + 1]) if "--workers" in args else 8
limit = int(args[args.index("--tiles") + 1]) if "--tiles" in args else None

if OUT.exists():
    sys.exit(f"{OUT} exists, skipped")

load_dotenv(".env")
ee.Initialize(project=os.environ["EE_PROJECT"])
crs = ee.Image(lr.ASSET).projection().getInfo()["crs"]
aoi = gpd.read_parquet("data.nosync/processed/study_area.parquet").to_crs(crs).union_all()
grid = Grid(lr.ASSET, aoi, TILE)
tiles = grid.tiles[:limit]
print(f"grid {grid.width} x {grid.height} px, {len(tiles)} of {len(grid.tiles)} tiles, {workers} workers")

slope = ee.Terrain.slope(ee.Image(DEM).resample("bilinear"))
img = slope.multiply(10).round().toUint16()

TMP.mkdir(parents=True, exist_ok=True)
t0 = time.time()
with ThreadPoolExecutor(workers) as pool:
    jobs = [pool.submit(grid.fetch, img, r, c, TMP / f"{r}_{c}.tif") for r, c in tiles]
    eecu = sum(j.result() for j in jobs)
print(f"{len(tiles)} tiles, {time.time() - t0:.0f} s, {eecu:,.0f} EECU-s")
if limit is not None:
    sys.exit()

a = grid.mosaic(TMP, "uint16", NODATA)
a[~grid.inside()] = NODATA
profile = dict(driver="COG", width=grid.width, height=grid.height, count=1, dtype="uint16", nodata=NODATA,
               crs=grid.crs, transform=grid.transform, compress="DEFLATE", predictor=2)
with rasterio.open(OUT, "w", **profile) as dst:
    dst.write(a, 1)
shutil.rmtree(TMP)
v = a[a != NODATA] / 10
row = dict(run=date.today(), mb=round(OUT.stat().st_size / 1e6, 1), seconds=round(time.time() - t0),
           eecu_s=round(eecu), median_deg=float(np.median(v)), max_deg=float(v.max()))
pd.DataFrame([row]).to_csv(LOG, mode="a", header=not LOG.exists(), index=False)
print(row)
