"""
Load loss patches with n_px >= 2 (D13) into PostGIS (EPSG:9377; to_postgis adds the GiST index).
Rows of the given years are replaced, so a rerun doesn't duplicate them.

In:  data.nosync/processed/loss_patches/patches_<year>.parquet
Out: table patches

Usage: python scripts/loss/load_patches.py [year ...]   (no years = all)
"""
import sys
import time

import geopandas as gpd
from sqlalchemy import text

import db
import loss_rule as lr

MIN_PX = 2

engine = db.engine()
years = [int(a) for a in sys.argv[1:] if a.isdigit()] or list(range(lr.FIRST_YEAR, lr.LAST_YEAR + 1))

with engine.begin() as con:
    if con.execute(text("SELECT to_regclass('patches') IS NOT NULL")).scalar():
        con.execute(text("DELETE FROM patches WHERE loss_year = ANY(:y)"), {"y": years})

for year in years:
    t0 = time.time()
    g = gpd.read_parquet(f"data.nosync/processed/loss_patches/patches_{year}.parquet")
    g = g[g.n_px >= MIN_PX]
    g.to_postgis("patches", engine, if_exists="append", index=False, chunksize=50_000)
    print(f"{year}: {len(g):,} patches loaded, {time.time() - t0:.0f} s")

with engine.begin() as con:
    con.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS patches_key ON patches (loss_year, patch_id)"))
    con.execute(text("ANALYZE patches"))
