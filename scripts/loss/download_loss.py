"""
Annual loss rasters from Earth Engine, downloaded directly in tiles (no Drive, no Cloud Storage).
One uint16 band per year on the native MapBiomas grid: code = to_class * 100 + sec_age,
0 = no loss, sec_age 0 = primary (secondary is always >= 2). Decode: code // 100, code % 100.
Pixels outside the study area are set to 0.

Out: data.nosync/processed/loss/loss_<year>.tif (COG). Tiles are cached while a year runs, so an
interrupted run resumes; they are deleted once the year is written. Each year's cost (EECU-s, summed
from the Earth Engine profile of every tile fetched in that run) is appended to download_log.csv.

Usage: python scripts/loss/download_loss.py [year ...] [--workers N]
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
import pandas as pd
import rasterio
from dotenv import load_dotenv

from piedemonte_forest import loss_rule as lr
from piedemonte_forest.gee_tiles import Grid

OUT = Path("data.nosync/processed/loss")
LOG = OUT / "download_log.csv"
TILE = 4096  # px; uint16 -> 33.5 MB, under the 48 MB request limit

args = sys.argv[1:]
workers = int(args[args.index("--workers") + 1]) if "--workers" in args else 8
years = [int(a) for a in args if a.isdigit() and len(a) == 4] or list(range(lr.FIRST_YEAR, lr.LAST_YEAR + 1))

load_dotenv(".env")
ee.Initialize(project=os.environ["EE_PROJECT"])

crs = ee.Image(lr.ASSET).projection().getInfo()["crs"]
aoi = gpd.read_parquet("data.nosync/processed/study_area.parquet").to_crs(crs).union_all()
grid = Grid(lr.ASSET, aoi, TILE)
inside = grid.inside()
print(f"grid {grid.width} x {grid.height} px, {len(grid.tiles)} tiles, {workers} workers")


def packed(year):
    loss = lr.loss(year)
    sec_age = lr.forest_type(year).select("sec_age").unmask(0)
    return lr.lulc(year).multiply(100).add(sec_age).updateMask(loss.selfMask()).unmask(0).toUint16()


for year in years:
    out = OUT / f"loss_{year}.tif"
    if out.exists():
        print(f"{year}: exists, skipped")
        continue
    tmp = OUT / f"tiles_{year}"
    tmp.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    img = packed(year)
    with ThreadPoolExecutor(workers) as pool:
        jobs = [pool.submit(grid.fetch, img, r, c, tmp / f"{r}_{c}.tif") for r, c in grid.tiles]
        eecu = sum(j.result() for j in jobs)
    code = grid.mosaic(tmp, "uint16", 0)
    code[~inside] = 0
    profile = dict(driver="COG", width=grid.width, height=grid.height, count=1, dtype="uint16", nodata=None,
                   crs=grid.crs, transform=grid.transform, compress="DEFLATE", predictor=2)
    with rasterio.open(out, "w", **profile) as dst:
        dst.write(code, 1)
    shutil.rmtree(tmp)
    row = dict(year=year, run=date.today(), loss_px=int((code > 0).sum()), mb=round(out.stat().st_size / 1e6, 1),
               seconds=round(time.time() - t0), eecu_s=round(eecu))
    pd.DataFrame([row]).to_csv(LOG, mode="a", header=not LOG.exists(), index=False)
    print(f"{year}: {row['loss_px']:,} loss px, {row['mb']} MB, {row['seconds']} s, {row['eecu_s']:,} EECU-s")
