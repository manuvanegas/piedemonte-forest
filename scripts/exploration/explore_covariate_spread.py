"""
Exploration: how much distance to each target layer varies across the forest, overall and by road
zone (nearest road within 10 km or farther). Loss patches serve only as a target (earlier clearing).
A layer whose p10-p90 range fits inside one H3 res-7 hex (corner to corner) gives hexes nearly the
same value, whatever the grouping, so it can't tell them apart. Roads are the main other way in; the
far zone shows what a layer offers away from them.

Points: 48,000 random points in forest (classes 3 and 6, D11) in 2007, the year before the first loss
year, drawn in the study area; the forest flag comes from Earth Engine, coordinates are drawn locally.
Distances are computed with geopandas against the same 200 km target sets as the loaders (A8).

Needs HydroRIVERS (make input-quicklook). Points are saved to
data.nosync/processed/exploration/background_points.parquet, the table to
results/exploration/covariate_spread.csv; both are reused. --rerun recomputes the table from the
saved points, --redraw also draws new points (Earth Engine).

Usage: python scripts/exploration/explore_covariate_spread.py [--rerun | --redraw]
"""
import os
import sys
from pathlib import Path

import ee
import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import shapely
from dotenv import load_dotenv

from piedemonte_forest import loss_rule as lr
from piedemonte_forest.patch_distances import TARGET_BUFFER

RAW = Path("data.nosync/raw")
POINTS = Path("data.nosync/processed/exploration/background_points.parquet")
PATCHES = Path("data.nosync/processed/loss_patches")
OUT = Path("results/exploration/covariate_spread.csv")
CRS = 9377
N_POINTS = 48_000
FOREST_YEAR = lr.FIRST_YEAR - 1
SEED = 0
CHUNK = 5_000  # points per Earth Engine request
ROAD_ZONE = 10_000  # m
HEX_SPAN = 2 * h3.average_hexagon_edge_length(7, "km")  # corner to corner, ~2.8 km
HYRIV = RAW / "hydrorivers/HydroRIVERS_v10_sa_shp.zip"


def background_points(area, n):
    """n random points in forest in FOREST_YEAR, inside `area` (EPSG:9377), and the EECU cost."""
    load_dotenv()
    ee.Initialize(project=os.environ["EE_PROJECT"])
    forest = lr.is_in(lr.lulc(FOREST_YEAR), lr.FOREST).rename("forest")
    rng = np.random.default_rng(SEED)
    x0, y0, x1, y1 = area.bounds
    kept, eecu = [], 0.0
    while sum(len(k) for k in kept) < n:
        xy = gpd.GeoSeries(gpd.points_from_xy(rng.uniform(x0, x1, CHUNK), rng.uniform(y0, y1, CHUNK)), crs=CRS)
        xy = xy[xy.within(area)].to_crs(4326)
        fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([p.x, p.y]), {"i": int(i)}) for i, p in xy.items()])
        got, cost = lr.get_info(forest.sampleRegions(fc, scale=30, geometries=False))
        eecu += cost
        flag = pd.Series({f["properties"]["i"]: f["properties"]["forest"] for f in got["features"]})
        kept.append(xy[flag.reindex(xy.index).fillna(0).astype(bool).to_numpy()])
        print(f"  background: {sum(len(k) for k in kept):,}/{n:,}", flush=True)
    pts = pd.concat(kept, ignore_index=True).iloc[:n].to_crs(CRS)
    return gpd.GeoDataFrame(geometry=pts.values, crs=CRS), eecu


