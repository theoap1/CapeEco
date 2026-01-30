#!/usr/bin/env python3
"""
CapeEco Database Seeder

Ensures PostGIS extensions exist, schema is applied, and seeds lookup/sample
data for smoke testing. Safe to run multiple times (idempotent).

Usage:
    python scripts/seed_data.py                    # default local DB
    DATABASE_URL=postgresql://... python scripts/seed_data.py
"""
import json
import logging
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

DB_URL = os.environ.get(
    "DATABASE_URL",
    f"postgresql://{os.environ.get('PGUSER', os.environ.get('USER', 'postgres'))}@localhost:5432/capeeco",
)

SCHEMA = "capeeco"
ROOT = Path(__file__).resolve().parent.parent


def get_engine():
    return create_engine(DB_URL, pool_pre_ping=True)


def ensure_postgis(conn):
    """Check and create PostGIS extension if missing."""
    result = conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'postgis'")).fetchone()
    if result:
        log.info("PostGIS extension: OK")
    else:
        log.info("Creating PostGIS extension...")
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis_topology"))
        conn.commit()
        log.info("PostGIS extension: created")


def ensure_schema(conn):
    """Check if capeeco schema exists, apply schema.sql if not."""
    result = conn.execute(text(
        "SELECT 1 FROM information_schema.schemata WHERE schema_name = :s"
    ), {"s": SCHEMA}).fetchone()
    if result:
        log.info("Schema '%s': exists", SCHEMA)
        return
    log.info("Applying schema from scripts/schema.sql...")
    schema_sql = (ROOT / "scripts" / "schema.sql").read_text()
    for stmt in schema_sql.split(";"):
        stmt = stmt.strip()
        if stmt and not stmt.startswith("--"):
            conn.execute(text(stmt))
    conn.commit()
    log.info("Schema applied")


def seed_offset_rules(conn):
    """Load offset_rules.json into a lookup table if not already present."""
    rules_path = ROOT / "data" / "processed" / "offset_rules.json"
    if not rules_path.exists():
        log.warning("offset_rules.json not found at %s — skipping", rules_path)
        return
    # The offset rules are read directly by biodiversity_engine.py from JSON,
    # so no DB table needed. Just verify the file is accessible.
    rules = json.loads(rules_path.read_text())
    log.info("offset_rules.json: loaded (%d CBA categories)", len(rules.get("cba_ratios", {})))


def seed_sample_properties(conn):
    """Insert a small set of sample properties for smoke testing if table is empty."""
    count = conn.execute(text(f"SELECT COUNT(*) FROM {SCHEMA}.properties")).scalar()
    if count > 0:
        log.info("Properties table: %d rows (skipping sample seed)", count)
        return

    log.info("Inserting sample test properties...")
    # These are representative Cape Town erven for smoke testing
    samples = [
        ("901", "BANTRY BAY", -33.9250, 18.3800, 500.0),
        ("1234", "CAMPS BAY", -33.9500, 18.3700, 800.0),
        ("5678", "WOODSTOCK", -33.9280, 18.4500, 350.0),
        ("100", "KIRSTENBOSCH", -33.9870, 18.4320, 2000.0),
        ("200", "MUIZENBERG", -34.1030, 18.4700, 600.0),
    ]
    for erf, suburb, lat, lon, area in samples:
        conn.execute(text(f"""
            INSERT INTO {SCHEMA}.properties (sg26_code, erf_number, suburb, centroid_lat, centroid_lon, area_sqm, area_ha, geom)
            VALUES (
                :sg26, :erf, :suburb, :lat, :lon, :area, :area_ha,
                ST_Multi(ST_Buffer(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius)::geometry)
            )
            ON CONFLICT (sg26_code) DO NOTHING
        """), {
            "sg26": f"SAMPLE-{erf}-{suburb[:4]}",
            "erf": erf, "suburb": suburb, "lat": lat, "lon": lon,
            "area": area, "area_ha": area / 10000,
            "radius": (area ** 0.5) / 2,  # approximate square side / 2
        })
    conn.commit()
    log.info("Inserted %d sample properties", len(samples))


def main():
    log.info("Connecting to: %s", DB_URL.split("@")[-1])  # hide credentials
    engine = get_engine()
    with engine.connect() as conn:
        ensure_postgis(conn)
        ensure_schema(conn)
        seed_offset_rules(conn)
        seed_sample_properties(conn)
    log.info("Seeding complete")


if __name__ == "__main__":
    main()
