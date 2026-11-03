"""
Distance from each loss patch to the nearest IGAC 1:100.000 double-line river (A9), queried against
rivers_sub. A patch touching or inside a river surface gets distance 0.

Needs PostGIS loaded by load_patches.py (all years) and load_targets.py --rivers.
Out: data.nosync/processed/covariates/rivers.parquet

Usage: python scripts/loss/distance_rivers.py
"""
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

import db
from patch_distances import TARGET_BUFFER, nearest_sql

OUT = Path("data.nosync/processed/covariates/rivers.parquet")

engine = db.engine()

t0 = time.time()
with engine.connect() as con:
    d = pd.read_sql(text(nearest_sql("patches", "rivers_sub", "river_id")), con)
    n_patches = con.execute(text("SELECT count(*) FROM patches")).scalar()
assert len(d) == n_patches, f"{len(d):,} rows for {n_patches:,} patches"
assert not d.duplicated(["loss_year", "patch_id"]).any()
# beyond the buffer, a river that wasn't loaded could be nearer
assert d.dist_m.max() < TARGET_BUFFER, f"max distance {d.dist_m.max():,.0f} m >= buffer {TARGET_BUFFER:,} m"

d = d.rename(columns={"target_id": "river_id", "dist_m": "river_dist_m"})
OUT.parent.mkdir(parents=True, exist_ok=True)
d.sort_values(["loss_year", "patch_id"]).to_parquet(OUT, index=False)
print(f"{len(d):,} patches, {time.time() - t0:.0f} s; median distance {d.river_dist_m.median():,.0f} m, "
      f"max {d.river_dist_m.max() / 1e3:,.1f} km")