def targets(ring):
    """Target layers within the 200 km ring (EPSG:9377), as in the loaders, plus the comparison layers."""
    if not HYRIV.exists():
        sys.exit(f"missing {HYRIV}: run make input-quicklook")
    bbox = tuple(gpd.GeoSeries([ring], crs=CRS).to_crs(4326).total_bounds)
    read = lambda path, **kw: gpd.read_file(path, bbox=bbox, **kw).to_crs(CRS)
    roads = read(f"zip://{RAW}/grip4/GRIP4_Region2_vector_shp.zip!GRIP4_region2.shp", columns=["GP_RTP"])
    runap = gpd.read_file(f"zip://{RAW}/runap/runap_latest.zip!runap.shp").to_crs(CRS)
    single = gpd.read_parquet(RAW / "igac_drenaje/drenaje_sencillo.parquet", columns=["geometry"]).to_crs(CRS)
    double = gpd.read_parquet(RAW / "igac_drenaje/drenaje_doble.parquet", columns=["geometry"]).to_crs(CRS)
    res = gpd.read_parquet(RAW / "ant_resguardos/resguardos.parquet", columns=["geometry"])
    res["geometry"] = shapely.make_valid(res.geometry.values, method="structure", keep_collapsed=False)
    hyriv = read(f"zip://{HYRIV}!HydroRIVERS_v10_sa_shp/HydroRIVERS_v10_sa.shp", columns=["DIS_AV_CMS"])
    # the three-year window before the first loss year (D14); patches are inside the study area
    earlier = pd.concat([gpd.read_parquet(PATCHES / f"patches_{y}.parquet", columns=["n_px", "geometry"])
                         for y in range(FOREST_YEAR - 2, FOREST_YEAR + 1)])
    earlier = earlier[earlier.n_px >= 2]  # D13
    layers = {
        "road (GRIP4)": roads,
        "protected area (RUNAP)": runap,
        "Indigenous resguardo (ANT)": res.to_crs(CRS),
        f"earlier clearing ({FOREST_YEAR - 2}-{FOREST_YEAR} loss)": earlier,
        "river: IGAC single- and double-line": pd.concat([single, double]),
        "river: IGAC double-line": double,
        **{f"river: HydroRIVERS >= {q} m3/s": hyriv[hyriv.DIS_AV_CMS >= q] for q in (1, 5, 20)},
    }
    return {k: gpd.GeoDataFrame(geometry=v.geometry.values, crs=CRS).pipe(lambda g: g[g.intersects(ring)])
            for k, v in layers.items()}


def nearest(points, target):
    j = gpd.sjoin_nearest(points[["geometry"]], target, distance_col="d")
    return j[~j.index.duplicated()].d.reindex(points.index)


redraw = "--redraw" in sys.argv
if redraw or "--rerun" in sys.argv or not OUT.exists():
    area = gpd.read_parquet("data.nosync/processed/study_area.parquet").to_crs(CRS).union_all()
    ring = area.buffer(TARGET_BUFFER)

    if redraw or not POINTS.exists():
        bg, eecu = background_points(area, N_POINTS)
        POINTS.parent.mkdir(parents=True, exist_ok=True)
        bg.assign(draw_eecu_s=round(eecu, 1)).to_parquet(POINTS)  # cost kept with the points
    pts = gpd.read_parquet(POINTS)
    eecu = pts.pop("draw_eecu_s").iloc[0]

    layers = targets(ring)
    for name, t in layers.items():
        pts[name] = nearest(pts, t) / 1e3
        print(f"  {name}", flush=True)
    road = pts["road (GRIP4)"]
    zones = {"all": road.notna(), f"road <= {ROAD_ZONE // 1000} km": road <= ROAD_ZONE / 1e3,
             f"road > {ROAD_ZONE // 1000} km": road > ROAD_ZONE / 1e3}

    rows = []
    for name in layers:
        for zone, inz in zones.items():
            d = pts.loc[inz, name]
            p10, p90 = d.quantile([0.1, 0.9])
            rows.append({"layer": name, "road_zone": zone, "n": len(d), "p10_km": p10, "median_km": d.median(),
                         "p90_km": p90, "p10_p90_km": p90 - p10, "fits_in_hex": p90 - p10 < HEX_SPAN,
                         "within_1km": (d < 1).mean(), "within_2km": (d < 2).mean(), "zero": (d == 0).mean()})
    meta = {"points": f"{len(pts):,} random points in forest in {FOREST_YEAR}, seed {SEED}",
            "hex_span_km": round(HEX_SPAN, 2), "background_draw_eecu_s": eecu}
    lr.save_check(OUT, pd.DataFrame(rows).round(3), **meta)

df, meta = lr.load_check(OUT)
print("\n".join(f"{k}: {v}" for k, v in meta.items()))
with pd.option_context("display.width", 200, "display.max_columns", 20):
    print(df.to_string(index=False))
