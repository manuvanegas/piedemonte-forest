"""
Study-area municipios (Caquetá, Guaviare, Meta, Putumayo) and their dissolved outline.

In:  HDX COD-AB admin-2 boundaries (DANE MGN 2020), read from the zip.
Out: data.nosync/processed/study_municipios.parquet, study_area.parquet (EPSG:9377).
"""
from pathlib import Path

import geopandas as gpd

ADM2 = "zip://data.nosync/raw/hdx_cod_ab/col-administrative-divisions-shapefiles.zip!col_admbnda_adm2_mgn_20200416.shp"
OUT = Path("data.nosync/processed")
DEPTS = ["Caquetá", "Guaviare", "Meta", "Putumayo"]

adm2 = gpd.read_file(ADM2)
m = adm2[adm2.ADM1_ES.isin(DEPTS)].to_crs(9377)
m = m[["ADM2_PCODE", "ADM2_ES", "ADM1_PCODE", "ADM1_ES", "geometry"]].reset_index(drop=True)
m["area_km2"] = m.area / 1e6

assert set(m.ADM1_ES) == set(DEPTS), set(DEPTS) - set(m.ADM1_ES)
assert len(m) == 62 and m.ADM2_PCODE.is_unique, len(m)
assert set(m.geom_type) <= {"Polygon", "MultiPolygon"}

OUT.mkdir(parents=True, exist_ok=True)
m.to_parquet(OUT / "study_municipios.parquet")
m.dissolve()[["geometry"]].assign(area_km2=lambda d: d.area / 1e6).to_parquet(OUT / "study_area.parquet")
print(m.groupby("ADM1_ES").agg(n=("ADM2_PCODE", "size"), km2=("area_km2", "sum")).round())
