"""
Check: time of the nearest-protected-area query (nearest_sql) on a random sample of 2015 patches,
against RUNAP as loaded and split into pieces of at most 256 vertices (runap_sub), extrapolated to
2015 and to all years, with each target table's rows and vertices. Both must give the same answer.

Needs PostGIS loaded by load_patches.py (2015 at least) and load_targets.py --runap. The result is saved to
results/initial-checks/nearest_timing.csv and reused; --rerun recomputes it.

Usage: python scripts/checks/check_nearest_timing.py [--rerun]
"""
import platform
import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from piedemonte_forest import db
from piedemonte_forest import loss_rule as lr
from piedemonte_forest.patch_distances import nearest_sql

OUT = Path("results/initial-checks/nearest_timing.csv")
N = 10_000
SEED = 0.42
TARGETS = {"runap": "ap_id", "runap_sub": "ap_id"}

if "--rerun" in sys.argv or not OUT.exists():
    engine = db.engine()
    sizes = pd.read_csv("results/initial-checks/patch_sizes.csv", comment="#")
    kept = sizes[(sizes.connectivity == 4) & (sizes["size"] != "1")]
    n_2015, n_all = kept[kept.year == 2015].patches.sum(), kept.patches.sum()

    with engine.begin() as con:
        con.execute(text(f"SELECT setseed({SEED}); DROP TABLE IF EXISTS timing_sample; "
                         "CREATE TABLE timing_sample AS SELECT * FROM patches WHERE loss_year = 2015 "
                         f"ORDER BY random() LIMIT {N}; ANALYZE timing_sample"))
        pg = con.execute(text("SELECT postgis_lib_version()")).scalar()
        db_arch = con.execute(text("SELECT version()")).scalar().split(" on ")[1].split(",")[0]
    rows, first = [], None
    for target, tid in TARGETS.items():
        t0 = time.time()
        with engine.connect() as con:
            d = pd.read_sql(text(nearest_sql("timing_sample", target, tid)), con)
        s = time.time() - t0
        if first is None:
            first = d.set_index("patch_id")
        same = d.set_index("patch_id").reindex(first.index)
        same_id = (same.target_id == first.target_id).mean()
        max_diff = (same.dist_m - first.dist_m).abs().max()
        nv = pd.read_sql(text(f"SELECT ST_NPoints(geometry) AS nv FROM {target}"), engine).nv
        rows.append({"target": target, "sample": len(d), "seconds": round(s, 1),
                     "ms_per_patch": round(s / len(d) * 1000, 2),
                     "est_h_2015": round(s / len(d) * n_2015 / 3600, 2),
                     "est_h_all_years": round(s / len(d) * n_all / 3600, 1),
                     "target_rows": len(nv), "target_nv_p99": round(nv.quantile(0.99)), "target_nv_max": nv.max(),
                     "median_dist_m": round(d.dist_m.median()), "share_inside": round((d.dist_m == 0).mean(), 3),
                     "same_target_as_runap": same_id, "max_dist_diff_m": round(max_diff, 6)})
        print(target, end=" ", flush=True)
    with engine.begin() as con:
        con.execute(text("DROP TABLE timing_sample"))
    lr.save_check(OUT, pd.DataFrame(rows), seed=SEED, postgis=pg, db_arch=db_arch,
                  host=platform.machine())

d, meta = lr.load_check(OUT)
print(f"\nrun {meta['run']}, PostGIS {meta['postgis']} ({meta['db_arch']}) on {meta['host']}:")
print(d.to_string(index=False))
