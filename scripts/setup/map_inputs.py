"""
Maps of the inputs: the two municipio groups, and the landscape layers the loss patches are measured against.

Out: figures/inputs/treatment.png  pre-ceasefire armed-group presence (D7) by municipio, with a locator map
     figures/inputs/sources.png    roads, double-line rivers (A9), protected areas, resguardos and slope, one
                                   panel each, over the two municipio groups (faint shading)
Prints, per group, the shares and densities the landscape map is read for.
"""
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
import shapely
from matplotlib.patches import Patch
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject

from piedemonte_forest import plot_style as ps

RAW = Path("data.nosync/raw")
PROC = Path("data.nosync/processed")
OUT = Path("figures/inputs")
ADM2 = f"zip://{RAW}/hdx_cod_ab/col-administrative-divisions-shapefiles.zip!col_admbnda_adm2_mgn_20200416.shp"
RUNAP = f"zip://{RAW}/runap/runap_latest.zip!runap.shp"
GRIP = f"zip://{RAW}/grip4/GRIP4_Region2_vector_shp.zip!GRIP4_region2.shp"
SLOPE = PROC / "slope/slope.tif"  # tenths of a degree
SIMPLIFY = 200  # m, display only
SLOPE_RES = 250  # m, display only
SLOPE_READ = 4  # read every 4th source pixel's block average (~120 m) before reprojecting, display only
SHADE = 0.25  # group shading under the layers; lighter on top of the slope raster
SHADE_SLOPE = 0.12
C = {"land": "#f4f1ea", "dept": "#9a9a9a", "park": "#5e9e5e", "road": "#444444", "river": "#0b4f8a",
     "res": "#7b5ea7"}

OUT.mkdir(parents=True, exist_ok=True)
munis = gpd.read_parquet(PROC / "study_municipios.parquet").merge(
    pd.read_parquet(PROC / "treatment.parquet")[["ADM2_PCODE", "treated"]], on="ADM2_PCODE", validate="one_to_one")
area = gpd.read_parquet(PROC / "study_area.parquet")
area_u = area.union_all()
depts = munis.dissolve("ADM1_ES").reset_index()
depts["geometry"] = depts.simplify(SIMPLIFY)
bbox = tuple(area.to_crs(4326).total_bounds)


shaded = munis.assign(geometry=munis.simplify(SIMPLIFY))


def groups_shade(ax, alpha, zorder=1):
    shaded.plot(ax=ax, color=shaded.treated.map(ps.GROUP_COLOR), alpha=alpha, edgecolor="white", linewidth=0.3,
                zorder=zorder)
    depts.boundary.plot(ax=ax, color=C["dept"], linewidth=0.5, zorder=zorder)


