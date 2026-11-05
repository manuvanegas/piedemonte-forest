"""
Check: where forest goes in year t (default 2015), compared with MapBiomas' own transition statistics.
Backs D10: class 25 counts as anthropic; forest → grassland, wetland or water is not loss.

Earth Engine: area of pixels that are forest in t-2 and t-1 and not forest in t, grouped by their
classes in t, t+1, t+2, t+3, plus forest area in t-1. About 0.35 EECU-h. The result is saved to
results/initial-checks/loss_destinations_<t>.csv and reused; --rerun recomputes it.
Comparison: forest → class t-1 → t for the four departments, from the MapBiomas Colombia Col. 3
transition statistics (~104 MB zip, downloaded once). Theirs is a plain one-year transition.

Usage: python scripts/checks/check_loss_destinations.py [year] [--rerun]
"""
import io
import os
import sys
import zipfile
from pathlib import Path

import ee
import pandas as pd
import requests
from dotenv import load_dotenv

from piedemonte_forest import loss_rule as lr

T = int(next((a for a in sys.argv[1:] if a.isdigit()), 2015))
OUT = Path(f"results/initial-checks/loss_destinations_{T}.csv")
STATS_URL = ("https://storage.googleapis.com/mapbiomas-public/initiatives/colombia/collection_3/"
             "statistics/statistics_for_website_mb_colombia_transision_col3.zip")
STATS_ZIP = Path("data.nosync/raw/mapbiomas_stats") / STATS_URL.rsplit("/", 1)[1]
STATS_CACHE = Path("data.nosync/processed/mapbiomas_transitions_departamento.parquet")
DEPTS = ["Caquetá", "Guaviare", "Meta", "Putumayo"]

if "--rerun" in sys.argv or not OUT.exists():
    load_dotenv()
    ee.Initialize(project=os.environ["EE_PROJECT"])
    c = [lr.lulc(y) for y in range(T, T + 4)]
    forest = {y: lr.is_in(lr.lulc(y), lr.FOREST) for y in (T - 2, T - 1, T)}
    cand = forest[T - 2].And(forest[T - 1]).And(forest[T].Not())
    key = c[0].multiply(1_000_000).add(c[1].multiply(10_000)).add(c[2].multiply(100)).add(c[3])
    ha = ee.Image.pixelArea().divide(1e4)
    kw = dict(geometry=lr.study_area(), scale=30, crs="EPSG:4326", maxPixels=1e10, tileScale=4)
    tally = ha.addBands(key.updateMask(cand)).reduceRegion(ee.Reducer.sum().group(1, "key"), **kw)
    forest_prev = ha.updateMask(forest[T - 1]).reduceRegion(ee.Reducer.sum(), **kw)
    res, eecu = lr.get_info(ee.Dictionary({"tally": tally, "forest_prev": forest_prev}))
    k = pd.Series([g["key"] for g in res["tally"]["groups"]])
    groups = pd.DataFrame({"c_t": k // 1_000_000, "c_t1": k // 10_000 % 100, "c_t2": k // 100 % 100,
                           "c_t3": k % 100, "ha": [round(g["sum"], 2) for g in res["tally"]["groups"]]})
    lr.save_check(OUT, groups, year=T, eecu_s=round(eecu), forest_prev_ha=round(res["forest_prev"]["area"]))

d, meta = lr.load_check(OUT)
forest_prev = float(meta["forest_prev_ha"])
loss = d[d.c_t.isin(lr.ANTHRO) & d.c_t1.isin(lr.ANTHRO)].ha.sum()
print(f"{T}: forest {T - 1} {forest_prev:,.0f} ha; forest {T - 2}-{T - 1} and not forest {T} "
      f"{d.ha.sum():,.0f} ha; loss (rule) {loss:,.0f} ha ({meta['eecu_s']} EECU-s, run {meta['run']})")
for cls in (12, 25):
    g = d[d.c_t == cls]
    share = (100 * g.groupby("c_t3").ha.sum() / g.ha.sum()).round(1).sort_values(ascending=False)
    print(f"forest -> {cls} in {T} ({g.ha.sum():,.0f} ha), class in {T + 3} (%): {share.head(4).to_dict()}")

if not STATS_CACHE.exists():
    if not STATS_ZIP.exists():
        STATS_ZIP.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(STATS_URL, stream=True, timeout=60) as r:
            r.raise_for_status()
            STATS_ZIP.write_bytes(r.content)
    with zipfile.ZipFile(STATS_ZIP) as z:
        xlsx = io.BytesIO(z.read(z.namelist()[0]))
    pd.read_excel(xlsx, sheet_name="TRANS_DEPARTAMENTO").to_parquet(STATS_CACHE)
s = pd.read_parquet(STATS_CACHE)
s = s[s.departamento.isin(DEPTS) & s.class_from.isin(lr.FOREST)]
col = f"p{T - 1}_{T}"
cmp = pd.DataFrame({"mapbiomas_stats": s[~s.class_to.isin(lr.FOREST)].groupby("class_to")[col].sum(),
                    "ours": d.groupby("c_t").ha.sum()}).fillna(0).round(0)
cmp = cmp.sort_values("mapbiomas_stats", ascending=False)
print(f"\nforest {T - 1}: MapBiomas stats {s[col].sum():,.0f} ha vs ours {forest_prev:,.0f} ha")
print(f"forest -> not forest {T - 1}->{T} by class (ha); ours also requires forest in {T - 2}:")
print(cmp.head(10).to_string())
print(f"forest -> anthropic: MapBiomas stats {cmp.loc[cmp.index.isin(lr.ANTHRO), 'mapbiomas_stats'].sum():,.0f}"
      f" vs ours {cmp.loc[cmp.index.isin(lr.ANTHRO), 'ours'].sum():,.0f} (before the t+1 check)")
