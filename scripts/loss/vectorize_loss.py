"""
Annual loss patches: 4-connected components of each year's loss raster, all sizes kept (the minimum
mapping unit is a filter on n_px at analysis time). Each patch gets its municipio from a point
inside it (representative_point) and that municipio's treatment.

In:  data.nosync/processed/loss/loss_<year>.tif (download_loss.py)
Out: data.nosync/processed/loss_patches/patches_<year>.parquet (GeoParquet, EPSG:9377)

Usage: python scripts/loss/vectorize_loss.py [year ...]
"""
import sys
import time
from pathlib import Path

import geopandas as gpd
import rasterio

import loss_rule as lr
import patch_tools as pt

LOSS = Path("data.nosync/processed/loss")
OUT = Path("data.nosync/processed/loss_patches")
CRS = 9377

years = [int(a) for a in sys.argv[1:] if a.isdigit()] or list(range(lr.FIRST_YEAR, lr.LAST_YEAR + 1))
muni = gpd.read_parquet("data.nosync/processed/study_municipios.parquet")[["ADM2_PCODE", "ADM1_PCODE", "geometry"]]
treat = gpd.pd.read_parquet("data.nosync/processed/treatment.parquet")[["ADM2_PCODE", "treated"]]
muni = muni.merge(treat, on="ADM2_PCODE", how="left").to_crs(CRS)
OUT.mkdir(parents=True, exist_ok=True)

for year in years:
    t0 = time.time()
    with rasterio.open(LOSS / f"loss_{year}.tif") as src:
        code, transform, crs = src.read(1), src.transform, src.crs
    loss, to_class, sec_age = pt.decode(code)
    del code
    labels, n_px = pt.label_components(loss, connectivity=4)
    attr = pt.patch_attributes(labels, n_px, to_class, sec_age)
    ids, geoms = pt.polygonize(labels, transform)
    del labels, loss, to_class, sec_age

    g = gpd.GeoDataFrame({"patch_id": ids}, geometry=geoms, crs=crs).to_crs(CRS)
    assert g.patch_id.is_unique, f"{year}: a label produced several polygons"
    g = g.join(attr, on="patch_id")
    g.insert(0, "loss_year", year)
    g["area_ha"] = g.area / 1e4

    pts = gpd.GeoDataFrame(geometry=g.representative_point(), crs=CRS)
    m = gpd.sjoin(pts, muni, predicate="within").drop(columns=["index_right", "geometry"])
    g = g.join(m[~m.index.duplicated()])
    border = gpd.sjoin(g[["geometry"]], muni[["geometry"]], predicate="intersects").index.value_counts()
    straddle = g.area_ha[border[border > 1].index].sum() / g.area_ha.sum()

    g.to_parquet(OUT / f"patches_{year}.parquet")
    print(f"{year}: {len(g):,} patches, {g.area_ha.sum():,.0f} ha, {g.ADM2_PCODE.isna().sum()} without municipio, "
          f"{straddle:.2%} of area in patches crossing a municipio border, {time.time() - t0:.0f} s")
