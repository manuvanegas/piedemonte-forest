"""
Summaries of the patch table (patch_table.py) for the loss tables and figures.
"""
import pandas as pd

PRE = (2008, 2014)  # last pre-ceasefire year 2014
POST = (2015, 2023)
DID_METRICS = ["road_km", "river_km", "earlier_touch", "slope_deg", "old_growth_share", "pa_share", "res_share"]
DID_GROUPS = ["treated", "control", "treated - control"]


def did_table(t: pd.DataFrame, pre=PRE, post=POST) -> pd.DataFrame:
    """
    Before/after × with/without pre-ceasefire armed-group presence, for seven metrics.

    t     patch table with loss_year, treated (0/1), area_ha, secondary_share, road_dist_m, river_dist_m,
          earlier_dist_m, slope_mean_deg, in_pa, in_res
    pre   first and last loss year of the pre period, both included; post the same
          (patches outside both periods are ignored)
    Metrics, per group and period:
      road_km        median distance to road over patches (each patch counts once), in km
      river_km       median distance to river over patches, in km
      earlier_touch  share of patches touching an earlier clearing (earlier_dist_m == 0), each patch once
      slope_deg      median over patches of the patch mean slope (slope_mean_deg), in degrees
      old_growth_share  old-growth share of loss area: sum(area_ha * (1 - secondary_share)) / sum(area_ha)
      pa_share       share of loss area in patches inside or touching a protected area (in_pa)
      res_share      share of loss area in patches inside or touching a resguardo (in_res)
    Returns a DataFrame:
      index    MultiIndex (metric, group), metrics in the order above, groups "treated", "control",
               "treated - control"
      columns  "pre", "post", "post - pre"
    The ("treated - control", "post - pre") cell of each metric is the difference in differences.
    """
    t = t.assign(period=None)  # a copy: the caller's table is left as is
    t.loc[t.loss_year.between(*pre), "period"] = "pre"
    t.loc[t.loss_year.between(*post), "period"] = "post"
    t = t[t.period.notna()].assign(
        touch=t.earlier_dist_m == 0,
        old_growth_ha=t.area_ha * (1 - t.secondary_share),
        pa_ha=t.area_ha * t.in_pa,
        res_ha=t.area_ha * t.in_res,
    )

    g = t.groupby(["period", "treated"]).agg(
        road_km=("road_dist_m", "median"),
        river_km=("river_dist_m", "median"),
        earlier_touch=("touch", "mean"),
        slope_deg=("slope_mean_deg", "median"),
        area_ha=("area_ha", "sum"),
        old_growth_ha=("old_growth_ha", "sum"),
        pa_ha=("pa_ha", "sum"),
        res_ha=("res_ha", "sum"),
    )
    g[["road_km", "river_km"]] /= 1000
    for share, ha in [("old_growth_share", "old_growth_ha"), ("pa_share", "pa_ha"), ("res_share", "res_ha")]:
        g[share] = g[ha] / g.area_ha

    # differences are column minus column: put groups in the columns, then periods
    w = g[DID_METRICS].stack().rename_axis(["period", "group", "metric"]).unstack("group")
    w = w.rename(columns={1: "treated", 0: "control"})
    w["treated - control"] = w.treated - w.control
    wide = w.stack().unstack("period")
    wide["post - pre"] = wide.post - wide.pre

    order = pd.MultiIndex.from_product([DID_METRICS, DID_GROUPS], names=["metric", "group"])
    return wide.reorder_levels(["metric", "group"]).reindex(order)[["pre", "post", "post - pre"]]
