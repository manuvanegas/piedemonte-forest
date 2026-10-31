"""
Check: how much loss, and how much of it secondary, sits in small patches. Backs D13 (the minimum
mapping unit filters patches at analysis time; area and rates use every loss pixel).

Per year and connectivity (4, 8): loss pixels, components and secondary share by patch size
(1, 2, 3-5, 6-10, 11-100, >100 px). Local only (no Earth Engine). The result is saved to
results/initial-checks/patch_sizes.csv and reused; --rerun recomputes it.

Usage: python scripts/loss/check_patch_sizes.py [--rerun]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

import loss_rule as lr
import patch_tools as pt

LOSS = Path("data.nosync/processed/loss")
OUT = Path("results/initial-checks/patch_sizes.csv")
BINS = [0, 1, 2, 5, 10, 100, np.inf]
NAMES = ["1", "2", "3-5", "6-10", "11-100", ">100"]

if "--rerun" in sys.argv or not OUT.exists():
    rows = []
    for year in range(lr.FIRST_YEAR, lr.LAST_YEAR + 1):
        with rasterio.open(LOSS / f"loss_{year}.tif") as src:
            loss, _, sec_age = pt.decode(src.read(1))
        for conn in (4, 8):
            labels, n_px = pt.label_components(loss, conn)
            m = labels > 0
            size = pd.cut(n_px[labels[m]], BINS, labels=NAMES)
            px = pd.DataFrame({"size": size, "secondary": sec_age[m] > 0})
            d = px.groupby("size", observed=False).agg(loss_px=("secondary", "size"),
                                                      secondary_px=("secondary", "sum"))
            d["patches"] = pd.cut(n_px[1:], BINS, labels=NAMES).value_counts().reindex(NAMES).values
            rows.append(d.reset_index().assign(year=year, connectivity=conn))
        print(year, end=" ", flush=True)
    lr.save_check(OUT, pd.concat(rows)[["year", "connectivity", "size", "patches", "loss_px", "secondary_px"]])

d, meta = lr.load_check(OUT)
d["size"] = pd.Categorical(d["size"].astype(str), NAMES, ordered=True)
for conn, g in d.groupby("connectivity"):
    t = g.groupby("size", observed=False)[["patches", "loss_px", "secondary_px"]].sum()
    t["share_loss_px"] = (t.loss_px / t.loss_px.sum()).round(3)
    t["secondary_share"] = (t.secondary_px / t.loss_px).round(3)
    print(f"\n{conn}-connected, {d.year.min()}-{d.year.max()} (run {meta['run']}):")
    print(t[["patches", "share_loss_px", "secondary_share"]].to_string())
by_year = d[d.connectivity == 4].assign(small=lambda x: x["size"].isin(["1"])).groupby(["year", "small"]).loss_px.sum().unstack()
print("\nshare of loss px in single-pixel patches (4-conn), by year:")
print((by_year[True] / by_year.sum(axis=1)).round(3).to_string())
