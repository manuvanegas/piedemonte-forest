"""
Mean slope of each loss patch over its own pixels (SRTM, A11). The loss raster is labelled again with
the same components as vectorize_loss.py, so labels are the patch_ids; slope sits on the same grid.
Void pixels (NODATA) are left out of the mean.

In:  data.nosync/processed/loss/loss_<year>.tif, data.nosync/processed/slope/slope.tif,
     data.nosync/processed/loss_patches/patches_<year>.parquet (to check the labels)
Out: data.nosync/processed/covariates/slope.parquet (patches with n_px >= 2, D13)

Usage: python scripts/loss/slope_per_patch.py
"""
import time
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

import loss_rule as lr
import patch_tools as pt

LOSS = Path("data.nosync/processed/loss")
PATCHES = Path("data.nosync/processed/loss_patches")
SLOPE = Path("data.nosync/processed/slope/slope.tif")
OUT = Path("data.nosync/processed/covariates/slope.parquet")
MIN_PX = 2

t0 = time.time()
with rasterio.open(SLOPE) as src:
    slope, grid, nodata = src.read(1), (src.shape, src.transform, src.crs), src.nodata
valid = slope != nodata

parts = []
for year in range(lr.FIRST_YEAR, lr.LAST_YEAR + 1):
    t1 = time.time()
    with rasterio.open(LOSS / f"loss_{year}.tif") as src:
        assert (src.shape, src.transform, src.crs) == grid, f"{year}: loss and slope grids differ"
        loss = pt.decode(src.read(1))[0]
    labels, n_px = pt.label_components(loss, connectivity=4)
    mean = pt.patch_mean(labels, n_px, slope, valid) / 10  # tenths of a degree -> degrees
    del labels, loss
    d = pd.DataFrame({"loss_year": year, "patch_id": np.arange(1, len(n_px)), "n_px": n_px[1:],
                      "slope_mean_deg": mean})
    d = d[d.n_px >= MIN_PX]

    # same labels as the stored patches
    ref = pd.read_parquet(PATCHES / f"patches_{year}.parquet", columns=["patch_id", "n_px"])
    ref = ref[ref.n_px >= MIN_PX]
    check = d.merge(ref, on="patch_id", how="outer", suffixes=("", "_ref"), indicator=True)
    assert (check._merge == "both").all() and (check.n_px == check.n_px_ref).all(), f"{year}: labels differ"

    parts.append(d.drop(columns="n_px"))
    print(f"{year}: {len(d):,} patches, {d.slope_mean_deg.isna().sum()} without valid slope, "
          f"{time.time() - t1:.0f} s", flush=True)

d = pd.concat(parts, ignore_index=True)
OUT.parent.mkdir(parents=True, exist_ok=True)
d.to_parquet(OUT, index=False)
print(f"{len(d):,} patches, {time.time() - t0:.0f} s; median {d.slope_mean_deg.median():.1f} deg, "
      f"p90 {d.slope_mean_deg.quantile(0.9):.1f} deg")
