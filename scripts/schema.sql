-- Cape Town Eco-Property Intelligence: Database Schema
-- PostgreSQL 15 + PostGIS 3.x
-- All geometries stored in EPSG:4326 (WGS84) for web mapping compatibility
-- Source data arrives in EPSG:3857 (Web Mercator) and is reprojected on load

-- =============================================================================
-- EXTENSIONS
-- =============================================================================
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- =============================================================================
-- SCHEMA
-- =============================================================================
DROP SCHEMA IF EXISTS capeeco CASCADE;
CREATE SCHEMA capeeco;
SET search_path TO capeeco, public;

-- =============================================================================
-- ENUM TYPES (for constrained values discovered in actual data)
-- =============================================================================

CREATE TYPE capeeco.cba_category AS ENUM (
    'PA',       -- Protected Area
    'CA',       -- Conservation Area
    'CBA 1a',   -- Critical Biodiversity Area 1a (irreplaceable, high/medium condition)
    'CBA 1b',   -- Critical Biodiversity Area 1b (irreplaceable, low condition)
    'CBA 1c',   -- Critical Biodiversity Area 1c (irreplaceable, connectivity)
    'CBA 2',    -- Critical Biodiversity Area 2 (optimal selection)
    'ESA 1',    -- Ecological Support Area 1 (natural/semi-natural)
    'ESA 2',    -- Ecological Support Area 2 (intensively modified)
    'ONA'       -- Other Natural Area
);

CREATE TYPE capeeco.ecosystem_threat_status AS ENUM (
    'CR',   -- Critically Endangered
    'EN',   -- Endangered
    'VU',   -- Vulnerable
    'LT'    -- Least Threatened
);

CREATE TYPE capeeco.habitat_condition AS ENUM (
    'Natural',
    'Good',
    'Fair',
    'Poor',
    'Irreversibly modified',
    'Natural aquatic habitat'
);

