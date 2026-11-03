"""
Download ANT's formalized indigenous resguardos (whole country) into data.nosync/raw/ant_resguardos/.
Skips the file if it exists.

Source: Agencia Nacional de Tierras open-data portal, layer "Resguardo Indígena Formalizado" (data
updated 2026-06-25 per the layer description), queried in pages. The only date is
ULTIMA_FECHA_ACTO_ADMIN, the last administrative act. Department/municipio fields are DANE codes.
Saved as served (GeoJSON output, EPSG:4326). Accessed 2026-11-02.
"""
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

OUT = Path("data.nosync/raw/ant_resguardos/resguardos.parquet")
SVC = ("https://utility.arcgis.com/usrsvcs/servers/8944116ccfd34a7189c4bc44b8e19186/rest/services/"
       "DatosAbiertos/Resguardo_Indigena_Formalizado/FeatureServer/0")
PAGE = 100  # large polygons; small pages keep each response manageable
HDR = {"User-Agent": "Mozilla/5.0"}


def get(params, tries=5):
    for i in range(tries):
        try:
            r = requests.get(f"{SVC}/query", params=params, headers=HDR, timeout=300)
            r.raise_for_status()
            js = r.json()
            if "error" in js:
                raise RuntimeError(js["error"])
            return js
        except Exception as e:
            if i == tries - 1:
                raise
            print(f"    retry {i + 1}: {e}")
            time.sleep(30 * (i + 1))


if OUT.exists():
    print(f"skip  {OUT.name}")
else:
    t0 = time.time()
    n = get({"where": "1=1", "returnCountOnly": "true", "f": "json"})["count"]
    parts, off = [], 0
    while off < n:
        js = get({"where": "1=1", "outFields": "*", "outSR": 4326, "orderByFields": "OBJECTID",
                  "resultOffset": off, "resultRecordCount": PAGE, "f": "geojson"})
        feats = js.get("features", [])
        if not feats:
            break
        parts.append(gpd.GeoDataFrame.from_features(feats, crs=4326))
        off += len(feats)
        print(f"  {off}/{n}")
    g = pd.concat(parts, ignore_index=True).drop_duplicates("OBJECTID").reset_index(drop=True)
    assert len(g) == n, f"{len(g)} features, server says {n}"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    g.to_parquet(OUT)
    print(f"got   {OUT.name} ({len(g)} features, {time.time() - t0:.0f} s)")
