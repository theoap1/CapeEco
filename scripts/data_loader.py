#!/usr/bin/env python3
"""
Cape Town Eco-Property: Data Loader Pipeline

Loads GeoJSON datasets into PostGIS with:
- Chunked loading for large files (avoids memory bombs)
- Staging tables with validation before promotion
- Geometry reprojection (EPSG:3857 -> EPSG:4326)
- Geometry validation and repair (ST_MakeValid)
- Per-table transactions (failure in one doesn't lose others)
- Spatial index creation post-load
- Spatial intersection pipeline for property × biodiversity

Usage:
    python3 data_loader.py --step setup     # Create database + schema
    python3 data_loader.py --step load      # Load all datasets
    python3 data_loader.py --step index     # Create spatial indexes
    python3 data_loader.py --step intersect # Run spatial joins
    python3 data_loader.py --step all       # Run everything
    python3 data_loader.py --step load --table properties  # Load single table
"""

import argparse
import json
import logging
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.validation import make_valid
from shapely import wkt
from sqlalchemy import create_engine, text

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_NAME = "capeeco"
DB_USER = os.environ.get("PGUSER", os.environ.get("USER", "postgres"))
DB_HOST = os.environ.get("PGHOST", "localhost")
DB_PORT = os.environ.get("PGPORT", "5432")
DB_PASSWORD = os.environ.get("PGPASSWORD", "")
SCHEMA = "capeeco"

DATA_DIR = Path("/Users/theoapteker/Documents/CapeEco/data/raw")
SCRIPTS_DIR = Path("/Users/theoapteker/Documents/CapeEco/scripts")

# Source CRS for all CCT data (verified from metadata)
SOURCE_CRS = "EPSG:4326"  # GeoJSON spec mandates WGS84; ArcGIS portal reprojects on export
TARGET_CRS = "EPSG:4326"

# Chunk sizes tuned per dataset based on actual file sizes
CHUNK_SIZES = {
    "properties": 10_000,       # 786MB, ~400k features → 40 chunks
    "address_points": 25_000,   # 350MB, ~700k features → 28 chunks
    "zoning_overlays": 10_000,  # 642MB, large polygons
    "biodiversity_areas": 2_000, # 90MB, ~5k features, complex polygons
    "heritage_sites": 5_000,    # 130MB, 38 fields
    "ecosystem_types": 1_000,   # 31MB
    "default": 5_000,
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(SCRIPTS_DIR / "data_loader.log"),
    ],
)
log = logging.getLogger(__name__)


# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_connection_string(dbname=None):
    """Build SQLAlchemy connection string."""
    db = dbname or DB_NAME
    if DB_PASSWORD:
        return f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{db}"
    return f"postgresql://{DB_USER}@{DB_HOST}:{DB_PORT}/{db}"


def get_engine(dbname=None):
    """Create SQLAlchemy engine with connection pooling."""
    return create_engine(
        get_connection_string(dbname),
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )


@contextmanager
def db_transaction(engine):
    """Context manager for a database transaction with rollback on error."""
    conn = engine.connect()
    trans = conn.begin()
    try:
        yield conn
        trans.commit()
    except Exception:
        trans.rollback()
        raise
    finally:
        conn.close()


# =============================================================================
# STEP 1: DATABASE SETUP
# =============================================================================

