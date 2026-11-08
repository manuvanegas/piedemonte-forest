"""
Figure: agreement between MapBiomas and GFC loss of old-growth forest (D12) by year and pre-ceasefire
armed-group presence (check_gfc_agreement.py). Top: share of MapBiomas old-growth loss that GFC flags within a
year; bottom: share of GFC loss inside MapBiomas old-growth forest that MapBiomas flags within a year.
Secondary forest is left out: GFC keeps only the first loss after 2000 in each pixel, so it cannot record
regrowth cleared again after an earlier recorded loss, and the two products can't be compared on it. Solid: same
pixel; dashed: same pixel or one of its eight neighbours. In the bottom row 2023 is a hollow marker: MapBiomas
loss for 2024 needs the 2025 map (D9), so GFC's 2023 loss is matched against 2022-2023 only.

In:  results/loss/gfc_agreement.csv, treatment.parquet
Out: figures/loss/gfc_agreement.png

Usage: python scripts/figures/plot_gfc_agreement.py
"""
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.ticker import PercentFormatter

from piedemonte_forest import loss_rule as lr
from piedemonte_forest import plot_style as ps

OUT = "figures/loss/gfc_agreement.png"

d = (pd.read_csv("results/loss/gfc_agreement.csv")
     .merge(pd.read_parquet("data.nosync/processed/treatment.parquet")[["ADM2_PCODE", "treated"]],
            on="ADM2_PCODE", validate="many_to_one")
     .groupby(["year", "treated"]).sum(numeric_only=True))
# last year with a full t-1..t+1 window on the other product
rows = [("mb", "MapBiomas loss\nflagged by GFC (%)", lr.LAST_YEAR),
        ("h", "GFC loss\nflagged by MapBiomas (%)", lr.LAST_YEAR - 1)]

FTYPE = "old_growth"
fig, axes = plt.subplots(2, 1, figsize=(5.2, 6), sharex=True, sharey=True)
for (src, ylabel, last), ax in zip(rows, axes):
    ax.set_ylabel(ylabel)
    for grp in (1, 0):
        g = d.xs(grp, level="treated")
        for rule, style in (("same", "-"), ("near", (0, (4, 2)))):
            share = g[f"{src}_{rule}_{FTYPE}"] / g[f"{src}_total_{FTYPE}"] * 100
            ms = 3.5 if rule == "same" else 2.1
            ax.plot(share.loc[:last].index, share.loc[:last], color=ps.GROUP_COLOR[grp], linestyle=style,
                    marker="o", markersize=ms, linewidth=2 if rule == "same" else 1.4)
            if last < lr.LAST_YEAR:  # incomplete window: hollow, joined by a faint line of the same style
                tail = share.loc[last:]
                ax.plot(tail.index, tail, color=ps.GROUP_COLOR[grp], linestyle=style, alpha=0.35,
                        linewidth=2 if rule == "same" else 1.4)
                ax.plot(tail.index[1:], tail.iloc[1:], linestyle="none", marker="o", markersize=ms + 1,
                        markerfacecolor="white", markeredgecolor=ps.GROUP_COLOR[grp])
    ps.ceasefire(ax, label=ax is axes[0])
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(PercentFormatter(decimals=0))
axes[0].set_title("Old-growth forest", fontsize=9, loc="left")
for ax in axes:
    ps.year_axis(ax, 2013, lr.LAST_YEAR, label_every=2)
axes[1].set_xlabel("Year")
handles = [Line2D([], [], color=ps.GROUP_COLOR[g], marker="o", markersize=3.5) for g in (1, 0)]
handles += [Line2D([], [], color=ps.MUTED, marker="o", markersize=3.5),
            Line2D([], [], color=ps.MUTED, linestyle=(0, (4, 2)), linewidth=1.4, marker="o", markersize=2.1),
            Line2D([], [], linestyle="none", marker="o", markersize=4.5, markerfacecolor="white",
                   markeredgecolor=ps.MUTED)]
labels = [ps.GROUP_LABEL[1], ps.GROUP_LABEL[0], "Same pixel", "Same pixel or a neighbor",
          "Incomplete year window"]
fig.legend(handles, labels, loc="lower center", ncol=2, fontsize=8, bbox_to_anchor=(0.5, -0.04))
fig.tight_layout(rect=(0, 0.11, 1, 1))
fig.align_ylabels(axes)
ps.save(fig, OUT)
