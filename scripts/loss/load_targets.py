"""
Load target layers for patch distances into PostGIS (EPSG:9377), each replacing its own tables.

Each layer is cut to TARGET_BUFFER around the study area (A8): a feature farther out can't be the
nearest one for a patch closer than that to some feature.
--runap  protected areas (A6); runap_sub splits each area into pieces of at most 256 vertices (A7)
--roads  GRIP4 roads (A5); roads_sub as for runap

In:  data.nosync/raw/runap/runap_latest.zip, data.nosync/raw/grip4/GRIP4_Region2_vector_shp.zip
Out: tables runap, runap_sub, roads, roads_sub

Usage: python scripts/loss/load_targets.py [--runap] [--roads]
"""
import argparse

import geopandas as gpd
from sqlalchemy import text

import db
from patch_distances import TARGET_BUFFER

CRS = 9377
MAX_VERTICES = 256

parser = argparse.ArgumentParser(description="Load target layers into PostGIS.")
parser.add_argument("--runap", action="store_true", help="protected areas (RUNAP)")
parser.add_argument("--roads", action="store_true", help="roads (GRIP4)")
args = parser.parse_args()
if not any(vars(args).values()):
    parser.error("say which layers to load, e.g. --runap")
engine = db.engine()


def subdivide(table, id_col):
    with engine.begin() as con:
        con.execute(text(f"""
            DROP TABLE IF EXISTS {table}_sub;
            CREATE TABLE {table}_sub AS SELECT {id_col}, ST_Subdivide(geometry, {MAX_VERTICES}) AS geometry FROM {table};
            CREATE INDEX ON {table}_sub USING gist (geometry);
            ANALYZE {table}; ANALYZE {table}_sub"""))
        return con.execute(text(f"SELECT count(*) FROM {table}_sub")).scalar()


area = gpd.read_parquet("data.nosync/processed/study_area.parquet").buffer(TARGET_BUFFER)

if args.runap:
    r = gpd.read_file("zip://data.nosync/raw/runap/runap_latest.zip!runap.shp")
    r = r[["ap_id", "ap_nombre", "ap_categor", "fecha_insc", "geometry"]].to_crs(CRS)
    r = r[r.intersects(area.iloc[0])]
    r.to_postgis("runap", engine, if_exists="replace", index=False)
    with engine.begin() as con:
        n_invalid = con.execute(text("SELECT count(*) FROM runap WHERE NOT ST_IsValid(geometry)")).scalar()
    print(f"runap: {len(r):,} areas within {TARGET_BUFFER / 1e3:.0f} km ({subdivide('runap', 'ap_id'):,} pieces), "
          f"{n_invalid} invalid geometries")

if args.roads:
    g = gpd.read_file("zip://data.nosync/raw/grip4/GRIP4_Region2_vector_shp.zip!GRIP4_region2.shp",
                      bbox=tuple(area.to_crs(4326).total_bounds), columns=["GP_RTP"])
    g = g.to_crs(CRS)
    g = g[g.intersects(area.iloc[0])].reset_index(drop=True)
    g = g.rename(columns={"GP_RTP": "road_type"}).rename_axis("road_id").reset_index()
    g.to_postgis("roads", engine, if_exists="replace", index=False)
    print(f"roads: {len(g):,} lines within {TARGET_BUFFER / 1e3:.0f} km ({subdivide('roads', 'road_id'):,} pieces)")
