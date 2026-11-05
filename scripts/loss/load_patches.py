"""
Load loss patches with n_px >= 2 (D13) into PostGIS (EPSG:9377; to_postgis adds the GiST index).
Rows of the given years are replaced, so a rerun doesn't duplicate them.
--lookback loads 2005-2007 into lookback_patches instead: targets for distance to earlier clearing only
(D14), kept apart so no other covariate is computed for them.

In:  data.nosync/processed/loss_patches/patches_<year>.parquet
Out: table patches, or lookback_patches

Usage: python scripts/loss/load_patches.py [year ...]   (no years = all)
       python scripts/loss/load_patches.py --lookback [year ...]
"""
import sys
import time

import geopandas as gpd
from sqlalchemy import text

from piedemonte_forest import db
from piedemonte_forest import loss_rule as lr

MIN_PX = 2

engine = db.engine()
lookback = "--lookback" in sys.argv
table = "lookback_patches" if lookback else "patches"
first, last = (lr.HISTORY_FIRST, lr.FIRST_YEAR - 1) if lookback else (lr.FIRST_YEAR, lr.LAST_YEAR)
years = [int(a) for a in sys.argv[1:] if a.isdigit()] or list(range(first, last + 1))

with engine.begin() as con:
    if con.execute(text(f"SELECT to_regclass('{table}') IS NOT NULL")).scalar():
        con.execute(text(f"DELETE FROM {table} WHERE loss_year = ANY(:y)"), {"y": years})

for year in years:
    t0 = time.time()
    g = gpd.read_parquet(f"data.nosync/processed/loss_patches/patches_{year}.parquet")
    g = g[g.n_px >= MIN_PX]
    if lookback:  # targets only: attributes not needed (a patch can lack a municipio, giving a NaN treated)
        g = g[["loss_year", "patch_id", "n_px", "geometry"]]
    g.to_postgis(table, engine, if_exists="append", index=False, chunksize=50_000)
    print(f"{year}: {len(g):,} patches loaded, {time.time() - t0:.0f} s")

with engine.begin() as con:
    con.execute(text(f"CREATE UNIQUE INDEX IF NOT EXISTS {table}_key ON {table} (loss_year, patch_id)"))
    # lets the planner skip a table with no rows in a year window (UNION ALL in nearest_earlier_sql)
    con.execute(text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_years"))
    con.execute(text(f"ALTER TABLE {table} ADD CONSTRAINT {table}_years CHECK (loss_year BETWEEN {first} AND {last})"))
    con.execute(text(f"ANALYZE {table}"))
