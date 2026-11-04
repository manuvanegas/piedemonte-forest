"""
MapBiomas Colombia Col. 3 classes and the annual forest-loss rule, as Earth Engine images.
Shared by the scripts in scripts/loss/. Decisions D8–D11 in docs/decisions/design.md.

loss_t = forest in t-2 and t-1, anthropic in t and t+1.
"""
import io
import json
import sys
from datetime import date
from pathlib import Path

import ee
import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping

ASSET = "projects/mapbiomas-colombia/assets/LULC/COLECCION3/INTEGRACION/COLOMBIA-1"
FIRST_YEAR, LAST_YEAR = 2008, 2023  # last year needs t+1 = 2024
HISTORY_FIRST = 2005  # 2005-2007: earlier-clearing targets only, not outcomes (D14)

FOREST = [3, 6]  # forest, flooded forest (D11)
ANTHRO = [9, 21, 24, 25, 30, 31, 35, 74, 75]  # D10


def lulc(year):
    return ee.Image(ASSET).select(f"classification_{year}")


def is_in(img, classes):
    return img.remap(classes, [1] * len(classes), 0)


def loss(year):
    assert HISTORY_FIRST <= year <= LAST_YEAR, year
    forest = [is_in(lulc(y), FOREST) for y in (year - 2, year - 1)]
    anthro = [is_in(lulc(y), ANTHRO) for y in (year, year + 1)]
    return forest[0].And(forest[1]).And(anthro[0]).And(anthro[1]).rename(f"loss_{year}")


FIRST_MAP = 1985
LOOKBACK = FIRST_YEAR - FIRST_MAP  # 23 years: same window for every loss year (robustness check)


def forest_type(year, lookback=None):
    """Bands `secondary` (0/1) and `sec_age` (years since the last clearing, masked if primary),
    as of t-1. A past clearing = two consecutive anthropic years, ending before t-2.
    Default: full history since 1985. lookback=LOOKBACK uses a fixed window instead (D12)."""
    start = FIRST_MAP if lookback is None else year - lookback
    assert start >= FIRST_MAP, (year, lookback)
    last = ee.Image(0)
    for y in range(start, year - 3):  # episode (y, y+1) ends by t-3
        episode = is_in(lulc(y), ANTHRO).And(is_in(lulc(y + 1), ANTHRO))
        last = last.max(episode.multiply(y + 1))
    secondary = last.gt(0)
    age = ee.Image(year - 1).subtract(last).updateMask(secondary)
    return secondary.rename("secondary").addBands(age.rename("sec_age"))


def study_area(path="data.nosync/processed/study_area.parquet"):
    # simplified ~200 m to keep requests small
    aoi = gpd.read_parquet(path).to_crs(4326).geometry.simplify(0.002).union_all()
    return ee.Geometry(json.loads(json.dumps(mapping(aoi))))


def get_info(obj):
    """getInfo() plus its cost in EECU-seconds (sum of the Earth Engine profile)."""
    buf = io.StringIO()
    with ee.profilePrinting(destination=buf):
        value = obj.getInfo()
    rows = [line.split() for line in buf.getvalue().splitlines()[1:]]
    return value, sum(float(r[0]) for r in rows if r and r[0] != "-")


def save_check(path, df, **meta):
    """CSV with `# key: value` header lines (run date, EECU cost, ...)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {"script": Path(sys.argv[0]).name, "run": str(date.today())} | meta
    with open(path, "w") as f:
        f.writelines(f"# {k}: {v}\n" for k, v in meta.items())
        df.to_csv(f, index=False)


def load_check(path):
    with open(path) as f:
        meta = dict(line[2:].rstrip("\n").split(": ", 1) for line in f if line.startswith("# "))
    return pd.read_csv(path, comment="#"), meta
