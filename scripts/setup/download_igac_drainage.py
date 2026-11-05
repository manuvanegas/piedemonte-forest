"""
Download IGAC 1:100.000 drainage for the study departments and a BUFFER ring around them (the
distance-target rule, A8) into data.nosync/raw/igac_drenaje/. Skips files that already exist.
Colombia only: the ring's parts in Ecuador and Peru have no IGAC data.

Source: IDEAM's republication of the IGAC layers (service Cartografia_Basica/Hidrografia), queried in
0.5° tiles and paged; each tile is saved under tiles/ so a rerun resumes after a server outage.
Features crossing tile edges are deduplicated by objectid. Not clipped.
Saved as served (GeoJSON output, EPSG:4326). Departments accessed 2026-10-23, ring 2026-11-02.
"""
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely.geometry import box

RAW = Path("data.nosync/raw")
OUT = RAW / "igac_drenaje"
ADM2 = "zip://" + str(RAW / "hdx_cod_ab/col-administrative-divisions-shapefiles.zip") + "!col_admbnda_adm2_mgn_20200416.shp"
DEPTS = ["Caquetá", "Guaviare", "Meta", "Putumayo"]
SVC = "http://dhime.ideam.gov.co/server/rest/services/Cartografia_Basica/Hidrografia/MapServer"
LAYERS = {"drenaje_sencillo.parquet": 0, "drenaje_doble.parquet": 1}
TILE = 0.5
BUFFER = 200_000  # m, as TARGET_BUFFER in src/piedemonte_forest/patch_distances.py
PAGE = 1000
HDR = {"User-Agent": "Mozilla/5.0"}  # the server rejects requests without one


def get(url, params, tries=5):
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=HDR, timeout=180)
            r.raise_for_status()
            js = r.json()
            if "error" in js:
                raise RuntimeError(js["error"])
            return js
        except Exception as e:
            if i == tries - 1:
                raise
            print(f"    retry {i + 1}: {e}")
            time.sleep(60 * (i + 1))


def fetch_tile(layer, bounds):
    parts, off = [], 0
    while True:
        js = get(f"{SVC}/{layer}/query", {
            "where": "1=1", "geometry": ",".join(f"{v:.4f}" for v in bounds),
            "geometryType": "esriGeometryEnvelope", "inSR": 4326, "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*", "outSR": 4326, "orderByFields": "objectid",
            "resultOffset": off, "resultRecordCount": PAGE, "f": "geojson"})
        feats = js.get("features", [])
        if feats:
            parts.append(gpd.GeoDataFrame.from_features(feats, crs=4326))
        if len(feats) < PAGE and not js.get("exceededTransferLimit"):
            return parts
        off += len(feats)


aoi = gpd.read_file(ADM2)
aoi = aoi[aoi.ADM1_ES.isin(DEPTS)].to_crs(9377).union_all().buffer(BUFFER)
aoi = gpd.GeoSeries([aoi], crs=9377).to_crs(4326).iloc[0]
x0, y0, x1, y1 = aoi.bounds
tiles = [box(x, y, x + TILE, y + TILE) for x in np.arange(x0, x1, TILE) for y in np.arange(y0, y1, TILE)]
tiles = [t for t in tiles if t.intersects(aoi)]

OUT.mkdir(parents=True, exist_ok=True)
for name, layer in LAYERS.items():
    out = OUT / name
    if out.exists():
        print(f"skip  {name}")
        continue
    t0, parts = time.time(), []
    cache = OUT / "tiles" / out.stem
    cache.mkdir(parents=True, exist_ok=True)
    for i, t in enumerate(tiles, 1):
        f = cache / f"{i:04d}.parquet"
        if not f.exists():
            got = fetch_tile(layer, t.bounds)
            (pd.concat(got, ignore_index=True) if got else gpd.GeoDataFrame(geometry=[], crs=4326)).to_parquet(f)
        parts.append(gpd.read_parquet(f))
        print(f"  {name}: tile {i}/{len(tiles)}, {sum(len(p) for p in parts)} features")
    g = pd.concat([p for p in parts if len(p)], ignore_index=True).drop_duplicates("objectid").reset_index(drop=True)
    g.to_parquet(out)
    print(f"got   {name} ({len(g)} features, {time.time() - t0:.0f} s)")
