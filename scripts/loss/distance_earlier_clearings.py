"""
Distance from each loss patch to the nearest patch cleared in the three years before it (t-3 to t-1,
D14). Patches from 2005-2007 count as earlier clearings only (table lookback_patches).

Needs PostGIS loaded by load_patches.py (all years) and load_patches.py --lookback.
Out: data.nosync/processed/covariates/earlier_clearings.parquet

Usage: python scripts/loss/distance_earlier_clearings.py
"""
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

import db
import loss_rule as lr
from patch_distances import nearest_earlier_sql

OUT = Path("data.nosync/processed/covariates/earlier_clearings.parquet")
WINDOW = 3  # years (D14)

engine = db.engine()

t0 = time.time()
parts = []
with engine.connect() as con:
    have = {r[0] for r in con.execute(text("SELECT DISTINCT loss_year FROM lookback_patches"))}
    missing = set(range(lr.FIRST_YEAR - WINDOW, lr.FIRST_YEAR)) - have
    assert not missing, f"lookback_patches lacks {sorted(missing)}: run load_patches.py --lookback"
    for year in range(lr.FIRST_YEAR, lr.LAST_YEAR + 1):
        t1 = time.time()
        parts.append(pd.read_sql(text(nearest_earlier_sql(year, WINDOW)), con))
        print(f"{year}: {len(parts[-1]):,} patches, {time.time() - t1:.0f} s", flush=True)
    n_patches = con.execute(text("SELECT count(*) FROM patches")).scalar()
d = pd.concat(parts, ignore_index=True)
assert len(d) == n_patches, f"{len(d):,} rows for {n_patches:,} patches"
assert not d.duplicated(["loss_year", "patch_id"]).any()
assert d.dist_m.notna().all()

d = d.rename(columns={"dist_m": "earlier_dist_m"})
OUT.parent.mkdir(parents=True, exist_ok=True)
d.sort_values(["loss_year", "patch_id"]).to_parquet(OUT, index=False)
print(f"{len(d):,} patches, {time.time() - t0:.0f} s; median distance {d.earlier_dist_m.median():,.0f} m, "
      f"{(d.earlier_dist_m == 0).mean():.0%} touching an earlier patch")
