"""
Check: flicker by year, 2008-2022. Of forest in t-1, the area that is not forest in t and forest
again in t+1 or t+2 (any class, and anthropic classes only), next to all forest → non-forest
and loss under the rule.

Earth Engine: one reduction over 75 bands. About 3.3 EECU-h. The result is saved to
results/initial-checks/flicker.csv and reused; --rerun recomputes it.

Usage: python scripts/loss/check_flicker.py [--rerun]
"""
import os
import sys
from pathlib import Path

import ee
import pandas as pd
from dotenv import load_dotenv

import loss_rule as lr

YEARS = range(lr.FIRST_YEAR, 2023)  # t+2 <= 2024
OUT = Path("results/initial-checks/flicker.csv")
COLS = ["forest", "nonforest", "flicker", "flicker_anthro", "loss"]

if "--rerun" in sys.argv or not OUT.exists():
    load_dotenv()
    ee.Initialize(project=os.environ["EE_PROJECT"])
    f = {y: lr.is_in(lr.lulc(y), lr.FOREST) for y in range(min(YEARS) - 1, max(YEARS) + 3)}
    a = {y: lr.is_in(lr.lulc(y), lr.ANTHRO) for y in YEARS}
    ha = ee.Image.pixelArea().divide(1e4)
    bands = []
    for t in YEARS:
        nf = f[t - 1].And(f[t].Not())
        back = f[t + 1].Or(f[t + 2])
        masks = [f[t - 1], nf, nf.And(back), nf.And(a[t]).And(back), lr.loss(t)]
        bands += [ha.updateMask(m).rename(f"{k}_{t}") for k, m in zip(COLS, masks)]
    sums = ee.Image.cat(bands).reduceRegion(ee.Reducer.sum(), lr.study_area(), 30, crs="EPSG:4326",
                                            maxPixels=1e11, tileScale=4)
    res, eecu = lr.get_info(sums)
    rows = pd.DataFrame([{"t": t} | {k: round(res[f"{k}_{t}"], 2) for k in COLS} for t in YEARS])
    lr.save_check(OUT, rows, eecu_s=round(eecu))

d, meta = lr.load_check(OUT)
d = d.set_index("t")
print(f"run {meta['run']}, {meta['eecu_s']} EECU-s")
print(pd.DataFrame({
    "nonforest_%": 100 * d.nonforest / d.forest,
    "flicker_%": 100 * d.flicker / d.forest,
    "flicker_of_nonforest_%": 100 * d.flicker / d.nonforest,
    "flicker_anthro_ha": d.flicker_anthro,
    "loss_ha": d.loss,
    "loss_%": 100 * d.loss / d.forest,
}).round(2).to_string())
