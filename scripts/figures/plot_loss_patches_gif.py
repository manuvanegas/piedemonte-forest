"""
Animated map: each year's loss patches (>= 2 px, D13), binned into 2 km cells, over the two municipio groups.
A cell is drawn when at least 1 ha was lost in it that year, coloured by the forest type (D12) that lost more
area there, more opaque the larger the share of the cell lost (full at 5%). Loss of earlier years (from 2008)
stays in grey. Patches are binned by a point inside each patch, so a patch larger than a cell counts in one cell.

In:  patch table with geometry (patch_table.py), study_municipios.parquet, study_area.parquet, treatment.parquet
Out: figures/loss/loss_patches.gif

Usage: python scripts/figures/plot_loss_patches_gif.py
"""
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import to_rgb
from matplotlib.legend_handler import HandlerPatch
from matplotlib.patches import Patch, Rectangle
from PIL import Image

from piedemonte_forest import loss_rule as lr
from piedemonte_forest import plot_style as ps
from piedemonte_forest.patch_table import patch_table

RAW = Path("data.nosync/raw")
PROC = Path("data.nosync/processed")
OUT = Path("figures/loss/loss_patches.gif")
ADM2 = f"zip://{RAW}/hdx_cod_ab/col-administrative-divisions-shapefiles.zip!col_admbnda_adm2_mgn_20200416.shp"
CELL = 2000  # m
MIN_HA = 1.0  # smallest loss in a cell that is drawn
FULL = 0.05  # share of the cell lost at full colour
SHADE = 0.10  # group shading
OUTLINE = "#8a8a8a"  # study area and group boundaries
OLD_GROWTH, SECONDARY, EARLIER = "#C8361B", "#E3A21A", "#9a9a9a"
FRAME_MS, LAST_MS = 1000, 3000
DPI = 110

munis = gpd.read_parquet(PROC / "study_municipios.parquet").merge(
    pd.read_parquet(PROC / "treatment.parquet")[["ADM2_PCODE", "treated"]], on="ADM2_PCODE", validate="one_to_one")
# dissolve before simplifying: simplified neighbours leave slivers that show as stray lines
groups = munis.dissolve("treated").simplify(300)
munis["geometry"] = munis.simplify(300)
area = gpd.read_parquet(PROC / "study_area.parquet")
colombia = gpd.read_file(ADM2).to_crs(9377).simplify(1000).buffer(1).union_all()
x0, y0, x1, y1 = area.total_bounds
xe, ye = np.arange(x0, x1 + CELL, CELL), np.arange(y0, y1 + CELL, CELL)
extent = (xe[0], xe[-1], ye[0], ye[-1])
cell_ha = CELL * CELL / 1e4

# loss per cell and year: old-growth and secondary ha (rows = y)
years = list(range(lr.FIRST_YEAR, lr.LAST_YEAR + 1))
prim, sec = {}, {}
for y in years:
    t = patch_table(years=[y], geometry=True)
    pt = t.geometry.representative_point()
    p_ha = t.area_ha * (1 - t.secondary_share)
    prim[y] = np.histogram2d(pt.x, pt.y, [xe, ye], weights=p_ha)[0].T
    sec[y] = np.histogram2d(pt.x, pt.y, [xe, ye], weights=t.area_ha - p_ha)[0].T


def layer(color, alpha):
    img = np.zeros((*alpha.shape, 4))
    img[..., :3] = to_rgb(color)
    img[..., 3] = alpha
    return img


class SquareHandler(HandlerPatch):
    """Square legend swatch, right-aligned in the handle box (the group swatches stay rectangles)."""

    def create_artists(self, legend, orig, xdescent, ydescent, width, height, fontsize, trans):
        sq = Rectangle((width - height - xdescent, -ydescent), height, height, transform=trans,
                       facecolor=orig.get_facecolor(), edgecolor="none")
        return [sq]


frames = []
earlier = np.zeros_like(prim[years[0]])
for y in years:
    tot = prim[y] + sec[y]
    alpha = np.clip(np.sqrt(tot / cell_ha / FULL), 0.25, 1) * (tot >= MIN_HA)
    now = layer(OLD_GROWTH, alpha)
    now[sec[y] > prim[y], :3] = to_rgb(SECONDARY)
    past = layer(EARLIER, np.clip(earlier / cell_ha / 0.02, 0, 1) * 0.45 * (earlier >= MIN_HA))

    fig, ax = plt.subplots(figsize=(8, 7.4))
    munis.plot(ax=ax, color=munis.treated.map(ps.GROUP_COLOR), alpha=SHADE, edgecolor="white", linewidth=0.3)
    ax.imshow(past, extent=extent, origin="lower", interpolation="antialiased", zorder=2)
    ax.imshow(now, extent=extent, origin="lower", interpolation="antialiased", zorder=3)
    groups.boundary.plot(ax=ax, color=OUTLINE, linewidth=0.6, zorder=4)
    area.boundary.plot(ax=ax, color=OUTLINE, linewidth=0.7, zorder=4)
    loc = ax.inset_axes([0.0, 0.7, 0.22, 0.28])
    gpd.GeoSeries([colombia], crs=9377).plot(ax=loc, color="#dddddd", linewidth=0)
    area.plot(ax=loc, color="black", linewidth=0)
    loc.set_axis_off()
    ax.set_axis_off()
    ax.set_title("Forest loss by year", fontsize=10, loc="left")
    ax.text(1.0, 1.0, str(y), transform=ax.transAxes, ha="right", va="top", fontsize=24, color=ps.INK, weight="bold")
    # column-wise: loss entries first, then the two groups
    # group swatches at the map's shading, outlined like the groups on the map
    loss_keys = [Patch(color=OLD_GROWTH, label="Loss, mostly old-growth forest"),
                 Patch(color=SECONDARY, label="Loss, mostly secondary forest"),
                 Patch(color=EARLIER, alpha=0.45, label=f"Loss in earlier years (from {years[0]})")]
    fig.legend(handles=loss_keys + [Patch(facecolor=(*to_rgb(ps.GROUP_COLOR[g]), SHADE), edgecolor=OUTLINE, linewidth=0.6,
                                          label=ps.GROUP_LABEL[g]) for g in (1, 0)],
               handler_map={h: SquareHandler() for h in loss_keys},
               loc="lower center", ncol=2, fontsize=8, frameon=False)
    fig.tight_layout(rect=(0, 0.09, 1, 1))
    fig.canvas.draw()
    frames.append(Image.fromarray(np.asarray(fig.canvas.buffer_rgba())).convert("RGB"))
    plt.close(fig)
    earlier += tot
    print(y, f"{tot.sum():,.0f} ha")

# one 256-colour palette for all frames, built from all of them, so pale tints keep their hue
strip = Image.new("RGB", (frames[0].width, frames[0].height * len(frames)))
for i, f in enumerate(frames):
    strip.paste(f, (0, i * f.height))
palette = strip.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
frames = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
OUT.parent.mkdir(parents=True, exist_ok=True)
frames[0].save(OUT, save_all=True, append_images=frames[1:], loop=0, optimize=False,
               duration=[FRAME_MS] * (len(frames) - 1) + [LAST_MS])
print("saved", OUT, f"{OUT.stat().st_size / 1e6:.1f} MB")
