"""
Load protected areas (RUNAP, whole country, so a patch's nearest area can lie outside the study
area) and loss patches with n_px >= 2 (D13) into PostGIS, both in EPSG:9377 (to_postgis adds the GiST index).

In:  data.nosync/raw/runap/runap_latest.zip, data.nosync/processed/loss_patches/patches_<year>.parquet
Out: tables runap, patches (rows of the given years are replaced)

Usage: python scripts/loss/load_db.py [year ...]
"""
import os
import sys
import time

import geopandas as gpd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

import loss_rule as lr

CRS = 9377
MIN_PX = 2

load_dotenv(".env")
# SQLAlchemy 2.1 defaults to psycopg 3; the env has psycopg2
engine = create_engine(os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+psycopg2://", 1))
years = [int(a) for a in sys.argv[1:] if a.isdigit()] or list(range(lr.FIRST_YEAR, lr.LAST_YEAR + 1))

r = gpd.read_file("zip://data.nosync/raw/runap/runap_latest.zip!runap.shp")
r = r[["ap_id", "ap_nombre", "ap_categor", "fecha_insc", "geometry"]].to_crs(CRS)
r.to_postgis("runap", engine, if_exists="replace", index=False)
with engine.begin() as con:
    n_invalid = con.execute(text("SELECT count(*) FROM runap WHERE NOT ST_IsValid(geometry)")).scalar()
print(f"runap: {len(r):,} areas, {n_invalid} invalid geometries")

with engine.begin() as con:
    exists = con.execute(text("SELECT to_regclass('patches') IS NOT NULL")).scalar()
    if exists:
        con.execute(text("DELETE FROM patches WHERE loss_year = ANY(:y)"), {"y": years})

for year in years:
    t0 = time.time()
    g = gpd.read_parquet(f"data.nosync/processed/loss_patches/patches_{year}.parquet")
    g = g[g.n_px >= MIN_PX]
    g.to_postgis("patches", engine, if_exists="append", index=False, chunksize=50_000)
    print(f"{year}: {len(g):,} patches loaded, {time.time() - t0:.0f} s")

with engine.begin() as con:
    con.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS patches_key ON patches (loss_year, patch_id)"))
    con.execute(text("ANALYZE runap; ANALYZE patches"))
