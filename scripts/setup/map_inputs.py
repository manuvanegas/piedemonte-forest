"""
Quick-look maps of the inputs, before any analysis.

Out: figures/inputs/sources.png        roads, protected areas, resguardos, rivers over the study area
     figures/inputs/rivers_el_doncello.png  IGAC 1:100k vs HydroRIVERS in one municipio
     figures/inputs/treatment.png      treatment (D7) by municipio, with border shares

El Doncello is shown because it spans both Andean foothills and flat lowland.
"""
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
import shapely
from matplotlib.patches import Patch

RAW = Path("data.nosync/raw")
PROC = Path("data.nosync/processed")
OUT = Path("figures/inputs")
ADM2 = f"zip://{RAW}/hdx_cod_ab/col-administrative-divisions-shapefiles.zip!col_admbnda_adm2_mgn_20200416.shp"
RUNAP = f"zip://{RAW}/runap/runap_latest.zip!runap.shp"
GRIP = f"zip://{RAW}/grip4/GRIP4_Region2_vector_shp.zip!GRIP4_region2.shp"
HYRIV = f"zip://{RAW}/hydrorivers/HydroRIVERS_v10_sa_shp.zip!HydroRIVERS_v10_sa_shp/HydroRIVERS_v10_sa.shp"
SIMPLIFY = 200  # m, display only
LABEL_SHIFT = {"El Dorado": (9000, 9000), "Lejanías": (-12000, 4000)}  # m, avoid overlaps
C = {"land": "#f4f1ea", "park": "#7fb27f", "road": "#555555", "river": "#1f6fb2", "river1": "#9cc3e6", "river2": "#0b2e59",
     "res": "#a0522d",
     "hyriv": "#d1495b", "treated": "#c2553d", "added": "#eba08f", "control": "#e8e2d6", "na": "#b5b5b5"}

OUT.mkdir(parents=True, exist_ok=True)
munis = gpd.read_parquet(PROC / "study_municipios.parquet")
area = gpd.read_parquet(PROC / "study_area.parquet")
area_u = area.union_all()
depts = munis.dissolve("ADM1_ES").reset_index()
depts["geometry"] = depts.simplify(SIMPLIFY)
bbox = tuple(area.to_crs(4326).total_bounds)


def finish(fig, ax, name, title):
    ax.set_title(title, fontsize=9, loc="left")
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("saved", OUT / name)


# --- sources overview ---
runap = gpd.read_file(RUNAP, bbox=bbox).to_crs(9377)
runap = gpd.clip(runap, area_u)
roads = gpd.clip(gpd.read_file(GRIP, bbox=bbox).to_crs(9377), area_u)
sen = gpd.clip(gpd.read_parquet(RAW / "igac_drenaje/drenaje_sencillo.parquet").to_crs(9377), area_u)
res = gpd.read_parquet(RAW / "ant_resguardos/resguardos.parquet", columns=["geometry"])
res["geometry"] = shapely.make_valid(res.geometry.values, method="structure", keep_collapsed=False)
res = gpd.clip(res.to_crs(9377), area_u)
dob = gpd.clip(gpd.read_parquet(RAW / "igac_drenaje/drenaje_doble.parquet").to_crs(9377), area_u)

fig, ax = plt.subplots(figsize=(9, 10))
depts.plot(ax=ax, color=C["land"], edgecolor="black", linewidth=0.8)
runap.simplify(SIMPLIFY).plot(ax=ax, color=C["park"], alpha=0.6, linewidth=0)
# hatch, not fill, so overlaps with protected areas show both
res.simplify(SIMPLIFY).plot(ax=ax, facecolor="none", edgecolor=C["res"], hatch="////", linewidth=0.5)
sen.plot(ax=ax, color=C["river1"], linewidth=0.3)
dob.plot(ax=ax, color=C["river2"], linewidth=0.4, edgecolor=C["river2"])
roads.plot(ax=ax, color=C["road"], linewidth=0.35)
for _, r in depts.iterrows():
    p = r.geometry.representative_point()
    ax.annotate(r.ADM1_ES.upper(), (p.x, p.y), fontsize=8, ha="center", alpha=0.5, weight="bold")
