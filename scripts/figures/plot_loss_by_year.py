"""
Figure: forest loss (patches >= 2 px, D13) as a share of remaining forest (D15), by year and pre-ceasefire
armed-group presence. The two groups hold very different forest areas, so loss in year t is scaled by the
group's forest in both t-2 and t-1, the pixels the loss rule (D9) can flag in t. Solid: all loss; dotted:
loss of old-growth forest (D12), over the same denominator, so the gap between them is secondary loss.
Top: all patches. Bottom: the same loss split by patch area (D17), over the same denominator and y scale, so
the three bottom panels add up to the top one.

In:  patch table (patch_table.py), data.nosync/processed/remaining_forest.parquet, treatment.parquet
Out: figures/loss/loss_by_year.png

Usage: python scripts/figures/plot_loss_by_year.py
"""
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import pandas as pd
from matplotlib.ticker import PercentFormatter

from piedemonte_forest import loss_rule as lr
from piedemonte_forest import plot_style as ps
from piedemonte_forest.patch_table import patch_table

OUT = "figures/loss/loss_by_year.png"
SIZES = {"(b) Small patches (under 5 ha)": (0, 5), "(c) Medium patches (5–25 ha)": (5, 25),
         "(d) Large patches (over 25 ha)": (25, float("inf"))}  # area_ha, (lo, hi]

t = patch_table()
forest = (pd.read_parquet("data.nosync/processed/remaining_forest.parquet")
          .merge(pd.read_parquet("data.nosync/processed/treatment.parquet")[["ADM2_PCODE", "treated"]],
                 on="ADM2_PCODE", validate="many_to_one")
          .groupby(["loss_year", "treated"]).forest_ha.sum().unstack("treated"))
t = t.assign(old_growth_ha=t.area_ha * (1 - t.secondary_share))


def rates(s):
    g = s.groupby(["loss_year", "treated"])
    share = g.area_ha.sum().unstack("treated", fill_value=0).reindex(forest.index, fill_value=0) / forest * 100
    old_growth = g.old_growth_ha.sum().unstack("treated", fill_value=0).reindex(forest.index, fill_value=0) / forest * 100
    assert share.notna().all().all(), "remaining forest missing for some years"
    return share, old_growth


def draw(ax, share, old_growth, markersize):
    for grp in (1, 0):
        c = ps.GROUP_COLOR[grp]
        ax.plot(share.index, share[grp], color=c, marker="o", markersize=markersize, label=ps.GROUP_LABEL[grp])
        ax.plot(old_growth.index, old_growth[grp], color=c, linestyle=":", linewidth=1.4, marker="o",
                markersize=markersize * 0.6)


fig = plt.figure(figsize=(10, 7.6))
grid = fig.add_gridspec(2, 3, height_ratios=(1.6, 1))
top = fig.add_subplot(grid[0, :])
bottom = [fig.add_subplot(grid[1, i], sharey=top) for i in range(3)]

share, old_growth = rates(t)
draw(top, share, old_growth, 4)
ps.ceasefire(top)
ps.year_axis(top, lr.FIRST_YEAR, lr.LAST_YEAR, label_every=1)
top.set_title("(a) All loss patches")
top.set_ylabel("Loss (% of remaining forest)")
print(pd.concat({"all": share, "old_growth": old_growth}, axis=1).round(3).to_string())

for ax, (title, (lo, hi)) in zip(bottom, SIZES.items()):
    s_share, s_old_growth = rates(t[(t.area_ha > lo) & (t.area_ha <= hi)])
    draw(ax, s_share, s_old_growth, 3)
    ps.ceasefire(ax, label=False)
    ps.year_axis(ax, lr.FIRST_YEAR, lr.LAST_YEAR, label_every=3)
    ax.set_title(title, fontsize=9)
    ax.set_xlabel("Year")
    if ax is not bottom[0]:
        ax.tick_params(labelleft=False)
    print(title)
    print(pd.concat({"all": s_share, "old_growth": s_old_growth}, axis=1).round(3).to_string())
bottom[0].set_ylabel("Loss (% of remaining forest)")
top.set_ylim(0, None)
top.yaxis.set_major_formatter(PercentFormatter(decimals=1))

handles, labels = top.get_legend_handles_labels()
handles += [Line2D([], [], color=ps.MUTED, marker="o", markersize=4),
            Line2D([], [], color=ps.MUTED, linestyle=":", linewidth=1.4, marker="o", markersize=2.4)]
labels += ["All forest", "Old-growth forest"]
fig.legend(handles, labels, loc="lower center", ncol=2, fontsize=8, bbox_to_anchor=(0.5, -0.01))
fig.tight_layout(rect=(0, 0.07, 1, 1), h_pad=2)
ps.save(fig, OUT)
