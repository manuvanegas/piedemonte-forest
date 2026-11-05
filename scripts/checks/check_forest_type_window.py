"""
Check: forest type of loss in year t (default 2023) under the full history (main) vs a fixed
23-year window (robustness). Backs D12.

Earth Engine: area of loss in t grouped by secondary (window), secondary (full) and age (full).
About 1-2 EECU-h for 2023 (both histories). The result is saved to
results/initial-checks/forest_type_window_<t>.csv and reused; --rerun recomputes it.

Usage: python scripts/checks/check_forest_type_window.py [year] [--rerun]
"""
import os
import sys
from pathlib import Path

import ee
import pandas as pd
from dotenv import load_dotenv

from piedemonte_forest import loss_rule as lr

T = int(next((a for a in sys.argv[1:] if a.isdigit()), 2023))
OUT = Path(f"results/initial-checks/forest_type_window_{T}.csv")

if "--rerun" in sys.argv or not OUT.exists():
    load_dotenv()
    ee.Initialize(project=os.environ["EE_PROJECT"])
    full, window = lr.forest_type(T), lr.forest_type(T, lookback=lr.LOOKBACK)
    key = (window.select("secondary").multiply(1000).add(full.select("secondary").multiply(100))
           .add(full.select("sec_age").unmask(0))).updateMask(lr.loss(T))
    ha = ee.Image.pixelArea().divide(1e4)
    tally = ha.addBands(key).reduceRegion(ee.Reducer.sum().group(1, "key"), lr.study_area(), 30,
                                          crs="EPSG:4326", maxPixels=1e10, tileScale=4)
    res, eecu = lr.get_info(tally)
    k = pd.Series([g["key"] for g in res["groups"]])
    groups = pd.DataFrame({"sec_window": k // 1000, "sec_full": k // 100 % 10, "age_full": k % 100,
                           "ha": [round(g["sum"], 2) for g in res["groups"]]})
    lr.save_check(OUT, groups, year=T, eecu_s=round(eecu))

d, meta = lr.load_check(OUT)
tot = d.ha.sum()
print(f"loss {T}: {tot:,.0f} ha (run {meta['run']}, {meta['eecu_s']} EECU-s)")
for (w, f), g in d.groupby(["sec_window", "sec_full"]):
    print(f"window {'sec' if w else 'pri'}, full {'sec' if f else 'pri'}: {g.ha.sum():,.0f} ha "
          f"({100 * g.ha.sum() / tot:.1f}%)")
diff = d[(d.sec_window == 0) & (d.sec_full == 1)]
print(f"primary under the window, secondary under full history: ages {diff.age_full.min()}-{diff.age_full.max()}")
sec = d[d.sec_full == 1]
print("secondary (full) by age (ha):",
      sec.groupby(pd.cut(sec.age_full, [1, 4, 9, 14, 19, 23, 40])).ha.sum().round(0).to_dict())