-- =============================================================================
-- TABLE: properties
-- The core table. One row per land parcel (erf).
-- Source: cct_land_parcels_2025.geojson (~400k parcels, 786MB)
--
-- Key design decisions:
--   - erf_number is TEXT not INTEGER because actual data has "10-RE", "102-0-1" formats
--   - sg26_code is the unique Surveyor General 25-char code (true unique ID)
--   - zoning is TEXT because split-zoned properties have comma-separated multi-values
--   - geometry is MULTIPOLYGON because all source data is MultiPolygon
--   - area_sqm computed from geometry in EPSG:3857 for accuracy (not from source SHAPE_Area
--     which is in decimal degrees squared)
-- =============================================================================
CREATE TABLE capeeco.properties (
    id              BIGSERIAL PRIMARY KEY,
    objectid        INTEGER,                    -- Source OBJECTID
    sg26_code       VARCHAR(30) UNIQUE NOT NULL, -- Surveyor General 26-digit code (actual unique key)
    sl_parcel_key   BIGINT,                     -- Source SL_LAND_PRCL_KEY
    erf_number      VARCHAR(50),                -- PRTY_NMBR: "241", "10-RE", "102-0-1"
    address_number  INTEGER,                    -- ADR_NO
    address_suffix  VARCHAR(10),                -- ADR_NO_SFX
    street_name     VARCHAR(200),               -- STR_NAME
    street_type     VARCHAR(50),                -- LU_STR_NAME_TYPE (Street, Road, Drive, etc.)
    suburb          VARCHAR(200),               -- OFC_SBRB_NAME
    alt_suburb_name VARCHAR(200),               -- ALT_NAME
    ward            VARCHAR(10),                -- WARD_NAME
    subcouncil      VARCHAR(10),                -- SUB_CNCL_NMBR
    legal_status    VARCHAR(50),                -- LU_LGL_STS_DSCR (Confirmed, etc.)

    -- Zoning (TEXT because split-zoned parcels have comma-separated lists)
    zoning_raw      TEXT,                       -- Raw ZONING field (can be very long for split zones)
    zoning_primary  VARCHAR(200),               -- First/primary zoning extracted from raw

    -- Computed fields (populated after load)
    area_sqm        DOUBLE PRECISION,           -- Computed via ST_Area(geom::geography)
    area_ha         DOUBLE PRECISION,           -- area_sqm / 10000
    centroid_lon    DOUBLE PRECISION,           -- For fast point lookups
    centroid_lat    DOUBLE PRECISION,

    -- Full address for geocoding/display
    full_address    TEXT,                       -- Constructed: "37 NEIL HARE Road, ATLANTIS INDUSTRIAL"

    -- Geometry: MULTIPOLYGON in WGS84
    geom            geometry(MultiPolygon, 4326) NOT NULL,

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABLE: biodiversity_areas
-- Source: cct_terrestrial_biodiversity_network_2025.geojson (~5k polygons, 90MB)
-- One row per BioNet polygon. Properties are linked via spatial intersection.
-- =============================================================================
CREATE TABLE capeeco.biodiversity_areas (
    id              BIGSERIAL PRIMARY KEY,
    objectid        INTEGER,
    cba_category    capeeco.cba_category NOT NULL,
    cba_name        VARCHAR(200),               -- Full name: "Critical Biodiversity Area 1a"
    subtype         TEXT,                        -- SBTY description
    sdf_category    VARCHAR(100),                -- SDF_CTGR: "Core 1: CBA", "Buffer 1", etc.
    description     TEXT,                        -- CBA_DSCR
    significance    TEXT,                        -- SGNF_HBT
    objective       TEXT,                        -- OBJC
    action          TEXT,                        -- ACTN
    compatible_use  TEXT,                        -- CMPT_ACTV
    habitat_cond    capeeco.habitat_condition,   -- HBT_CNDT
    esa_significance VARCHAR(100),               -- CESA_SGNF: "Animal Movement", "Fire Regime"
    protected_area  VARCHAR(200),                -- NAME_PRTC_AREA
    proclaimed      VARCHAR(100),                -- PRCL
    managed         BOOLEAN,                     -- MNGD
    primary_class   VARCHAR(100),                -- PRMR_CLS
    area_ha         DOUBLE PRECISION,            -- AREA_HCTR from source
    perimeter_m     DOUBLE PRECISION,            -- PRMT_MTR from source

    geom            geometry(MultiPolygon, 4326) NOT NULL,

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABLE: ecosystem_types
-- Source: cct_sanbi_ecosystem_status_2011.geojson + cct_indigenous_vegetation_current_2025.geojson
-- Vegetation type polygons with threat status.
-- =============================================================================
CREATE TABLE capeeco.ecosystem_types (
    id                  BIGSERIAL PRIMARY KEY,
    objectid            INTEGER,
    vegetation_type     VARCHAR(200),           -- NTNL_VGTN_TYPE
    vegetation_subtype  VARCHAR(200),           -- VGTN_SBTY
    community           VARCHAR(200),           -- CMNT
    threat_status       capeeco.ecosystem_threat_status, -- ECSY_STS_2011
    area_ha             DOUBLE PRECISION,       -- AREA_HCTR
    perimeter_m         DOUBLE PRECISION,

    geom                geometry(MultiPolygon, 4326) NOT NULL,

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABLE: wetlands
-- Source: cct_wetlands_2025.geojson
-- Aquatic biodiversity network features.
-- =============================================================================
CREATE TABLE capeeco.wetlands (
    id              BIGSERIAL PRIMARY KEY,
    objectid        INTEGER,
    geom            geometry(MultiPolygon, 4326) NOT NULL,
    -- Fields populated from metadata inspection
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABLE: urban_edges
-- Source: cct_urban_development_edge_2025.geojson + cct_coastal_urban_edge_2025.geojson
-- =============================================================================
CREATE TABLE capeeco.urban_edges (
    id              BIGSERIAL PRIMARY KEY,
    objectid        INTEGER,
    edge_type       VARCHAR(50) NOT NULL,       -- 'development' or 'coastal'
    geom            geometry(Geometry, 4326) NOT NULL,  -- Could be Polygon or LineString
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABLE: zoning_overlays
-- Source: cct_zoning_2025.geojson (~642MB, separate from property zoning)
-- Full zoning scheme polygons with detailed attributes.
-- =============================================================================
CREATE TABLE capeeco.zoning_overlays (
    id              BIGSERIAL PRIMARY KEY,
    objectid        INTEGER,
    geom            geometry(MultiPolygon, 4326) NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABLE: heritage_sites
-- Source: cct_heritage_inventory_2025.geojson + cct_nhra_protection_2025.geojson
-- =============================================================================
CREATE TABLE capeeco.heritage_sites (
    id              BIGSERIAL PRIMARY KEY,
    objectid        INTEGER,
    source          VARCHAR(20) NOT NULL,       -- 'inventory' or 'nhra'
    site_name       VARCHAR(500),
    heritage_category INTEGER,
    resource_type_1 VARCHAR(200),
    resource_type_2 VARCHAR(200),
    description     TEXT,
    architectural_style VARCHAR(200),
    period          VARCHAR(200),
    nhra_status     VARCHAR(200),
    city_grading    VARCHAR(200),
    street_address  TEXT,
    area_ha         DOUBLE PRECISION,

    geom            geometry(MultiPolygon, 4326) NOT NULL,

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABLE: address_points
-- Source: cct_street_address_numbers_2025.geojson (~350MB, ~700k points)
-- Used for geocoding.
-- =============================================================================
CREATE TABLE capeeco.address_points (
    id              BIGSERIAL PRIMARY KEY,
    objectid        INTEGER,
    address_number  INTEGER,
    address_prefix  VARCHAR(10),
    address_suffix  VARCHAR(10),
    suburb          VARCHAR(200),
    street_name     VARCHAR(200),
    street_type     VARCHAR(50),
    full_address    VARCHAR(500),               -- FULL_ADR
    property_id     BIGINT,                     -- FK populated via spatial join later

    geom            geometry(Point, 4326) NOT NULL,

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABLE: solar_installations
-- Source: cct_smartfacility_solar_2025.geojson
-- =============================================================================
CREATE TABLE capeeco.solar_installations (
    id              BIGSERIAL PRIMARY KEY,
    objectid        INTEGER,
    geom            geometry(Point, 4326) NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABLE: environmental_focus_areas
-- Source: cct_environmental_focus_areas_2025.geojson
-- =============================================================================
CREATE TABLE capeeco.environmental_focus_areas (
    id              BIGSERIAL PRIMARY KEY,
    objectid        INTEGER,
    name            VARCHAR(200),
    description     VARCHAR(500),
    area_ha         DOUBLE PRECISION,
    geom            geometry(MultiPolygon, 4326) NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- DERIVED/COMPUTED TABLES (populated by the data loader pipeline)
-- =============================================================================

-- Spatial join: which biodiversity designations overlap each property
CREATE TABLE capeeco.property_biodiversity (
    id                  BIGSERIAL PRIMARY KEY,
    property_id         BIGINT NOT NULL REFERENCES capeeco.properties(id),
    biodiversity_area_id BIGINT NOT NULL REFERENCES capeeco.biodiversity_areas(id),
    cba_category        capeeco.cba_category NOT NULL,
    habitat_condition   capeeco.habitat_condition,
    overlap_area_sqm    DOUBLE PRECISION,       -- Area of intersection
    overlap_pct         DOUBLE PRECISION,       -- % of property covered by this designation
    created_at          TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(property_id, biodiversity_area_id)
);

-- Spatial join: which ecosystem type each property falls in
CREATE TABLE capeeco.property_ecosystems (
    id                  BIGSERIAL PRIMARY KEY,
    property_id         BIGINT NOT NULL REFERENCES capeeco.properties(id),
    ecosystem_type_id   BIGINT NOT NULL REFERENCES capeeco.ecosystem_types(id),
    vegetation_type     VARCHAR(200),
    threat_status       capeeco.ecosystem_threat_status,
    overlap_area_sqm    DOUBLE PRECISION,
    overlap_pct         DOUBLE PRECISION,
    created_at          TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(property_id, ecosystem_type_id)
);

-- Is the property inside or outside the urban edge?
CREATE TABLE capeeco.property_urban_edge (
    id              BIGSERIAL PRIMARY KEY,
    property_id     BIGINT NOT NULL REFERENCES capeeco.properties(id) UNIQUE,
    inside_urban_edge BOOLEAN NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Offset calculation results (per development proposal)
CREATE TABLE capeeco.offset_calculations (
    id                          BIGSERIAL PRIMARY KEY,
    property_id                 BIGINT NOT NULL REFERENCES capeeco.properties(id),
    proposed_footprint_sqm      DOUBLE PRECISION NOT NULL,
    cba_category                capeeco.cba_category,
    ecosystem_threat_status     capeeco.ecosystem_threat_status,
    habitat_condition           capeeco.habitat_condition,
    base_ratio                  DOUBLE PRECISION,
    condition_multiplier        DOUBLE PRECISION,
    urban_edge_adjustment       DOUBLE PRECISION,
    required_offset_ha          DOUBLE PRECISION,
    estimated_cost_zar          DOUBLE PRECISION,
    is_no_go                    BOOLEAN DEFAULT FALSE,
    no_go_reason                TEXT,
    conservation_bank_eligible  BOOLEAN DEFAULT FALSE,
    notes                       TEXT,
    created_at                  TIMESTAMPTZ DEFAULT NOW()
);

-- Rainfall station data (tabular)
CREATE TABLE capeeco.rainfall_stations (
    id              SERIAL PRIMARY KEY,
    station_id      VARCHAR(50) UNIQUE NOT NULL,
    station_name    VARCHAR(200),
    geom            geometry(Point, 4326),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE capeeco.rainfall_data (
    id              BIGSERIAL PRIMARY KEY,
    station_id      VARCHAR(50) NOT NULL,
    observation_date DATE NOT NULL,
    rainfall_mm     DOUBLE PRECISION,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Solar potential per property (computed)
CREATE TABLE capeeco.solar_potential (
    id                  BIGSERIAL PRIMARY KEY,
    property_id         BIGINT NOT NULL REFERENCES capeeco.properties(id) UNIQUE,
    roof_area_sqm       DOUBLE PRECISION,
    annual_kwh_estimate DOUBLE PRECISION,
    annual_kwh_per_sqm  DOUBLE PRECISION,       -- Based on Cape Town avg solar irradiance
    payback_years       DOUBLE PRECISION,
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- STAGING TABLES (for safe data loading with rollback capability)
-- Loader writes to staging first, validates, then promotes to production tables.
-- =============================================================================
CREATE TABLE capeeco.staging_properties      (LIKE capeeco.properties      INCLUDING ALL);
CREATE TABLE capeeco.staging_biodiversity     (LIKE capeeco.biodiversity_areas INCLUDING ALL);
CREATE TABLE capeeco.staging_ecosystem_types  (LIKE capeeco.ecosystem_types  INCLUDING ALL);
CREATE TABLE capeeco.staging_address_points   (LIKE capeeco.address_points   INCLUDING ALL);
CREATE TABLE capeeco.staging_heritage         (LIKE capeeco.heritage_sites   INCLUDING ALL);

-- Drop the FK constraints and unique constraints on staging tables (they interfere with bulk load)
-- Staging tables are validated before promotion
ALTER TABLE capeeco.staging_properties DROP CONSTRAINT IF EXISTS staging_properties_sg26_code_key;
ALTER TABLE capeeco.staging_properties DROP CONSTRAINT IF EXISTS staging_properties_pkey;
ALTER TABLE capeeco.staging_biodiversity DROP CONSTRAINT IF EXISTS staging_biodiversity_pkey;
ALTER TABLE capeeco.staging_ecosystem_types DROP CONSTRAINT IF EXISTS staging_ecosystem_types_pkey;
ALTER TABLE capeeco.staging_address_points DROP CONSTRAINT IF EXISTS staging_address_points_pkey;
ALTER TABLE capeeco.staging_heritage DROP CONSTRAINT IF EXISTS staging_heritage_pkey;

-- =============================================================================
-- INDEXES
-- Created AFTER data load for performance (building indexes on empty tables
-- then inserting is slower than inserting then building indexes).
-- These are created by the data_loader.py after load completes.
-- =============================================================================

-- This file defines the indexes but they are created by data_loader.py post-load:
-- See create_indexes() function in data_loader.py

-- =============================================================================
-- COMMENTS
-- =============================================================================
COMMENT ON SCHEMA capeeco IS 'Cape Town Eco-Property Intelligence Platform';
COMMENT ON TABLE capeeco.properties IS 'Land parcels (erven) from CCT cadastral data. ~400k rows.';
COMMENT ON TABLE capeeco.biodiversity_areas IS 'BioNet 2024 CBA/ESA polygons. ~5k rows.';
COMMENT ON TABLE capeeco.ecosystem_types IS 'SANBI vegetation ecosystem status. ~25 types, ~2k polygons.';
COMMENT ON TABLE capeeco.property_biodiversity IS 'Spatial join: property × biodiversity. Computed post-load.';
COMMENT ON TABLE capeeco.property_ecosystems IS 'Spatial join: property × ecosystem type. Computed post-load.';
COMMENT ON TABLE capeeco.property_urban_edge IS 'Is property inside/outside urban development edge. Computed post-load.';
COMMENT ON COLUMN capeeco.properties.erf_number IS 'Property number. TEXT because formats include "10-RE", "102-0-1", "10202-0-2" for remainders and subdivisions.';
COMMENT ON COLUMN capeeco.properties.sg26_code IS 'Surveyor General 26-digit code. The true unique identifier for SA land parcels.';
COMMENT ON COLUMN capeeco.properties.zoning_raw IS 'Raw zoning. Split-zoned parcels have comma-separated multi-values that can be hundreds of chars.';

-- =============================================================================
-- USERS (authentication)
-- =============================================================================
CREATE TABLE IF NOT EXISTS capeeco.users (
    id          BIGSERIAL PRIMARY KEY,
    email       VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name   VARCHAR(255),
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON capeeco.users(email);
