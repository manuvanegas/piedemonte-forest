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
import io
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
from rasterio.features import geometry_mask
from rasterio.transform import Affine
from shapely.geometry import box

import loss_rule as lr

OUT = Path("data.nosync/processed/loss")
LOG = OUT / "download_log.csv"
TILE = 4096  # px; uint16 -> 33.5 MB, under the 48 MB request limit
RETRIES = 3

args = sys.argv[1:]
workers = int(args[args.index("--workers") + 1]) if "--workers" in args else 8
years = [int(a) for a in args if a.isdigit() and len(a) == 4] or list(range(lr.FIRST_YEAR, lr.LAST_YEAR + 1))

load_dotenv(".env")
ee.Initialize(project=os.environ["EE_PROJECT"])

# native grid, snapped around the study area
proj = ee.Image(lr.ASSET).projection().getInfo()
native = Affine(*proj["transform"])
aoi = gpd.read_parquet("data.nosync/processed/study_area.parquet").to_crs(proj["crs"]).union_all()
c0, r0 = map(int, np.floor(~native * (aoi.bounds[0], aoi.bounds[3])))
c1, r1 = map(int, np.ceil(~native * (aoi.bounds[2], aoi.bounds[1])))
transform = native * Affine.translation(c0, r0)
width, height = c1 - c0, r1 - r0
tiles = [(r, c) for r in range(0, height, TILE) for c in range(0, width, TILE)
         if box(*rasterio.windows.bounds(((r, min(r + TILE, height)), (c, min(c + TILE, width))),
                                         transform)).intersects(aoi)]
inside = ~geometry_mask([aoi], (height, width), transform)
print(f"grid {width} x {height} px, {len(tiles)} tiles, {workers} workers")


def packed(year):
    loss = lr.loss(year)
    sec_age = lr.forest_type(year).select("sec_age").unmask(0)
    return lr.lulc(year).multiply(100).add(sec_age).updateMask(loss.selfMask()).unmask(0).toUint16()


def eecu_s(profile):
    rows = [line.split() for line in profile.splitlines()[1:]]
    return sum(float(r[0]) for r in rows if r and r[0] != "-")


def fetch(img, r, c, path):
    """Download one tile; returns its cost in EECU-s (0 if cached)."""
    if path.exists():
        return 0.0
    t = transform * Affine.translation(c, r)
    grid = {"dimensions": {"width": min(TILE, width - c), "height": min(TILE, height - r)},
            "affineTransform": {"scaleX": t.a, "shearX": t.b, "translateX": t.c,
                                "shearY": t.d, "scaleY": t.e, "translateY": t.f},
            "crsCode": proj["crs"]}
    for attempt in range(RETRIES):
        try:
            buf = io.StringIO()
            with ee.profilePrinting(destination=buf):
                data = ee.data.computePixels({"expression": img, "fileFormat": "GEO_TIFF", "grid": grid})
            path.with_suffix(".part").write_bytes(data)
            path.with_suffix(".part").rename(path)
            return eecu_s(buf.getvalue())
        except Exception as e:
            if attempt == RETRIES - 1:
                raise
            print(f"  tile {r},{c}: {e}; retrying")
            time.sleep(10 * (attempt + 1))


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
        jobs = [pool.submit(fetch, img, r, c, tmp / f"{r}_{c}.tif") for r, c in tiles]
        eecu = sum(j.result() for j in jobs)
    code = np.zeros((height, width), np.uint16)
    for r, c in tiles:
        with rasterio.open(tmp / f"{r}_{c}.tif") as src:
            a = src.read(1)
        code[r:r + a.shape[0], c:c + a.shape[1]] = a
    code[~inside] = 0
    profile = dict(driver="COG", width=width, height=height, count=1, dtype="uint16", nodata=None,
                   crs=proj["crs"], transform=transform, compress="DEFLATE", predictor=2)
    with rasterio.open(out, "w", **profile) as dst:
        dst.write(code, 1)
    shutil.rmtree(tmp)
    row = dict(year=year, run=date.today(), loss_px=int((code > 0).sum()), mb=round(out.stat().st_size / 1e6, 1),
               seconds=round(time.time() - t0), eecu_s=round(eecu))
    pd.DataFrame([row]).to_csv(LOG, mode="a", header=not LOG.exists(), index=False)
    print(f"{year}: {row['loss_px']:,} loss px, {row['mb']} MB, {row['seconds']} s, {row['eecu_s']:,} EECU-s")
