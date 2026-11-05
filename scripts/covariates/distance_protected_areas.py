"""
Distance from each loss patch to the nearest protected area (RUNAP, current boundaries, A6), queried
against runap_sub (A7). A patch overlapping or touching an area gets distance 0 and in_pa = True.

Needs PostGIS loaded by load_patches.py (all years) and load_targets.py --runap.
Out: data.nosync/processed/covariates/protected_areas.parquet

Usage: python scripts/covariates/distance_protected_areas.py
"""
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from piedemonte_forest import db
from piedemonte_forest.patch_distances import TARGET_BUFFER, nearest_sql

OUT = Path("data.nosync/processed/covariates/protected_areas.parquet")

engine = db.engine()

t0 = time.time()
with engine.connect() as con:
    d = pd.read_sql(text(nearest_sql("patches", "runap_sub", "ap_id")), con)
    n_patches = con.execute(text("SELECT count(*) FROM patches")).scalar()
assert len(d) == n_patches, f"{len(d):,} rows for {n_patches:,} patches"
assert not d.duplicated(["loss_year", "patch_id"]).any()
# beyond the buffer, an area that wasn't loaded could be nearer
assert d.dist_m.max() < TARGET_BUFFER, f"max distance {d.dist_m.max():,.0f} m >= buffer {TARGET_BUFFER:,} m"

d = d.rename(columns={"target_id": "pa_id", "dist_m": "pa_dist_m"})
d["in_pa"] = d.pa_dist_m == 0
OUT.parent.mkdir(parents=True, exist_ok=True)
d.sort_values(["loss_year", "patch_id"]).to_parquet(OUT, index=False)
print(f"{len(d):,} patches, {time.time() - t0:.0f} s; median distance {d.pa_dist_m.median():,.0f} m, "
      f"{d.in_pa.mean():.1%} in or touching a protected area")
