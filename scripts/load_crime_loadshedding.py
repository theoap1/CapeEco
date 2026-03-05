#!/usr/bin/env python3
"""
Siteline — Crime & Load Shedding Data Loader

Loads:
1. SAPS police station boundaries (GeoJSON polygons → police_stations)
2. SAPS crime statistics (CSV → crime_stats)
3. CoCT load shedding blocks (GeoJSON polygons → loadshedding_blocks)

Usage:
    python3 scripts/load_crime_loadshedding.py --step all
    python3 scripts/load_crime_loadshedding.py --step stations
    python3 scripts/load_crime_loadshedding.py --step crime
    python3 scripts/load_crime_loadshedding.py --step loadshedding
"""

import argparse
import csv
import json
import logging
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_NAME = os.environ.get("PGDATABASE", "capeeco")
DB_USER = os.environ.get("PGUSER", os.environ.get("USER", "postgres"))
DB_HOST = os.environ.get("PGHOST", "localhost")
DB_PORT = os.environ.get("PGPORT", "5432")
DB_PASSWORD = os.environ.get("PGPASSWORD", "")
SCHEMA = os.environ.get("SITELINE_SCHEMA", "capeeco")

DATA_DIR = Path(__file__).parent.parent / "data" / "raw"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def get_engine():
    if DB_PASSWORD:
        url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    else:
        url = f"postgresql://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(url, pool_size=5, max_overflow=10, pool_pre_ping=True)


# =============================================================================
# STEP 1: Load SAPS station boundaries
# =============================================================================