def save(fig, name):
    fig.savefig(OUT / name, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("saved", OUT / name)


# --- the two groups ---
colombia = gpd.read_file(ADM2).to_crs(9377).simplify(1000).buffer(1).union_all()
fig, ax = plt.subplots(figsize=(8, 8.5))
m = munis.assign(geometry=munis.simplify(SIMPLIFY))
m.plot(ax=ax, color=m.treated.map(ps.GROUP_COLOR), alpha=0.85, edgecolor="white", linewidth=0.4)
depts.boundary.plot(ax=ax, color="black", linewidth=0.9)
for _, r in depts.iterrows():
    p = r.geometry.representative_point()
    ax.annotate(r.ADM1_ES.upper(), (p.x, p.y), fontsize=8, ha="center", color="white", weight="bold")
n = munis.treated.value_counts()
ax.legend(handles=[Patch(color=ps.GROUP_COLOR[1], alpha=0.85, label=f"{ps.GROUP_LABEL[1]} ({n[1]} municipios)"),
                   Patch(color=ps.GROUP_COLOR[0], alpha=0.85, label=f"{ps.GROUP_LABEL[0]} ({n[0]} municipios)")],
          loc="upper center", bbox_to_anchor=(0.5, 0.02), fontsize=8, frameon=False)
inset = ax.inset_axes([0.0, 0.62, 0.26, 0.3])
gpd.GeoSeries([colombia], crs=9377).plot(ax=inset, color="#dddddd", linewidth=0)
area.plot(ax=inset, color="black", linewidth=0)
inset.set_axis_off()
ax.set_title("Municipios by pre-ceasefire armed-group presence", fontsize=10, loc="left")
ax.set_axis_off()
save(fig, "treatment.png")

# --- landscape layers ---
roads = gpd.clip(gpd.read_file(GRIP, bbox=bbox).to_crs(9377), area_u)
rivers = gpd.clip(gpd.read_parquet(RAW / "igac_drenaje/drenaje_doble.parquet").to_crs(9377), area_u)
runap = gpd.clip(gpd.read_file(RUNAP, bbox=bbox).to_crs(9377), area_u)
res = gpd.read_parquet(RAW / "ant_resguardos/resguardos.parquet", columns=["geometry"])
res["geometry"] = shapely.make_valid(res.geometry.values, method="structure", keep_collapsed=False)
res = gpd.clip(res.to_crs(9377), area_u)

with rasterio.open(SLOPE) as src:
    small = src.read(1, out_shape=(src.height // SLOPE_READ, src.width // SLOPE_READ),
                     resampling=Resampling.average).astype("float32")
    small[small == src.nodata] = np.nan
    small_tr = src.transform * src.transform.scale(src.width / small.shape[1], src.height / small.shape[0])
    tr, w, h = calculate_default_transform(src.crs, "EPSG:9377", small.shape[1], small.shape[0], *src.bounds,
                                           resolution=SLOPE_RES)
    slope = np.full((h, w), np.nan, dtype="float32")
    reproject(small, slope, src_transform=small_tr, src_crs=src.crs, dst_transform=tr, dst_crs="EPSG:9377",
              resampling=Resampling.average, src_nodata=np.nan, dst_nodata=np.nan)
slope /= 10
extent = (tr.c, tr.c + tr.a * w, tr.f + tr.e * h, tr.f)

panels = ["Roads (GRIP4, 2012 mapping)", "Wide rivers (IGAC drainage, 1:100,000)",
          "Protected areas (RUNAP, current boundaries)", "Indigenous resguardos (ANT, current boundaries)",
          "Slope (SRTM, 2000)"]
fig, axes = plt.subplots(2, 3, figsize=(12, 7.2))
for ax, title in zip(axes.flat, panels):
    if title.startswith("Slope"):
        area.plot(ax=ax, color=C["land"], linewidth=0)
    else:
        groups_shade(ax, SHADE)
    ax.set_title(title, fontsize=9, loc="left")
    ax.set_axis_off()
a = axes.flat
roads.plot(ax=a[0], color=C["road"], linewidth=0.3)
rivers.plot(ax=a[1], color=C["river"], linewidth=0.4, edgecolor=C["river"])
runap.simplify(SIMPLIFY).plot(ax=a[2], color=C["park"], alpha=0.9, linewidth=0)
res.simplify(SIMPLIFY).plot(ax=a[3], color=C["res"], alpha=0.9, linewidth=0)
im = a[4].imshow(slope, extent=extent, cmap="Greys", vmin=0, vmax=15, interpolation="antialiased", zorder=2)
groups_shade(a[4], SHADE_SLOPE, zorder=3)
for ax in axes.flat[:5]:
    ax.set_xlim(area.total_bounds[[0, 2]])
    ax.set_ylim(area.total_bounds[[1, 3]])
a[5].set_axis_off()
a[5].legend(handles=[Patch(facecolor=ps.GROUP_COLOR[g], edgecolor="none", alpha=SHADE + 0.15,
                           label=ps.GROUP_LABEL[g].replace(" armed", "\narmed")) for g in (1, 0)],
            loc="upper left", bbox_to_anchor=(0.22, 1.0), fontsize=8.5, frameon=False, title="Municipios",
            title_fontsize=8.5, alignment="left")
# left edge: the slope colourbar, next to the slope panel only; right: legend, then the locator
locator = a[5].inset_axes([0.22, 0.0, 0.55, 0.55])
gpd.GeoSeries([colombia], crs=9377).plot(ax=locator, color="#dddddd", linewidth=0)
area.plot(ax=locator, color="black", linewidth=0)
locator.set_axis_off()
cb = fig.colorbar(im, cax=a[5].inset_axes([0.0, 0.1, 0.035, 0.8]), orientation="vertical", extend="max")
cb.set_label("Slope (degrees)", fontsize=8)
cb.ax.tick_params(labelsize=7)
fig.tight_layout()
save(fig, "sources.png")

# --- what the landscape map is read for, per group ---
groups = {g: munis[munis.treated == g].union_all() for g in (1, 0)}
near_river = rivers.buffer(5000).union_all()
rows = {}
for g, geom in groups.items():
    km2 = geom.area / 1e6
    rows[ps.GROUP_LABEL[g]] = {
        "area_km2": km2,
        "road_km_per_1000km2": roads.clip(geom).length.sum() / 1e3 / km2 * 1000,
        "within_5km_of_double_river_%": geom.intersection(near_river).area / geom.area * 100,
        "protected_%": runap.union_all().intersection(geom).area / geom.area * 100,
        "resguardo_%": res.union_all().intersection(geom).area / geom.area * 100,
    }
print(pd.DataFrame(rows).round(1).to_string())
