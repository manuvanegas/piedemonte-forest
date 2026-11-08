"""
Figure: where loss patches (>= 2 px, D13) sit, by year and pre-ceasefire armed-group presence. Each patch
counts once. Six panels: median distance to road and to river, share of patches touching a clearing of the
previous three years (D14), median patch slope, and the share of loss area in patches inside or touching a
protected area or a resguardo. Bands: 25th to 75th percentile of patches (spread, not uncertainty of the
median).

Distance to earlier clearing is shown as a share, not a median: 40% of patches touch an earlier clearing,
and the median (30-90 m) only steps between a few pixel spacings.

In:  patch table (patch_table.py)
Out: figures/loss/access_by_year.png

Usage: python scripts/figures/plot_access_by_year.py
"""
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

from piedemonte_forest import loss_rule as lr
from piedemonte_forest import plot_style as ps
from piedemonte_forest.patch_table import patch_table

OUT = "figures/loss/access_by_year.png"

t = patch_table().assign(road_km=lambda d: d.road_dist_m / 1e3, river_km=lambda d: d.river_dist_m / 1e3,
                         touch=lambda d: (d.earlier_dist_m == 0) * 100,
                         pa_ha=lambda d: d.area_ha * d.in_pa, res_ha=lambda d: d.area_ha * d.in_res)
gb = t.rename(columns={"slope_mean_deg": "slope"}).groupby(["loss_year", "treated"])
area = gb.area_ha.sum()
g = gb[["road_km", "river_km", "slope"]].median().assign(touch=gb.touch.mean(), pa=gb.pa_ha.sum() / area * 100,
                                                         res=gb.res_ha.sum() / area * 100)
SHARES = ("touch", "pa", "res")
panels = [
    ("road_km", "Median distance to closest road", "Distance (km)"),
    ("river_km", "Median distance to closest river", "Distance (km)"),
    ("touch", "Patches touching an earlier clearing", "Share of patches (%)"),
    ("slope", "Median patch slope", "Slope (degrees)"),
    ("pa", "Loss inside or touching a protected area", "Share of loss area (%)"),
    ("res", "Loss inside or touching an Indigenous resguardo", "Share of loss area (%)"),
]

fig, axes = plt.subplots(3, 2, figsize=(8, 8), sharex=True)
for ax, (col, title, ylabel) in zip(axes.flat, panels):
    s = g[col].unstack("treated")
    for grp in (1, 0):
        ax.plot(s.index, s[grp], color=ps.GROUP_COLOR[grp], marker="o", markersize=3.5, label=ps.GROUP_LABEL[grp])
    ps.ceasefire(ax, label=ax is axes.flat[0])
    ax.set_title(title, fontsize=9)
    ax.set_ylabel(ylabel)
    ax.set_ylim(0, s.max().max() * 1.15)
    if col in SHARES:
        ax.yaxis.set_major_formatter(PercentFormatter(decimals=0))
    ps.year_axis(ax, lr.FIRST_YEAR, lr.LAST_YEAR, label_every=3)
for ax in axes[-1]:
    ax.set_xlabel("Year")
# same units side by side (distances, area shares): one y range per row
for row in (axes[0], axes[2]):
    top = max(ax.get_ylim()[1] for ax in row)
    for ax in row:
        ax.set_ylim(0, top)
handles, labels = axes.flat[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="lower center", ncol=2, fontsize=8, bbox_to_anchor=(0.5, -0.03))
fig.tight_layout(rect=(0, 0.04, 1, 1))
fig.align_ylabels(axes[:, 0])
fig.align_ylabels(axes[:, 1])
ps.save(fig, OUT)
print(g.unstack("treated").round(2).T.to_string())
