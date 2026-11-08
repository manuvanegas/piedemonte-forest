"""
Check: agreement between MapBiomas loss (D9, all pixels, D13) and Hansen GFC v1.13 loss (D5), 2013-2023,
per municipio and forest type at t-1 (D12). Both ways:
  mb  MapBiomas loss in t; matched if Hansen loss in t-1..t+1
  h   Hansen loss in t inside MapBiomas remaining forest (D15); matched if MapBiomas loss in t-1..t+1
Hansen is read on the MapBiomas grid (nearest neighbour; pixel 0.00025° vs 0.000269°). Two match rules:
  same  same pixel
  near  within one pixel (3x3 neighbourhood), for misalignment between the two products
MapBiomas loss stops at 2023 (needs 2024), so for t = 2023 the h window is 2022-2023 only.

Earth Engine: one reduceRegions per year over 62 municipios. Years already in the output are skipped,
so a test year is kept; --rerun recomputes all.

In:  data.nosync/processed/study_municipios.parquet
Out: results/loss/gfc_agreement.csv (ADM2_PCODE, year, {mb,h}_{total,same,near}_{old_growth,secondary} in ha)

Usage: python scripts/checks/check_gfc_agreement.py [YEAR ...] [--rerun]   (default: 2013-2023)
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

HANSEN = "UMD/hansen/global_forest_change_2025_v1_13"
bands_names = ["mb_total", "mb_same", "mb_near", "h_total", "h_same", "h_near"]
FIRST = 2013  # D5
OUT = Path("results/loss/gfc_agreement.csv")

load_dotenv()
ee.Initialize(project=os.environ["EE_PROJECT"])

muni = gpd.read_parquet("data.nosync/processed/study_municipios.parquet")[["ADM2_PCODE", "geometry"]]
muni["geometry"] = shapely.coverage_simplify(muni.geometry.values, 50)
fc = ee.FeatureCollection(json.loads(muni.to_crs(4326).to_json(drop_id=True)))
grid = lr.lulc(lr.FIRST_YEAR).projection().getInfo()  # MapBiomas grid for every band

h_year = ee.Image(HANSEN).select("lossyear")  # 1-25 = 2001-2025, 0 = no loss


def near(img):
    """1 where img is 1 in the pixel or one of its 8 neighbours."""
    return img.focalMax(radius=1, kernelType="square", units="pixels")


def bands(year):
    window = [y for y in (year - 1, year, year + 1) if lr.HISTORY_FIRST <= y <= lr.LAST_YEAR]
    mb = lr.loss(year)
    mb_win = ee.Image(0)
    for y in window:
        mb_win = mb_win.Or(lr.loss(y))
    h = h_year.eq(year - 2000).unmask(0)
    h_win = h_year.gte(year - 2001).And(h_year.lte(year - 1999)).unmask(0)
    remaining = lr.is_in(lr.lulc(year - 2), lr.FOREST).And(lr.is_in(lr.lulc(year - 1), lr.FOREST))
    h = h.And(remaining)
    secondary = lr.forest_type(year).select("secondary")
    sets = {"mb_total": mb, "mb_same": mb.And(h_win), "mb_near": mb.And(near(h_win)),
            "h_total": h, "h_same": h.And(mb_win), "h_near": h.And(near(mb_win))}
    ha = ee.Image.pixelArea().divide(1e4)
    out = []
    for name, m in sets.items():
        for ftype, sel in (("old_growth", secondary.Not()), ("secondary", secondary)):
            out.append(ha.updateMask(m.And(sel)).rename(f"{name}_{ftype}"))
    return ee.Image.cat(out).unmask(0)


years = [int(a) for a in sys.argv[1:] if a.isdigit()] or list(range(FIRST, lr.LAST_YEAR + 1))
rerun = "--rerun" in sys.argv
done = pd.read_csv(OUT) if OUT.exists() and not rerun else pd.DataFrame(columns=["ADM2_PCODE", "year"])
for year in years:
    assert FIRST <= year <= lr.LAST_YEAR, year
    if year in set(done.year):
        print(year, "already in", OUT)
        continue
    img = bands(year)
    sums = img.reduceRegions(fc, ee.Reducer.sum(), crs=grid["crs"], crsTransform=grid["transform"], tileScale=4)
    t0 = time.time()
    res, eecu = lr.get_info(sums.select(["ADM2_PCODE"] + img.bandNames().getInfo(), retainGeometry=False))
    d = pd.DataFrame([f["properties"] for f in res["features"]]).assign(year=year)
    assert len(d) == len(muni), f"{len(d)} results for {len(muni)} municipios"
    done = pd.concat([done, d], ignore_index=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    done.sort_values(["year", "ADM2_PCODE"]).to_csv(OUT, index=False)  # saved before printing
    s = {k: d[f"{k}_old_growth"].sum() + d[f"{k}_secondary"].sum() for k in [*bands_names]}
    print(f"{year}: MapBiomas loss {s['mb_total']:,.0f} ha, matched {s['mb_same'] / s['mb_total']:.1%} (same px) / "
          f"{s['mb_near'] / s['mb_total']:.1%} (1 px); Hansen loss in forest {s['h_total']:,.0f} ha, matched "
          f"{s['h_same'] / s['h_total']:.1%} / {s['h_near'] / s['h_total']:.1%}; "
          f"{eecu:,.0f} EECU-s, {time.time() - t0:.0f} s")
