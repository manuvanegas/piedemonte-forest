"""
Attach Prem et al. (2020) treatment flags to municipios, plus the share of each study municipio's
border shared with FARC1 neighbours (in any department), and the project treatment (D7):
FARC1, or FARC2 with at least BORDER_MIN of the border shared with FARC1 municipios.

Matching: department + municipio name, compared without accents, case, spaces or Prem's
parenthesised footnote marks; remaining spelling differences via prem_municipio_aliases.csv.
Prem's lon1/lat1 (lat at 2 decimals, ~1 km) only checks matches, never assigns them.
The join runs nationally so that neighbours outside the study area carry flags too.

In:  Prem replication panel (zip), HDX admin-2 (zip), study_municipios.parquet.
Out: data.nosync/processed/treatment.parquet (one row per study municipio, no geometry),
     treatment_all.parquet (flags for every matched municipio, for maps of neighbours).
"""
import io
import re
import unicodedata
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd

PREM = "data.nosync/raw/prem2020/RepliDataset.zip"
ADM2 = "zip://data.nosync/raw/hdx_cod_ab/col-administrative-divisions-shapefiles.zip!col_admbnda_adm2_mgn_20200416.shp"
STUDY = "data.nosync/processed/study_municipios.parquet"
ALIASES = "scripts/setup/prem_municipio_aliases.csv"
OUT = Path("data.nosync/processed/treatment.parquet")
OUT_ALL = OUT.with_name("treatment_all.parquet")
FLAGS = ["FARC1", "FARC1_P10", "FARC2", "FARC_N"]
CHECK_KM = 2  # point farther than this from its matched polygon gets flagged
BORDER_MIN = 0.8


def norm(s):
    s = re.sub(r"\(.*?\)", "", str(s))
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return "".join(c for c in s if c.isalnum())


# flags are static per municipio: keep one row each
with zipfile.ZipFile(PREM) as z:
    p = pd.read_stata(io.BytesIO(z.read("Dataset/YearlyPanel_ForReg.dta")), convert_categoricals=False)
p = p.groupby("M_code").first().reset_index()[["depto", "municipio", "lon1", "lat1"] + FLAGS]
assert len(p) == 1119

al = pd.read_csv(ALIASES)
fix = dict(zip(al.depto.map(norm) + "|" + al.prem_name.map(norm), al.adm2_name))
p["key"] = p.depto.map(norm) + "|" + p.municipio.map(norm)
p["match"] = p.key.map(lambda k: "alias" if k in fix else "name")
p["key"] = p.depto.map(norm) + "|" + p.apply(lambda r: norm(fix.get(r.key, r.municipio)), axis=1)

adm2 = gpd.read_file(ADM2).to_crs(9377)
adm2["key"] = adm2.ADM1_ES.map(norm) + "|" + adm2.ADM2_ES.map(norm)
assert adm2.key.is_unique and p.key.is_unique

m = adm2[["ADM2_PCODE", "key", "geometry"]].merge(p, on="key", how="left")
unmatched = p[~p.key.isin(adm2.key)]
print(f"Prem rows {len(p)}: matched {len(p) - len(unmatched)} ({(p.match == 'alias').sum()} via alias); "
      f"unmatched {unmatched[['depto', 'municipio']].values.tolist()}")
print(f"HDX municipios without a Prem row: {m.FARC1.isna().sum()}")

# point check
pts = gpd.GeoSeries(gpd.points_from_xy(m.lon1, m.lat1), crs=4326).to_crs(9377)
m["pt_dist_km"] = m.distance(pts, align=False) / 1e3

study = gpd.read_parquet(STUDY)
s = m[m.ADM2_PCODE.isin(study.ADM2_PCODE)].copy()
assert len(s) == 62 and s.FARC1.notna().all(), s[s.FARC1.isna()].ADM2_PCODE.tolist()

# border share with FARC1 neighbours; international borders count as untreated
farc1 = m[m.FARC1 == 1]
shares = []
for code, geom in zip(s.ADM2_PCODE, s.geometry):
    nb = farc1[(farc1.ADM2_PCODE != code) & farc1.intersects(geom.buffer(100))]
    edge = geom.boundary
    shares.append(edge.intersection(nb.union_all().buffer(100)).length / edge.length if len(nb) else 0.0)
s["border_treated_share"] = shares
s["treated"] = ((s.FARC1 == 1) | ((s.FARC2 == 1) & (s.border_treated_share >= BORDER_MIN))).astype(int)

s = s.rename(columns={"depto": "prem_depto", "municipio": "prem_municipio"})
cols = ["ADM2_PCODE", "prem_depto", "prem_municipio", "match", "pt_dist_km", *FLAGS, "border_treated_share", "treated"]
s = pd.DataFrame(s[cols]).astype({f: int for f in FLAGS}).sort_values("ADM2_PCODE").reset_index(drop=True)
s.to_parquet(OUT, index=False)
# written after OUT so make sees it as up to date
pd.DataFrame(m.loc[m.FARC1.notna(), ["ADM2_PCODE", *FLAGS]]).astype({f: int for f in FLAGS}).to_parquet(OUT_ALL, index=False)

far = s[s.pt_dist_km > CHECK_KM]
print(f"study municipios: {len(s)}; FARC1 = 1: {s.FARC1.sum()}; treated (D7): {s.treated.sum()}; via alias: {(s.match == 'alias').sum()}")
print("added by D7:", s.loc[(s.treated == 1) & (s.FARC1 == 0), "prem_municipio"].tolist())
print(f"point check (> {CHECK_KM} km from matched polygon): {far[['prem_municipio', 'pt_dist_km']].round(1).values.tolist()}")
print(s[s.FARC1 == 0].nlargest(8, "border_treated_share")[["prem_municipio", "FARC2", "FARC_N", "border_treated_share"]].round(2).to_string(index=False))