finish(fig, ax, "sources.png", "Study area: protected areas (RUNAP, green), Indigenous resguardos (ANT, brown hatch),\n"
       "roads (GRIP4, grey), rivers (IGAC 1:100k; single-line light blue, double-line dark blue)")

# --- rivers in El Doncello ---
mu = munis[munis.ADM2_ES == "El Doncello"]
x0, y0, x1, y1 = mu.total_bounds
win = gpd.GeoSeries.from_xy([x0 - 3000, x1 + 3000], [y0 - 3000, y1 + 3000], crs=9377).union_all().envelope
zoom = (x0 + 0.55 * (x1 - x0), y0, x1, y0 + 0.3 * (y1 - y0))
hyriv = gpd.clip(gpd.read_file(HYRIV, bbox=tuple(mu.to_crs(4326).buffer(0.05).total_bounds)).to_crs(9377), win)
s_mu, d_mu = gpd.clip(sen, win), gpd.clip(dob, win)

fig, axs = plt.subplots(1, 2, figsize=(13, 9), gridspec_kw={"width_ratios": [1, 1.3]})
for ax, lim in [(axs[0], None), (axs[1], zoom)]:
    hyriv.plot(ax=ax, color=C["hyriv"], linewidth=1.6 if lim else 0.9, alpha=0.8)
    s_mu.plot(ax=ax, color=C["river"], linewidth=0.8 if lim else 0.35)
    d_mu.plot(ax=ax, color=C["river2"])
    mu.boundary.plot(ax=ax, color="black", linewidth=0.8)
    if lim:
        ax.set_xlim(lim[0], lim[2]); ax.set_ylim(lim[1], lim[3])
    ax.set_axis_off()
axs[0].set_title("El Doncello (Caquetá)", fontsize=9, loc="left")
axs[1].set_title("Zoom: lowland south-east", fontsize=9, loc="left")
fig.suptitle("IGAC 1:100k single-line (blue) and double-line (dark blue) vs HydroRIVERS v1.0 (red, all reaches)",
             fontsize=10)
fig.tight_layout()
fig.savefig(OUT / "rivers_el_doncello.png", dpi=160, bbox_inches="tight")
plt.close(fig)
print("saved", OUT / "rivers_el_doncello.png")

# --- treatment ---
adm2 = gpd.read_file(ADM2).to_crs(9377)
near = adm2[adm2.intersects(area_u.buffer(60_000))][["ADM2_PCODE", "geometry"]]
near = near.merge(pd.read_parquet(PROC / "treatment_all.parquet"), on="ADM2_PCODE", how="left")
near["geometry"] = near.simplify(SIMPLIFY)
t = munis.merge(pd.read_parquet(PROC / "treatment.parquet"), on="ADM2_PCODE")

added = t[(t.treated == 1) & (t.FARC1 == 0)]
fill = near.FARC1.map({1: C["treated"], 0: C["control"]}).fillna(C["na"])
fill[near.ADM2_PCODE.isin(added.ADM2_PCODE)] = C["added"]

fig, ax = plt.subplots(figsize=(9, 10))
near.plot(ax=ax, color=fill, edgecolor="white", linewidth=0.3)
depts.boundary.plot(ax=ax, color="black", linewidth=1.1)
for _, r in t[(t.FARC1 == 0) & (t.border_treated_share >= 0.5)].iterrows():
    p = r.geometry.representative_point()
    dx, dy = LABEL_SHIFT.get(r.ADM2_ES, (0, 0))
    ax.annotate(f"{r.ADM2_ES}\n{r.border_treated_share:.0%}", (p.x + dx, p.y + dy), fontsize=6.5, ha="center")
ax.legend(handles=[Patch(color=C["treated"], label="FARC1 = 1 (Prem et al. 2020)"),
                   Patch(color=C["added"], label="added by this project: ≥ 80% of border\nwith FARC1 municipios and FARC2 = 1"),
                   Patch(color=C["control"], label="neither")],
          loc="lower left", fontsize=7.5, frameon=False)
finish(fig, ax, "treatment.png", "Pre-ceasefire armed-group presence by municipio (study area outlined; neighbours shown for context).\n"
       "Labels: share of border with FARC1 municipios, for study municipios with FARC1 = 0")