def setup_database():
    """Create the database and apply schema."""
    log.info("=== STEP 1: DATABASE SETUP ===")

    # Connect to default 'postgres' database to create our DB
    default_engine = get_engine("postgres")

    with default_engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        # Check if database exists
        result = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
            {"dbname": DB_NAME},
        )
        if result.fetchone():
            log.info(f"Database '{DB_NAME}' already exists")
        else:
            conn.execute(text(f'CREATE DATABASE "{DB_NAME}"'))
            log.info(f"Created database '{DB_NAME}'")

    default_engine.dispose()

    # Now connect to our database and apply schema
    engine = get_engine()

    with engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        # Enable PostGIS
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis_topology"))
        log.info("PostGIS extensions enabled")

    # Apply schema SQL via psql (handles multi-statement blocks correctly)
    schema_file = SCRIPTS_DIR / "schema.sql"
    import subprocess
    result = subprocess.run(
        ["psql", "-U", DB_USER, "-h", DB_HOST, "-p", str(DB_PORT),
         "-d", DB_NAME, "-f", str(schema_file), "-v", "ON_ERROR_STOP=1"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        log.error(f"Schema apply failed:\n{result.stderr}")
        raise RuntimeError("Schema apply failed")

    log.info("Schema applied successfully")
    engine.dispose()


# =============================================================================
# STEP 2: DATA LOADING
# =============================================================================

def fix_geometries(gdf):
    """Fix invalid geometries and ensure MultiPolygon type."""
    if gdf.empty:
        return gdf

    # Fix invalid geometries
    invalid_mask = ~gdf.geometry.is_valid
    n_invalid = invalid_mask.sum()
    if n_invalid > 0:
        log.info(f"  Fixing {n_invalid} invalid geometries")
        gdf.loc[invalid_mask, "geometry"] = gdf.loc[invalid_mask, "geometry"].apply(
            make_valid
        )

    # Remove null/empty geometries
    null_mask = gdf.geometry.is_empty | gdf.geometry.isna()
    n_null = null_mask.sum()
    if n_null > 0:
        log.warning(f"  Dropping {n_null} null/empty geometries")
        gdf = gdf[~null_mask].copy()

    return gdf


def promote_to_multi(gdf, target_type="MultiPolygon"):
    """Promote single geometries to multi (Polygon -> MultiPolygon, etc.)."""
    from shapely.geometry import MultiPolygon, MultiPoint, MultiLineString, mapping

    type_map = {
        "MultiPolygon": ("Polygon", MultiPolygon),
        "MultiPoint": ("Point", MultiPoint),
        "MultiLineString": ("LineString", MultiLineString),
    }

    if target_type not in type_map:
        return gdf

    single_type, multi_cls = type_map[target_type]
    needs_promotion = gdf.geometry.geom_type == single_type
    n_promote = needs_promotion.sum()

    if n_promote > 0:
        log.info(f"  Promoting {n_promote} {single_type} -> {target_type}")
        gdf.loc[needs_promotion, "geometry"] = gdf.loc[
            needs_promotion, "geometry"
        ].apply(lambda g: multi_cls([g]))

    # Handle GeometryCollections (can happen after make_valid)
    is_gc = gdf.geometry.geom_type == "GeometryCollection"
    if is_gc.sum() > 0:
        log.info(f"  Extracting {is_gc.sum()} GeometryCollections")

        def extract_from_gc(gc, target_single=single_type):
            parts = [g for g in gc.geoms if g.geom_type in (single_type, target_type)]
            if not parts:
                return None
            all_singles = []
            for p in parts:
                if p.geom_type == target_type:
                    all_singles.extend(list(p.geoms))
                else:
                    all_singles.append(p)
            return multi_cls(all_singles) if all_singles else None

        gdf.loc[is_gc, "geometry"] = gdf.loc[is_gc, "geometry"].apply(extract_from_gc)
        # Drop any that couldn't be converted
        gdf = gdf.dropna(subset=["geometry"])

    return gdf


def load_geojson_chunked(filepath, chunk_size, process_func=None):
    """
    Load a large GeoJSON file in chunks using ijson streaming parser.
    Returns an iterator of GeoDataFrames.
    """
    import ijson

    filepath = str(filepath)
    log.info(f"  Streaming {filepath} in chunks of {chunk_size}")

    features_batch = []
    total = 0

    with open(filepath, "rb") as f:
        for feature in ijson.items(f, "features.item"):
            # Convert Decimal types to float (ijson returns Decimals)
            props = {}
            for k, v in feature.get("properties", {}).items():
                if hasattr(v, "as_integer_ratio"):  # Decimal
                    props[k] = float(v)
                else:
                    props[k] = v

            features_batch.append({
                "type": "Feature",
                "geometry": feature.get("geometry"),
                "properties": props,
            })

            if len(features_batch) >= chunk_size:
                total += len(features_batch)
                gdf = gpd.GeoDataFrame.from_features(features_batch, crs=SOURCE_CRS)
                if process_func:
                    gdf = process_func(gdf)
                yield gdf
                features_batch = []
                log.info(f"    Processed {total} features so far...")

    # Final batch
    if features_batch:
        total += len(features_batch)
        gdf = gpd.GeoDataFrame.from_features(features_batch, crs=SOURCE_CRS)
        if process_func:
            gdf = process_func(gdf)
        yield gdf

    log.info(f"  Total features: {total}")


def reproject_gdf(gdf):
    """Reproject from source CRS to target CRS."""
    if gdf.crs and gdf.crs != TARGET_CRS:
        return gdf.to_crs(TARGET_CRS)
    return gdf


def rename_geom_column(gdf):
    """Rename geometry column from 'geometry' to 'geom' to match DB schema."""
    if gdf.geometry.name != "geom":
        gdf = gdf.rename_geometry("geom")
    return gdf


def write_to_postgis(gdf, table_name, engine, schema=None, if_exists="append", index=False, chunksize=None):
    """Wrapper around to_postgis that ensures geom column name matches DB schema."""
    gdf = rename_geom_column(gdf)
    kwargs = {"schema": schema, "if_exists": if_exists, "index": index}
    if chunksize:
        kwargs["chunksize"] = chunksize
    gdf.to_postgis(table_name, engine, **kwargs)


# ---------------------------------------------------------------------------
# Per-table loading functions
# ---------------------------------------------------------------------------

def load_properties(engine):
    """Load land parcels into staging_properties, validate, promote."""
    log.info("--- Loading: properties (land parcels) ---")
    filepath = DATA_DIR / "cct_land_parcels_2025.geojson"
    if not filepath.exists():
        log.error(f"File not found: {filepath}")
        return

    chunk_size = CHUNK_SIZES["properties"]
    total_loaded = 0

    # Truncate staging table
    with db_transaction(engine) as conn:
        conn.execute(text(f"TRUNCATE {SCHEMA}.staging_properties"))

    def process_properties_chunk(gdf):
        # Reproject
        gdf = reproject_gdf(gdf)
        # Fix geometries
        gdf = fix_geometries(gdf)
        # Promote to MultiPolygon
        gdf = promote_to_multi(gdf, "MultiPolygon")
        return gdf

    for chunk_gdf in load_geojson_chunked(filepath, chunk_size, process_properties_chunk):
        if chunk_gdf.empty:
            continue

        # Map source columns to our schema
        df = gpd.GeoDataFrame({
            "objectid": pd.to_numeric(chunk_gdf.get("OBJECTID"), errors="coerce").astype("Int64"),
            "sg26_code": chunk_gdf.get("SG26_CODE"),
            "sl_parcel_key": pd.to_numeric(chunk_gdf.get("SL_LAND_PRCL_KEY"), errors="coerce").astype("Int64"),
            "erf_number": chunk_gdf.get("PRTY_NMBR"),
            "address_number": pd.to_numeric(chunk_gdf.get("ADR_NO"), errors="coerce").astype("Int64"),
            "address_suffix": chunk_gdf.get("ADR_NO_SFX"),
            "street_name": chunk_gdf.get("STR_NAME"),
            "street_type": chunk_gdf.get("LU_STR_NAME_TYPE"),
            "suburb": chunk_gdf.get("OFC_SBRB_NAME"),
            "alt_suburb_name": chunk_gdf.get("ALT_NAME"),
            "ward": chunk_gdf.get("WARD_NAME"),
            "subcouncil": chunk_gdf.get("SUB_CNCL_NMBR"),
            "legal_status": chunk_gdf.get("LU_LGL_STS_DSCR"),
            "zoning_raw": chunk_gdf.get("ZONING"),
            "geometry": chunk_gdf.geometry,
        }, geometry="geometry", crs=TARGET_CRS)

        # Extract primary zoning (first value from comma-separated list)
        df["zoning_primary"] = df["zoning_raw"].apply(
            lambda x: x.split(",")[0].strip() if isinstance(x, str) else None
        )

        # Build full address
        df["full_address"] = df.apply(
            lambda r: " ".join(
                filter(None, [
                    str(int(r["address_number"])) if pd.notna(r["address_number"]) else None,
                    str(r.get("address_suffix", "")).strip() or None,
                    str(r.get("street_name", "")).strip() or None,
                    str(r.get("street_type", "")).strip() or None,
                    str(r.get("suburb", "")).strip() or None,
                ])
            ) or None,
            axis=1,
        )

        # Drop rows with null sg26_code (our unique key)
        n_before = len(df)
        df = df.dropna(subset=["sg26_code"])
        if len(df) < n_before:
            log.warning(f"  Dropped {n_before - len(df)} rows with null sg26_code")

        # Write to staging table
        try:
            write_to_postgis(df, 
                "staging_properties",
                engine,
                schema=SCHEMA,
                if_exists="append",
                index=False,
                chunksize=2000,
            )
            total_loaded += len(df)
        except Exception as e:
            log.error(f"  Error writing chunk to staging: {e}")
            # Try row-by-row for this chunk to identify bad rows
            for idx in range(0, len(df), 100):
                mini = df.iloc[idx : idx + 100]
                try:
                    write_to_postgis(mini, 
                        "staging_properties", engine, schema=SCHEMA,
                        if_exists="append", index=False,
                    )
                    total_loaded += len(mini)
                except Exception as e2:
                    log.error(f"  Failed sub-chunk at row {idx}: {e2}")

    log.info(f"  Staging loaded: {total_loaded} properties")

    # Validate staging data
    with db_transaction(engine) as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM {SCHEMA}.staging_properties"))
        staging_count = result.scalar()
        log.info(f"  Staging count: {staging_count}")

        # Check for duplicate sg26_codes
        result = conn.execute(text(f"""
            SELECT sg26_code, COUNT(*) as cnt
            FROM {SCHEMA}.staging_properties
            GROUP BY sg26_code HAVING COUNT(*) > 1
            LIMIT 10
        """))
        dupes = result.fetchall()
        if dupes:
            log.warning(f"  Found {len(dupes)} duplicate sg26_codes (keeping first)")
            # Deduplicate
            conn.execute(text(f"""
                DELETE FROM {SCHEMA}.staging_properties a
                USING {SCHEMA}.staging_properties b
                WHERE a.id > b.id AND a.sg26_code = b.sg26_code
            """))

    # Promote: staging -> production
    promote_staging(engine, "staging_properties", "properties")

    # Compute derived fields (area, centroid)
    log.info("  Computing derived fields (area_sqm, centroid)...")
    with db_transaction(engine) as conn:
        conn.execute(text(f"""
            UPDATE {SCHEMA}.properties SET
                area_sqm = ST_Area(geom::geography),
                area_ha = ST_Area(geom::geography) / 10000.0,
                centroid_lon = ST_X(ST_Centroid(geom)),
                centroid_lat = ST_Y(ST_Centroid(geom))
        """))

    log.info("  Properties load complete")


def load_biodiversity(engine):
    """Load BioNet terrestrial biodiversity network."""
    log.info("--- Loading: biodiversity_areas (BioNet) ---")
    filepath = DATA_DIR / "cct_terrestrial_biodiversity_network_2025.geojson"
    if not filepath.exists():
        log.error(f"File not found: {filepath}")
        return

    chunk_size = CHUNK_SIZES["biodiversity_areas"]
    total_loaded = 0

    with db_transaction(engine) as conn:
        conn.execute(text(f"TRUNCATE {SCHEMA}.staging_biodiversity"))

    def process_bio_chunk(gdf):
        gdf = reproject_gdf(gdf)
        gdf = fix_geometries(gdf)
        gdf = promote_to_multi(gdf, "MultiPolygon")
        return gdf

    for chunk_gdf in load_geojson_chunked(filepath, chunk_size, process_bio_chunk):
        if chunk_gdf.empty:
            continue

        # Map managed field to boolean
        managed_map = {"Yes": True, "No": False}

        df = gpd.GeoDataFrame({
            "objectid": pd.to_numeric(chunk_gdf.get("OBJECTID"), errors="coerce").astype("Int64"),
            "cba_category": chunk_gdf.get("CBA_CTGR"),
            "cba_name": chunk_gdf.get("CBA_NAME"),
            "subtype": chunk_gdf.get("SBTY"),
            "sdf_category": chunk_gdf.get("SDF_CTGR"),
            "description": chunk_gdf.get("CBA_DSCR"),
            "significance": chunk_gdf.get("SGNF_HBT"),
            "objective": chunk_gdf.get("OBJC"),
            "action": chunk_gdf.get("ACTN"),
            "compatible_use": chunk_gdf.get("CMPT_ACTV"),
            "habitat_cond": chunk_gdf.get("HBT_CNDT"),
            "esa_significance": chunk_gdf.get("CESA_SGNF"),
            "protected_area": chunk_gdf.get("NAME_PRTC_AREA"),
            "proclaimed": chunk_gdf.get("PRCL"),
            "managed": chunk_gdf.get("MNGD").map(managed_map) if "MNGD" in chunk_gdf else None,
            "primary_class": chunk_gdf.get("PRMR_CLS"),
            "area_ha": chunk_gdf.get("AREA_HCTR"),
            "perimeter_m": chunk_gdf.get("PRMT_MTR"),
            "geometry": chunk_gdf.geometry,
        }, geometry="geometry", crs=TARGET_CRS)

        # Trim whitespace from string fields
        for col in df.select_dtypes(include=["object"]).columns:
            if col != "geometry":
                df[col] = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)

        try:
            write_to_postgis(df, 
                "staging_biodiversity", engine, schema=SCHEMA,
                if_exists="append", index=False, chunksize=1000,
            )
            total_loaded += len(df)
        except Exception as e:
            log.error(f"  Error: {e}")

    log.info(f"  Staging loaded: {total_loaded} biodiversity areas")
    promote_staging(engine, "staging_biodiversity", "biodiversity_areas")
    log.info("  Biodiversity load complete")


def load_ecosystem_types(engine):
    """Load SANBI ecosystem status data."""
    log.info("--- Loading: ecosystem_types (SANBI) ---")
    filepath = DATA_DIR / "cct_sanbi_ecosystem_status_2011.geojson"
    if not filepath.exists():
        log.error(f"File not found: {filepath}")
        return

    chunk_size = CHUNK_SIZES["ecosystem_types"]
    total_loaded = 0

    with db_transaction(engine) as conn:
        conn.execute(text(f"TRUNCATE {SCHEMA}.staging_ecosystem_types"))

    def process_eco_chunk(gdf):
        gdf = reproject_gdf(gdf)
        gdf = fix_geometries(gdf)
        gdf = promote_to_multi(gdf, "MultiPolygon")
        return gdf

    for chunk_gdf in load_geojson_chunked(filepath, chunk_size, process_eco_chunk):
        if chunk_gdf.empty:
            continue

        df = gpd.GeoDataFrame({
            "objectid": pd.to_numeric(chunk_gdf.get("OBJECTID"), errors="coerce").astype("Int64"),
            "vegetation_type": chunk_gdf.get("NTNL_VGTN_TYPE"),
            "vegetation_subtype": chunk_gdf.get("VGTN_SBTY"),
            "community": chunk_gdf.get("CMNT"),
            "threat_status": chunk_gdf.get("ECSY_STS_2011"),
            "area_ha": chunk_gdf.get("AREA_HCTR"),
            "perimeter_m": chunk_gdf.get("PRMT_MTR"),
            "geometry": chunk_gdf.geometry,
        }, geometry="geometry", crs=TARGET_CRS)

        try:
            write_to_postgis(df, 
                "staging_ecosystem_types", engine, schema=SCHEMA,
                if_exists="append", index=False,
            )
            total_loaded += len(df)
        except Exception as e:
            log.error(f"  Error: {e}")

    log.info(f"  Staging loaded: {total_loaded} ecosystem polygons")
    promote_staging(engine, "staging_ecosystem_types", "ecosystem_types")
    log.info("  Ecosystem types load complete")


def load_address_points(engine):
    """Load street address numbers for geocoding."""
    log.info("--- Loading: address_points ---")
    filepath = DATA_DIR / "cct_street_address_numbers_2025.geojson"
    if not filepath.exists():
        log.error(f"File not found: {filepath}")
        return

    chunk_size = CHUNK_SIZES["address_points"]
    total_loaded = 0

    with db_transaction(engine) as conn:
        conn.execute(text(f"TRUNCATE {SCHEMA}.staging_address_points"))

    def process_addr_chunk(gdf):
        gdf = reproject_gdf(gdf)
        # Points don't need make_valid or multi promotion
        # But remove nulls
        null_mask = gdf.geometry.isna()
        if null_mask.sum() > 0:
            gdf = gdf[~null_mask].copy()
        return gdf

    for chunk_gdf in load_geojson_chunked(filepath, chunk_size, process_addr_chunk):
        if chunk_gdf.empty:
            continue

        df = gpd.GeoDataFrame({
            "objectid": pd.to_numeric(chunk_gdf.get("OBJECTID"), errors="coerce").astype("Int64"),
            "address_number": pd.to_numeric(chunk_gdf.get("ADR_NO"), errors="coerce").astype("Int64"),
            "address_prefix": chunk_gdf.get("ADR_NO_PRF"),
            "address_suffix": chunk_gdf.get("ADR_NO_SFX"),
            "suburb": chunk_gdf.get("OFC_SBRB_NAME"),
            "street_name": chunk_gdf.get("STR_NAME"),
            "street_type": chunk_gdf.get("LU_STR_NAME_TYPE"),
            "full_address": chunk_gdf.get("FULL_ADR"),
            "geometry": chunk_gdf.geometry,
        }, geometry="geometry", crs=TARGET_CRS)

        try:
            write_to_postgis(df, 
                "staging_address_points", engine, schema=SCHEMA,
                if_exists="append", index=False, chunksize=5000,
            )
            total_loaded += len(df)
        except Exception as e:
            log.error(f"  Error: {e}")

    log.info(f"  Staging loaded: {total_loaded} address points")
    promote_staging(engine, "staging_address_points", "address_points")
    log.info("  Address points load complete")


def load_urban_edges(engine):
    """Load urban development edge and coastal urban edge."""
    log.info("--- Loading: urban_edges ---")

    with db_transaction(engine) as conn:
        conn.execute(text(f"TRUNCATE {SCHEMA}.urban_edges"))

    for filepath, edge_type in [
        (DATA_DIR / "cct_urban_development_edge_2025.geojson", "development"),
        (DATA_DIR / "cct_coastal_urban_edge_2025.geojson", "coastal"),
    ]:
        if not filepath.exists():
            log.warning(f"  Skipping {filepath} (not found)")
            continue

        log.info(f"  Loading {edge_type} edge from {filepath.name}")
        gdf = gpd.read_file(str(filepath))
        gdf = gdf.to_crs(TARGET_CRS)
        gdf = fix_geometries(gdf)
        gdf["edge_type"] = edge_type

        df = gpd.GeoDataFrame({
            "objectid": pd.to_numeric(gdf.get("OBJECTID"), errors="coerce").astype("Int64"),
            "edge_type": gdf["edge_type"],
            "geometry": gdf.geometry,
        }, geometry="geometry", crs=TARGET_CRS)

        write_to_postgis(df, "urban_edges", engine, schema=SCHEMA, if_exists="append", index=False)
        log.info(f"    Loaded {len(df)} {edge_type} edge features")

    log.info("  Urban edges load complete")


def load_heritage(engine):
    """Load heritage inventory and NHRA protections."""
    log.info("--- Loading: heritage_sites ---")

    with db_transaction(engine) as conn:
        conn.execute(text(f"TRUNCATE {SCHEMA}.staging_heritage"))

    total_loaded = 0

    # Heritage inventory (130MB, many fields)
    filepath = DATA_DIR / "cct_heritage_inventory_2025.geojson"
    if filepath.exists():
        chunk_size = CHUNK_SIZES["heritage_sites"]

        def process_heritage_chunk(gdf):
            gdf = reproject_gdf(gdf)
            gdf = fix_geometries(gdf)
            gdf = promote_to_multi(gdf, "MultiPolygon")
            return gdf

        for chunk_gdf in load_geojson_chunked(filepath, chunk_size, process_heritage_chunk):
            if chunk_gdf.empty:
                continue

            df = gpd.GeoDataFrame({
                "objectid": pd.to_numeric(chunk_gdf.get("OBJECTID"), errors="coerce").astype("Int64"),
                "source": "inventory",
                "site_name": chunk_gdf.get("HRTG_INV_SITE_NAME"),
                "heritage_category": pd.to_numeric(chunk_gdf.get("HRTG_INV_RCS_CAT"), errors="coerce").astype("Int64"),
                "resource_type_1": chunk_gdf.get("HRTG_INV_RCS_TYPE_1"),
                "resource_type_2": chunk_gdf.get("HRTG_INV_RCS_TYPE_2"),
                "description": chunk_gdf.get("SITE_DSRP"),
                "architectural_style": chunk_gdf.get("ARCH_STYL"),
                "period": chunk_gdf.get("PRD"),
                "nhra_status": chunk_gdf.get("NHRA_STS"),
                "city_grading": chunk_gdf.get("CNFR_CCT_GRD"),
                "street_address": chunk_gdf.get("STR_ADR"),
                "geometry": chunk_gdf.geometry,
            }, geometry="geometry", crs=TARGET_CRS)

            try:
                write_to_postgis(df, 
                    "staging_heritage", engine, schema=SCHEMA,
                    if_exists="append", index=False, chunksize=2000,
                )
                total_loaded += len(df)
            except Exception as e:
                log.error(f"  Error: {e}")

    # NHRA protections (1MB, small)
    filepath2 = DATA_DIR / "cct_nhra_protection_2025.geojson"
    if filepath2.exists():
        gdf = gpd.read_file(str(filepath2))
        gdf = gdf.to_crs(TARGET_CRS)
        gdf = fix_geometries(gdf)
        gdf = promote_to_multi(gdf, "MultiPolygon")

        df = gpd.GeoDataFrame({
            "objectid": pd.to_numeric(gdf.get("OBJECTID"), errors="coerce").astype("Int64"),
            "source": "nhra",
            "site_name": gdf.get("NHRA_NAME") if "NHRA_NAME" in gdf else None,
            "geometry": gdf.geometry,
        }, geometry="geometry", crs=TARGET_CRS)

        write_to_postgis(df, 
            "staging_heritage", engine, schema=SCHEMA,
            if_exists="append", index=False,
        )
        total_loaded += len(df)

    log.info(f"  Staging loaded: {total_loaded} heritage features")
    promote_staging(engine, "staging_heritage", "heritage_sites")
    log.info("  Heritage load complete")


def load_environmental(engine):
    """Load environmental focus areas (small dataset, direct load)."""
    log.info("--- Loading: environmental_focus_areas ---")
    filepath = DATA_DIR / "cct_environmental_focus_areas_2025.geojson"
    if not filepath.exists():
        log.warning(f"  Skipping (not found)")
        return

    gdf = gpd.read_file(str(filepath))
    gdf = gdf.to_crs(TARGET_CRS)
    gdf = fix_geometries(gdf)
    gdf = promote_to_multi(gdf, "MultiPolygon")

    df = gpd.GeoDataFrame({
        "objectid": pd.to_numeric(gdf.get("OBJECTID"), errors="coerce").astype("Int64"),
        "name": gdf.get("NAME"),
        "description": gdf.get("DSCR"),
        "area_ha": gdf.get("AREA_HCTR"),
        "geometry": gdf.geometry,
    }, geometry="geometry", crs=TARGET_CRS)

    with db_transaction(engine) as conn:
        conn.execute(text(f"TRUNCATE {SCHEMA}.environmental_focus_areas"))

    write_to_postgis(df, "environmental_focus_areas", engine, schema=SCHEMA, if_exists="append", index=False)
    log.info(f"  Loaded {len(df)} environmental focus areas")


def load_wetlands(engine):
    """Load wetlands (25MB, direct load)."""
    log.info("--- Loading: wetlands ---")
    filepath = DATA_DIR / "cct_wetlands_2025.geojson"
    if not filepath.exists():
        return

    gdf = gpd.read_file(str(filepath))
    gdf = gdf.to_crs(TARGET_CRS)
    gdf = fix_geometries(gdf)
    gdf = promote_to_multi(gdf, "MultiPolygon")

    df = gpd.GeoDataFrame({
        "objectid": pd.to_numeric(gdf.get("OBJECTID"), errors="coerce").astype("Int64"),
        "geometry": gdf.geometry,
    }, geometry="geometry", crs=TARGET_CRS)

    with db_transaction(engine) as conn:
        conn.execute(text(f"TRUNCATE {SCHEMA}.wetlands"))

    write_to_postgis(df, "wetlands", engine, schema=SCHEMA, if_exists="append", index=False)
    log.info(f"  Loaded {len(df)} wetland polygons")


# ---------------------------------------------------------------------------
# Staging promotion
# ---------------------------------------------------------------------------

def promote_staging(engine, staging_table, production_table):
    """
    Move validated data from staging to production table.
    Uses INSERT...SELECT to avoid lock contention and allow rollback.
    """
    log.info(f"  Promoting {staging_table} -> {production_table}")

    with db_transaction(engine) as conn:
        # Get column list (excluding id which is auto-generated)
        result = conn.execute(text(f"""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = '{SCHEMA}' AND table_name = '{production_table}'
            AND column_name NOT IN ('id', 'created_at')
            ORDER BY ordinal_position
        """))
        prod_cols = [row[0] for row in result]

        result = conn.execute(text(f"""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = '{SCHEMA}' AND table_name = '{staging_table}'
            AND column_name NOT IN ('id', 'created_at')
            ORDER BY ordinal_position
        """))
        staging_cols = [row[0] for row in result]

        # Use only columns that exist in both
        common_cols = [c for c in prod_cols if c in staging_cols]
        cols_str = ", ".join(common_cols)

        # Truncate production and insert from staging
        conn.execute(text(f"TRUNCATE {SCHEMA}.{production_table} CASCADE"))

        # Use ST_MakeValid as a final safety net on geometry
        geom_col = "geom" if "geom" in common_cols else None
        if geom_col:
            select_parts = []
            for c in common_cols:
                if c == "geom":
                    select_parts.append(f"ST_MakeValid({c}) AS {c}")
                else:
                    select_parts.append(c)
            select_str = ", ".join(select_parts)
        else:
            select_str = cols_str

        conn.execute(text(f"""
            INSERT INTO {SCHEMA}.{production_table} ({cols_str})
            SELECT {select_str}
            FROM {SCHEMA}.{staging_table}
            WHERE geom IS NOT NULL
        """))

        result = conn.execute(text(f"SELECT COUNT(*) FROM {SCHEMA}.{production_table}"))
        count = result.scalar()
        log.info(f"  Promoted {count} rows to {production_table}")

        # Clear staging
        conn.execute(text(f"TRUNCATE {SCHEMA}.{staging_table}"))


# =============================================================================
# STEP 3: INDEXES
# =============================================================================

def create_indexes(engine):
    """Create spatial and attribute indexes after data load."""
    log.info("=== STEP 3: CREATE INDEXES ===")

    indexes = [
        # Spatial indexes (GIST)
        f"CREATE INDEX IF NOT EXISTS idx_properties_geom ON {SCHEMA}.properties USING GIST (geom)",
        f"CREATE INDEX IF NOT EXISTS idx_biodiversity_geom ON {SCHEMA}.biodiversity_areas USING GIST (geom)",
        f"CREATE INDEX IF NOT EXISTS idx_ecosystem_geom ON {SCHEMA}.ecosystem_types USING GIST (geom)",
        f"CREATE INDEX IF NOT EXISTS idx_address_geom ON {SCHEMA}.address_points USING GIST (geom)",
        f"CREATE INDEX IF NOT EXISTS idx_heritage_geom ON {SCHEMA}.heritage_sites USING GIST (geom)",
        f"CREATE INDEX IF NOT EXISTS idx_urban_edges_geom ON {SCHEMA}.urban_edges USING GIST (geom)",
        f"CREATE INDEX IF NOT EXISTS idx_wetlands_geom ON {SCHEMA}.wetlands USING GIST (geom)",
        f"CREATE INDEX IF NOT EXISTS idx_envfocus_geom ON {SCHEMA}.environmental_focus_areas USING GIST (geom)",
        f"CREATE INDEX IF NOT EXISTS idx_prop_bio_geom ON {SCHEMA}.property_biodiversity USING BTREE (property_id)",
        f"CREATE INDEX IF NOT EXISTS idx_prop_eco_geom ON {SCHEMA}.property_ecosystems USING BTREE (property_id)",

        # Attribute indexes for common queries
        f"CREATE INDEX IF NOT EXISTS idx_properties_sg26 ON {SCHEMA}.properties (sg26_code)",
        f"CREATE INDEX IF NOT EXISTS idx_properties_suburb ON {SCHEMA}.properties (suburb)",
        f"CREATE INDEX IF NOT EXISTS idx_properties_erf ON {SCHEMA}.properties (erf_number)",
        f"CREATE INDEX IF NOT EXISTS idx_properties_zoning ON {SCHEMA}.properties (zoning_primary)",
        f"CREATE INDEX IF NOT EXISTS idx_properties_centroid ON {SCHEMA}.properties (centroid_lon, centroid_lat)",
        f"CREATE INDEX IF NOT EXISTS idx_biodiversity_cba ON {SCHEMA}.biodiversity_areas (cba_category)",
        f"CREATE INDEX IF NOT EXISTS idx_ecosystem_threat ON {SCHEMA}.ecosystem_types (threat_status)",
        f"CREATE INDEX IF NOT EXISTS idx_address_suburb ON {SCHEMA}.address_points (suburb)",
        f"CREATE INDEX IF NOT EXISTS idx_address_street ON {SCHEMA}.address_points (street_name)",
        f"CREATE INDEX IF NOT EXISTS idx_address_full ON {SCHEMA}.address_points USING GIN (to_tsvector('english', full_address))",
    ]

    for idx_sql in indexes:
        try:
            with db_transaction(engine) as conn:
                log.info(f"  {idx_sql.split('IF NOT EXISTS ')[1].split(' ON')[0]}")
                conn.execute(text(idx_sql))
        except Exception as e:
            log.warning(f"  Index warning: {e}")

    # ANALYZE for query planner
    with db_transaction(engine) as conn:
        conn.execute(text(f"ANALYZE {SCHEMA}.properties"))
        conn.execute(text(f"ANALYZE {SCHEMA}.biodiversity_areas"))
        conn.execute(text(f"ANALYZE {SCHEMA}.ecosystem_types"))
        conn.execute(text(f"ANALYZE {SCHEMA}.address_points"))

    log.info("  Indexes created and tables analyzed")


# =============================================================================
# STEP 4: SPATIAL INTERSECTIONS
# =============================================================================

def run_spatial_intersections(engine):
    """
    Compute spatial joins between properties and biodiversity/ecosystem/urban-edge layers.
    These are expensive queries — run in batches by suburb to avoid timeouts.
    """
    log.info("=== STEP 4: SPATIAL INTERSECTIONS ===")

    # 4a: Property × Biodiversity Areas
    log.info("--- 4a: Property × Biodiversity Areas ---")
    with db_transaction(engine) as conn:
        conn.execute(text(f"TRUNCATE {SCHEMA}.property_biodiversity"))
        log.info("  Running spatial intersection (this may take 10-30 minutes for ~400k properties)...")

        # Batch by suburb to avoid memory issues and allow progress tracking
        result = conn.execute(text(f"SELECT DISTINCT suburb FROM {SCHEMA}.properties ORDER BY suburb"))
        suburbs = [row[0] for row in result]
        log.info(f"  Processing {len(suburbs)} suburbs")

    total_intersections = 0
    for i, suburb in enumerate(suburbs):
        try:
            with db_transaction(engine) as conn:
                conn.execute(text(f"""
                    INSERT INTO {SCHEMA}.property_biodiversity
                        (property_id, biodiversity_area_id, cba_category, habitat_condition,
                         overlap_area_sqm, overlap_pct)
                    SELECT
                        p.id,
                        b.id,
                        b.cba_category,
                        b.habitat_cond,
                        ST_Area(ST_Intersection(p.geom, b.geom)::geography),
                        ST_Area(ST_Intersection(p.geom, b.geom)::geography) / NULLIF(p.area_sqm, 0) * 100
                    FROM {SCHEMA}.properties p
                    JOIN {SCHEMA}.biodiversity_areas b ON ST_Intersects(p.geom, b.geom)
                    WHERE p.suburb = :suburb
                    ON CONFLICT (property_id, biodiversity_area_id) DO NOTHING
                """), {"suburb": suburb})

                result = conn.execute(text(f"""
                    SELECT COUNT(*) FROM {SCHEMA}.property_biodiversity
                    WHERE property_id IN (SELECT id FROM {SCHEMA}.properties WHERE suburb = :suburb)
                """), {"suburb": suburb})
                n = result.scalar()
                total_intersections += n

            if (i + 1) % 50 == 0:
                log.info(f"    Progress: {i+1}/{len(suburbs)} suburbs, {total_intersections} intersections")
        except Exception as e:
            log.warning(f"    Error for suburb '{suburb}': {e}")

    log.info(f"  Total property-biodiversity intersections: {total_intersections}")

    # 4b: Property × Ecosystem Types
    log.info("--- 4b: Property × Ecosystem Types ---")
    with db_transaction(engine) as conn:
        conn.execute(text(f"TRUNCATE {SCHEMA}.property_ecosystems"))

    for i, suburb in enumerate(suburbs):
        try:
            with db_transaction(engine) as conn:
                conn.execute(text(f"""
                    INSERT INTO {SCHEMA}.property_ecosystems
                        (property_id, ecosystem_type_id, vegetation_type, threat_status,
                         overlap_area_sqm, overlap_pct)
                    SELECT
                        p.id,
                        e.id,
                        e.vegetation_type,
                        e.threat_status,
                        ST_Area(ST_Intersection(p.geom, e.geom)::geography),
                        ST_Area(ST_Intersection(p.geom, e.geom)::geography) / NULLIF(p.area_sqm, 0) * 100
                    FROM {SCHEMA}.properties p
                    JOIN {SCHEMA}.ecosystem_types e ON ST_Intersects(p.geom, e.geom)
                    WHERE p.suburb = :suburb
                    ON CONFLICT (property_id, ecosystem_type_id) DO NOTHING
                """), {"suburb": suburb})

            if (i + 1) % 50 == 0:
                log.info(f"    Progress: {i+1}/{len(suburbs)} suburbs")
        except Exception as e:
            log.warning(f"    Error for suburb '{suburb}': {e}")

    # 4c: Property × Urban Edge (inside/outside)
    log.info("--- 4c: Property × Urban Edge ---")
    with db_transaction(engine) as conn:
        conn.execute(text(f"TRUNCATE {SCHEMA}.property_urban_edge"))

        # The urban development edge is a polygon; properties inside it are "inside"
        conn.execute(text(f"""
            INSERT INTO {SCHEMA}.property_urban_edge (property_id, inside_urban_edge)
            SELECT p.id, TRUE
            FROM {SCHEMA}.properties p
            WHERE EXISTS (
                SELECT 1 FROM {SCHEMA}.urban_edges ue
                WHERE ue.edge_type = 'development'
                AND ST_Intersects(p.geom, ue.geom)
            )
        """))

        result = conn.execute(text(f"SELECT COUNT(*) FROM {SCHEMA}.property_urban_edge"))
        inside_count = result.scalar()
        log.info(f"  Properties inside urban edge: {inside_count}")

        # Insert remaining as outside (use LEFT JOIN instead of NOT IN for performance)
        conn.execute(text(f"""
            INSERT INTO {SCHEMA}.property_urban_edge (property_id, inside_urban_edge)
            SELECT p.id, FALSE
            FROM {SCHEMA}.properties p
            LEFT JOIN {SCHEMA}.property_urban_edge pue ON p.id = pue.property_id
            WHERE pue.property_id IS NULL
        """))

        result = conn.execute(text(f"SELECT COUNT(*) FROM {SCHEMA}.property_urban_edge"))
        total_count = result.scalar()
        log.info(f"  Total properties with urban edge status: {total_count}")

    log.info("  Spatial intersections complete")


# =============================================================================
# MAIN
# =============================================================================

def load_all(engine, table=None):
    """Load all datasets or a specific table."""
    loaders = {
        "properties": load_properties,
        "biodiversity": load_biodiversity,
        "ecosystem_types": load_ecosystem_types,
        "address_points": load_address_points,
        "urban_edges": load_urban_edges,
        "heritage": load_heritage,
        "environmental": load_environmental,
        "wetlands": load_wetlands,
    }

    if table:
        if table in loaders:
            loaders[table](engine)
        else:
            log.error(f"Unknown table: {table}. Available: {list(loaders.keys())}")
    else:
        for name, loader in loaders.items():
            t0 = time.time()
            try:
                loader(engine)
            except Exception as e:
                log.error(f"Failed to load {name}: {e}")
                import traceback
                traceback.print_exc()
            elapsed = time.time() - t0
            log.info(f"  [{name}] completed in {elapsed:.1f}s\n")


def main():
    parser = argparse.ArgumentParser(description="Cape Town Eco-Property Data Loader")
    parser.add_argument(
        "--step",
        choices=["setup", "load", "index", "intersect", "all"],
        required=True,
        help="Pipeline step to execute",
    )
    parser.add_argument("--table", help="Load a specific table only (with --step load)")
    args = parser.parse_args()

    engine = get_engine()

    if args.step == "setup" or args.step == "all":
        setup_database()
        engine.dispose()
        engine = get_engine()

    if args.step == "load" or args.step == "all":
        load_all(engine, args.table)

    if args.step == "index" or args.step == "all":
        create_indexes(engine)

    if args.step == "intersect" or args.step == "all":
        run_spatial_intersections(engine)

    engine.dispose()
    log.info("Done.")


if __name__ == "__main__":
    main()
