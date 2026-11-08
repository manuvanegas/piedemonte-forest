"""
Loss patches with n_px >= MIN_PX (D13) and all their covariates, one row per patch, for figures and summaries.
Run from the repository root.
"""
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyarrow.parquet as pq

from piedemonte_forest import loss_rule as lr

PATCHES = Path("data.nosync/processed/loss_patches")
COVARIATES = Path("data.nosync/processed/covariates")
LAYERS = ["roads", "rivers", "protected_areas", "resguardos", "earlier_clearings", "slope"]
KEY = ["loss_year", "patch_id"]


def patch_table(years=None, geometry=False):
    """
    years     loss years to read (default: all, FIRST_YEAR-LAST_YEAR)
    geometry  True returns a GeoDataFrame with patch polygons (EPSG:9377); False drops them (faster, smaller)
    """
    years = list(years or range(lr.FIRST_YEAR, lr.LAST_YEAR + 1))
    assert all(lr.FIRST_YEAR <= y <= lr.LAST_YEAR for y in years), years

    parts = []
    for y in years:
        path = PATCHES / f"patches_{y}.parquet"
        if geometry:
            p = gpd.read_parquet(path)
        else:
            p = pd.read_parquet(path, columns=[c for c in pq.read_schema(path).names if c != "geometry"])
        parts.append(p[p.n_px >= lr.MIN_PX])
    t = pd.concat(parts, ignore_index=True)
    assert t.treated.notna().all(), "patch without municipio"

    for layer in LAYERS:
        c = pd.read_parquet(COVARIATES / f"{layer}.parquet", filters=[("loss_year", "in", years)])
        t = t.merge(c, on=KEY, how="left", validate="one_to_one", indicator=True)
        assert (t._merge == "both").all() and len(c) == len(t), f"{layer}: rows don't match the patches"
        t = t.drop(columns="_merge")
    return t