def load_stations(engine):
    """Load SAPS police station boundary polygons into police_stations table."""
    geojson_path = DATA_DIR / "saps_boundaries.geojson"
    if not geojson_path.exists():
        log.error("Missing %s", geojson_path)
        return

    log.info("Loading SAPS station boundaries from %s", geojson_path)

    with open(geojson_path) as f:
        data = json.load(f)

    features = data.get("features", [])
    log.info("Found %d station boundary features", len(features))

    with engine.connect() as conn:
        # Create table
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.police_stations (
                id          BIGSERIAL PRIMARY KEY,
                station_name VARCHAR(200) NOT NULL,
                province    VARCHAR(100),
                geom        geometry(Geometry, 4326) NOT NULL,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.execute(text(f"TRUNCATE {SCHEMA}.police_stations RESTART IDENTITY CASCADE"))
        conn.commit()

        inserted = 0
        for feat in features:
            props = feat.get("properties", {})
            geom = feat.get("geometry")
            if not geom:
                continue

            station_name = props.get("COMPNT_NM", "").strip()
            if not station_name:
                continue

            geom_json = json.dumps(geom)

            conn.execute(text(f"""
                INSERT INTO {SCHEMA}.police_stations (station_name, geom)
                VALUES (:name, ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326))
            """), {"name": station_name, "geom": geom_json})
            inserted += 1

            if inserted % 200 == 0:
                log.info("  Inserted %d stations...", inserted)

        # Create spatial index
        conn.execute(text(f"""
            CREATE INDEX IF NOT EXISTS idx_police_stations_geom
            ON {SCHEMA}.police_stations USING GIST (geom)
        """))
        conn.execute(text(f"""
            CREATE INDEX IF NOT EXISTS idx_police_stations_name
            ON {SCHEMA}.police_stations (station_name)
        """))
        conn.commit()

    log.info("Loaded %d police station boundaries", inserted)

    # Try to assign provinces from station coordinates CSV
    _assign_provinces(engine)


def _assign_provinces(engine):
    """Assign provinces to stations using the station coordinates CSV."""
    coords_path = DATA_DIR / "saps_station_coordinates.csv"
    if not coords_path.exists():
        log.info("No station coordinates CSV found, skipping province assignment")
        return

    # Build station→province mapping from the crime stats CSV
    crime_csv = DATA_DIR / "saps_crime_stats_wc.csv"
    if not crime_csv.exists():
        # Try the full XLSX-extracted CSV
        log.info("No crime stats CSV for province mapping, using boundary names only")
        return

    # Read province mapping from crime stats
    station_provinces = {}
    with open(crime_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            station_provinces[row["station_name"].upper()] = row["province"]

    # Also read from the original small CSV if available
    small_csv = DATA_DIR / "saps_crime_stats.csv"
    if small_csv.exists():
        with open(small_csv) as f:
            reader = csv.DictReader(f)
            for row in reader:
                station_provinces[row["Police Station"].upper()] = row["Province"]

    if not station_provinces:
        return

    with engine.connect() as conn:
        for name, province in station_provinces.items():
            conn.execute(text(f"""
                UPDATE {SCHEMA}.police_stations
                SET province = :prov
                WHERE UPPER(station_name) = :name AND province IS NULL
            """), {"prov": province, "name": name})
        conn.commit()

    log.info("Assigned provinces to stations from crime stats data")


# =============================================================================
# STEP 2: Load crime statistics
# =============================================================================

def load_crime_stats(engine):
    """Load SAPS crime statistics into crime_stats table."""
    csv_path = DATA_DIR / "saps_crime_stats_wc.csv"
    if not csv_path.exists():
        log.error("Missing %s — run XLSX extraction first", csv_path)
        return

    log.info("Loading crime statistics from %s", csv_path)

    with engine.connect() as conn:
        # Create table
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.crime_stats (
                id          BIGSERIAL PRIMARY KEY,
                station_id  BIGINT REFERENCES {SCHEMA}.police_stations(id),
                station_name VARCHAR(200) NOT NULL,
                category    VARCHAR(200) NOT NULL,
                year        VARCHAR(20) NOT NULL,
                count       INTEGER NOT NULL DEFAULT 0,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.execute(text(f"TRUNCATE {SCHEMA}.crime_stats RESTART IDENTITY"))
        conn.commit()

        # Build station name → id mapping
        rows = conn.execute(text(f"""
            SELECT id, UPPER(station_name) as name FROM {SCHEMA}.police_stations
        """)).fetchall()
        station_map = {r[1]: r[0] for r in rows}

        with open(csv_path) as f:
            reader = csv.DictReader(f)
            inserted = 0
            batch = []

            for row in reader:
                station_name = row["station_name"]
                station_id = station_map.get(station_name.upper())
                category = row["category"]
                year = row["year"]
                count = int(row["count"])

                batch.append({
                    "sid": station_id,
                    "name": station_name,
                    "cat": category,
                    "yr": year,
                    "cnt": count,
                })

                if len(batch) >= 1000:
                    _insert_crime_batch(conn, batch)
                    inserted += len(batch)
                    batch = []

            if batch:
                _insert_crime_batch(conn, batch)
                inserted += len(batch)

        # Create indexes
        conn.execute(text(f"""
            CREATE INDEX IF NOT EXISTS idx_crime_stats_station
            ON {SCHEMA}.crime_stats (station_id)
        """))
        conn.execute(text(f"""
            CREATE INDEX IF NOT EXISTS idx_crime_stats_name
            ON {SCHEMA}.crime_stats (station_name)
        """))
        conn.execute(text(f"""
            CREATE INDEX IF NOT EXISTS idx_crime_stats_year
            ON {SCHEMA}.crime_stats (year)
        """))
        conn.commit()

    log.info("Loaded %d crime stat records", inserted)


def _insert_crime_batch(conn, batch):
    for row in batch:
        conn.execute(text(f"""
            INSERT INTO {SCHEMA}.crime_stats (station_id, station_name, category, year, count)
            VALUES (:sid, :name, :cat, :yr, :cnt)
        """), row)
    conn.commit()


# =============================================================================
# STEP 3: Load loadshedding blocks
# =============================================================================

def load_loadshedding(engine):
    """Load CoCT load shedding block boundaries into loadshedding_blocks table."""
    geojson_path = DATA_DIR / "cct_loadshedding_blocks.geojson"
    if not geojson_path.exists():
        log.error("Missing %s", geojson_path)
        return

    log.info("Loading load shedding blocks from %s", geojson_path)

    with open(geojson_path) as f:
        data = json.load(f)

    features = data.get("features", [])
    log.info("Found %d load shedding block features", len(features))

    with engine.connect() as conn:
        # Create table
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.loadshedding_blocks (
                id              BIGSERIAL PRIMARY KEY,
                block_number    INTEGER NOT NULL,
                block_name      VARCHAR(50),
                area_sqm        DOUBLE PRECISION,
                geom            geometry(Geometry, 4326) NOT NULL,
                created_at      TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.execute(text(f"TRUNCATE {SCHEMA}.loadshedding_blocks RESTART IDENTITY"))
        conn.commit()

        inserted = 0
        for feat in features:
            props = feat.get("properties", {})
            geom = feat.get("geometry")
            if not geom:
                continue

            block_id = props.get("BlockID")
            if block_id is None:
                continue

            geom_json = json.dumps(geom)
            area = props.get("Shape__Area")

            conn.execute(text(f"""
                INSERT INTO {SCHEMA}.loadshedding_blocks (block_number, block_name, area_sqm, geom)
                VALUES (:num, :name, :area, ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326))
            """), {
                "num": int(block_id),
                "name": f"Block {block_id}",
                "area": area,
                "geom": geom_json,
            })
            inserted += 1

        # Create spatial index
        conn.execute(text(f"""
            CREATE INDEX IF NOT EXISTS idx_loadshedding_geom
            ON {SCHEMA}.loadshedding_blocks USING GIST (geom)
        """))
        conn.execute(text(f"""
            CREATE INDEX IF NOT EXISTS idx_loadshedding_block
            ON {SCHEMA}.loadshedding_blocks (block_number)
        """))
        conn.commit()

    log.info("Loaded %d load shedding blocks", inserted)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Load crime & load shedding data")
    parser.add_argument("--step", choices=["all", "stations", "crime", "loadshedding"],
                        default="all", help="Which step to run")
    args = parser.parse_args()

    engine = get_engine()

    # Ensure schema exists
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
        conn.commit()

    if args.step in ("all", "stations"):
        load_stations(engine)

    if args.step in ("all", "crime"):
        load_crime_stats(engine)

    if args.step in ("all", "loadshedding"):
        load_loadshedding(engine)

    log.info("Done!")


if __name__ == "__main__":
    main()
