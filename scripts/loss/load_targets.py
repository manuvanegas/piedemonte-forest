"""
Load target layers for patch distances into PostGIS (EPSG:9377), each replacing its own tables.

--runap  protected areas, whole country, so a patch's nearest area can lie outside the study area
         (A6). runap_sub splits each area into pieces of at most 256 vertices (A7).

In:  data.nosync/raw/runap/runap_latest.zip
Out: tables runap, runap_sub

Usage: python scripts/loss/load_targets.py --runap
"""
import argparse

import geopandas as gpd
from sqlalchemy import text

import db

CRS = 9377
MAX_VERTICES = 256

parser = argparse.ArgumentParser(description="Load target layers into PostGIS.")
parser.add_argument("--runap", action="store_true", help="protected areas (RUNAP)")
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


if args.runap:
    r = gpd.read_file("zip://data.nosync/raw/runap/runap_latest.zip!runap.shp")
    r = r[["ap_id", "ap_nombre", "ap_categor", "fecha_insc", "geometry"]].to_crs(CRS)
    r.to_postgis("runap", engine, if_exists="replace", index=False)
    with engine.begin() as con:
        n_invalid = con.execute(text("SELECT count(*) FROM runap WHERE NOT ST_IsValid(geometry)")).scalar()
    print(f"runap: {len(r):,} areas ({subdivide('runap', 'ap_id'):,} pieces), {n_invalid} invalid geometries")
