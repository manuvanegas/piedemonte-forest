"""
PostGIS connection from DATABASE_URL in .env.
"""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine


def engine():
    load_dotenv(".env")
    # SQLAlchemy 2.1 defaults to psycopg 3; the env has psycopg2
    return create_engine(os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+psycopg2://", 1))
