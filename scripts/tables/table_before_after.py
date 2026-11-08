"""
Table: seven patch metrics before (2008-2014) and after (2015-2023) the ceasefire, with and without
pre-ceasefire armed-group presence, and the change in the gap between groups (did_table in summaries.py).
Distances in km, slope in degrees, shares as fractions (of patches for earlier clearings, of loss area
otherwise).

In:  patch table (patch_table.py)
Out: results/loss/before_after.csv

Usage: python scripts/tables/table_before_after.py
"""
from pathlib import Path

from piedemonte_forest.patch_table import patch_table
from piedemonte_forest.summaries import did_table

OUT = Path("results/loss/before_after.csv")

tab = did_table(patch_table())
OUT.parent.mkdir(parents=True, exist_ok=True)
tab.round(4).to_csv(OUT)
print(tab.round(3).to_string())
