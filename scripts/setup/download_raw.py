"""
Download raw inputs into data.nosync/raw/. Skips files that already exist.
--optional also fetches inputs used only by the quick-look maps.

RUNAP's "latest.zip" is not versioned: the copy used here was accessed 2026-06-28.
"""
import hashlib
import sys
from pathlib import Path

import requests

RAW = Path("data.nosync/raw")

SOURCES = {
    "hdx_cod_ab/col-administrative-divisions-shapefiles.zip":
        "https://data.humdata.org/dataset/50ea7fee-f9af-45a7-8a52-abb9c790a0b6/resource/"
        "32fba556-0109-4d1c-84cb-c8abddf7775b/download/col-administrative-divisions-shapefiles.zip",
    "runap/runap_latest.zip":
        "https://storage.googleapis.com/pnn_geodatabase/runap/latest.zip",
    "grip4/GRIP4_Region2_vector_shp.zip":
        "https://zenodo.org/api/records/6420961/files/GRIP4_Region2_vector_shp.zip/content",
    "prem2020/RepliDataset.zip":
        "https://www.dropbox.com/s/555dnlnapw6j4o0/RepliDataset.zip?dl=1",
}

OPTIONAL = {
    "hydrorivers/HydroRIVERS_v10_sa_shp.zip":
        "https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_sa_shp.zip",
}
if "--optional" in sys.argv:
    SOURCES |= OPTIONAL


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


for rel, url in SOURCES.items():
    out = RAW / rel
    if out.exists():
        print(f"skip  {rel} ({out.stat().st_size / 1e6:.0f} MB, sha1 {sha1(out)[:12]})")
        continue
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".part")
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    tmp.rename(out)
    print(f"got   {rel} ({out.stat().st_size / 1e6:.0f} MB, sha1 {sha1(out)[:12]})")
