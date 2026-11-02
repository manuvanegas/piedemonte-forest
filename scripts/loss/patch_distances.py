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
