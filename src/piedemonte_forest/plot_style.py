"""
Shared look of the result figures: group colours, the ceasefire marker, saving.
"""
from pathlib import Path

import matplotlib.pyplot as plt

# treated as in figures/inputs/treatment.png; pair checked for colour-blind separation
GROUP_COLOR = {1: "#A85A43", 0: "#1F6F86"}
GROUP_LABEL = {1: "Pre-ceasefire armed-group presence", 0: "No pre-ceasefire armed-group presence"}
INK, MUTED, GRID = "#222222", "#6b6b6b", "#e6e6e6"

plt.rcParams.update({
    "font.size": 9, "axes.titlesize": 10, "axes.titlelocation": "left", "axes.edgecolor": MUTED,
    "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID,
    "grid.linewidth": 0.8, "lines.linewidth": 2, "legend.frameon": False,
})


def ceasefire(ax, label=True):
    """Dashed line between 2014 (last pre-ceasefire year) and 2015: each point is a whole year."""
    ax.axvline(2014.5, color=MUTED, linestyle="--", linewidth=1, zorder=0)
    if label:
        ax.annotate("ceasefire (Dec 2014)", (2014.5, 1), xycoords=("data", "axes fraction"), xytext=(4, -2),
                    textcoords="offset points", va="top", color=MUTED, fontsize=8)


def year_axis(ax, first, last, label_every=1):
    """A tick for every year; labels every label_every years."""
    ax.set_xticks(range(first, last + 1))
    ax.set_xticklabels([str(y) if (y - first) % label_every == 0 else "" for y in range(first, last + 1)])
    ax.set_xlim(first - 0.5, last + 0.5)


def save(fig, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("saved", path)
