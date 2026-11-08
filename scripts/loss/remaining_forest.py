"""
Remaining forest for loss year t, per study municipio: forest (classes 3 and 6, D11) in both t-2 and t-1,
the only pixels the loss rule (D9) can flag in t. Denominator of the annual loss rate (D15).

Earth Engine: one reduceRegions per loss year over 62 municipios (borders simplified to 50 m as a
coverage, so neighbours still share them), about 1.3 EECU-h a year. Years already in the output are
skipped, so a test year is kept.

In:  data.nosync/processed/study_municipios.parquet
Out: data.nosync/processed/remaining_forest.parquet (ADM2_PCODE, loss_year, forest_ha)

Usage: python scripts/loss/remaining_forest.py [YEAR ...]   (default: every loss year)
"""
import json
import os
import sys
import time
from pathlib import Path

import ee
import geopandas as gpd
import pandas as pd
import shapely
from dotenv import load_dotenv

from piedemonte_forest import loss_rule as lr

OUT = Path("data.nosync/processed/remaining_forest.parquet")

load_dotenv()
ee.Initialize(project=os.environ["EE_PROJECT"])

muni = gpd.read_parquet("data.nosync/processed/study_municipios.parquet")[["ADM2_PCODE", "geometry"]]
muni["geometry"] = shapely.coverage_simplify(muni.geometry.values, 50)
fc = ee.FeatureCollection(json.loads(muni.to_crs(4326).to_json(drop_id=True)))

years = [int(y) for y in sys.argv[1:]] or list(range(lr.FIRST_YEAR, lr.LAST_YEAR + 1))
done = pd.read_parquet(OUT) if OUT.exists() else pd.DataFrame(columns=["ADM2_PCODE", "loss_year", "forest_ha"])

for year in years:
    if year in set(done.loss_year):
        print(year, "already in", OUT)
        continue
    forest = lr.is_in(lr.lulc(year - 2), lr.FOREST).And(lr.is_in(lr.lulc(year - 1), lr.FOREST))
    ha = ee.Image.pixelArea().divide(1e4).updateMask(forest).rename("forest_ha")
    sums = ha.reduceRegions(fc, ee.Reducer.sum().setOutputs(["forest_ha"]), 30, crs="EPSG:4326", tileScale=4)

    t0 = time.time()
    res, eecu = lr.get_info(sums.select(["ADM2_PCODE", "forest_ha"], retainGeometry=False))
    d = pd.DataFrame([f["properties"] for f in res["features"]]).assign(loss_year=year)
    assert len(d) == len(muni), f"{len(d)} results for {len(muni)} municipios"
    done = pd.concat([done, d[["ADM2_PCODE", "loss_year", "forest_ha"]]], ignore_index=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    done.sort_values(["loss_year", "ADM2_PCODE"]).to_parquet(OUT, index=False)  # saved before printing
    print(f"{year}: {d.forest_ha.sum():,.0f} ha remaining; {eecu:,.0f} EECU-s, {time.time() - t0:.0f} s")
