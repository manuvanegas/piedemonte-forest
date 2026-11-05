"""
Exploration: how much slope varies across the forest, at the same 48,000 random 2007 forest points as
explore_covariate_spread.py (run that first; it draws the points). Kept apart from that table, which is
in km and judged against the hex span; slope is in degrees.

In:  data.nosync/processed/exploration/background_points.parquet, data.nosync/processed/slope/slope.tif
Out: results/exploration/slope_spread.csv

Usage: python scripts/exploration/explore_slope_spread.py
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio

from piedemonte_forest import loss_rule as lr

POINTS = Path("data.nosync/processed/exploration/background_points.parquet")
SLOPE = Path("data.nosync/processed/slope/slope.tif")
OUT = Path("results/exploration/slope_spread.csv")

pts = gpd.read_parquet(POINTS)
with rasterio.open(SLOPE) as src:
    xy = pts.to_crs(src.crs).geometry
    v = np.array([s[0] for s in src.sample(zip(xy.x, xy.y))], dtype=float)
    v[v == src.nodata] = np.nan
d = pd.Series(v[~np.isnan(v)] / 10)  # tenths of a degree -> degrees

q = d.quantile([0.1, 0.5, 0.9])
row = {"layer": "slope (SRTM)", "n": len(d), "no_data": int(np.isnan(v).sum()),
       "p10_deg": q[0.1], "median_deg": q[0.5], "p90_deg": q[0.9],
       "under_5deg": (d < 5).mean(), "over_15deg": (d > 15).mean()}
lr.save_check(OUT, pd.DataFrame([row]).round(3), points=f"{len(pts):,} random points in forest in 2007 "
              "(explore_covariate_spread.py)")
df, meta = lr.load_check(OUT)
print("\n".join(f"{k}: {v}" for k, v in meta.items()))
print(df.to_string(index=False))
