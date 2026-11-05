"""
Distance from each loss patch to the nearest road (GRIP4, the 2012 network, A5), queried against
roads_sub, with that road's GRIP4 type (2 primary, 3 secondary, 4 tertiary, 5 local).

Needs PostGIS loaded by load_patches.py (all years) and load_targets.py --roads.
Out: data.nosync/processed/covariates/roads.parquet

Usage: python scripts/covariates/distance_roads.py
"""
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from piedemonte_forest import db
from piedemonte_forest.patch_distances import TARGET_BUFFER, nearest_sql

OUT = Path("data.nosync/processed/covariates/roads.parquet")

engine = db.engine()

t0 = time.time()
with engine.connect() as con:
    d = pd.read_sql(text(nearest_sql("patches", "roads_sub", "road_id")), con)
    n_patches = con.execute(text("SELECT count(*) FROM patches")).scalar()
    types = pd.read_sql(text("SELECT road_id, road_type FROM roads"), con)
assert len(d) == n_patches, f"{len(d):,} rows for {n_patches:,} patches"
assert not d.duplicated(["loss_year", "patch_id"]).any()
# beyond the buffer, a road that wasn't loaded could be nearer
assert d.dist_m.max() < TARGET_BUFFER, f"max distance {d.dist_m.max():,.0f} m >= buffer {TARGET_BUFFER:,} m"

d = d.rename(columns={"target_id": "road_id", "dist_m": "road_dist_m"}).merge(types, on="road_id")
OUT.parent.mkdir(parents=True, exist_ok=True)
d.sort_values(["loss_year", "patch_id"]).to_parquet(OUT, index=False)
print(f"{len(d):,} patches, {time.time() - t0:.0f} s; median distance {d.road_dist_m.median():,.0f} m, "
      f"max {d.road_dist_m.max() / 1e3:,.1f} km")
