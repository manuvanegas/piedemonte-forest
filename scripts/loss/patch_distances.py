"""
Nearest-neighbour distance from each loss patch to a target layer in PostGIS.
"""
# targets are loaded within this distance of the study area; the distance scripts check no patch is farther
TARGET_BUFFER = 200_000  # m


def nearest_sql(patches: str, target: str, target_id: str) -> str:
    """
    SQL returning one row per patch: its nearest target, by that target's ID column, and the distance to it.

    patches    table or subquery with loss_year, patch_id, geometry (EPSG:9377)
    target     table with geometry (EPSG:9377), GiST-indexed
    target_id  name of the ID column in `target` (e.g. ap_id for runap)
    Returns columns: loss_year, patch_id, target_id (always this name), dist_m (0 if touching or inside).
    """
    return f"""
    SELECT p.loss_year, p.patch_id, n.target_id, n.dist_m
    FROM {patches} p
    CROSS JOIN LATERAL (
        SELECT t.{target_id} AS target_id, ST_Distance(p.geometry, t.geometry) AS dist_m
        FROM {target} t
        ORDER BY p.geometry <-> t.geometry
        LIMIT 1
    ) n
    """


def nearest_earlier_sql(year: int, window: int = 3, patches: str = "patches",
                        lookback: str = "lookback_patches") -> str:
    """
    SQL returning one row per patch of `year`: the distance to the nearest patch cleared in the `window`
    years before it, t-window to t-1 (D14). Same-year and later patches never count.

    year      loss year t of the patches measured
    window    look-back years (3)
    patches   table with loss_year, patch_id, geometry (EPSG:9377), GiST-indexed: 2008-2023
    lookback  same columns, 2005-2007 (targets only); for t <= 2010 part of the window is here
    Returns columns: loss_year, patch_id, dist_m (0 if touching).
    """
    return f"""
    SELECT p.loss_year, p.patch_id, n.dist_m
    FROM {patches} p
    CROSS JOIN LATERAL (
        SELECT ST_Distance(p.geometry, t.geometry) AS dist_m
        FROM (
            SELECT loss_year, geometry FROM {patches}
            UNION ALL
            SELECT loss_year, geometry FROM {lookback}
        ) t
        WHERE t.loss_year BETWEEN {year - window} AND {year - 1}
        ORDER BY p.geometry <-> t.geometry
        LIMIT 1
    ) n
    WHERE p.loss_year = {year}
    """