"""
Siteline — Development Potential & Site Plan Engine

Calculates maximum development potential for properties using:
- Cape Town Zoning Scheme (CTZS) Table A regulations
- Property geometry (PostGIS spatial analysis)
- Biodiversity constraints (CBA/ESA no-go zones)
- Urban edge status
- Heritage buffers

Functions:
1. calculate_development_potential(property_id) — Full development yield analysis
2. generate_site_plan_geojson(property_id) — GeoJSON FeatureCollection for map rendering
"""

import json
import logging
import math
import os

from sqlalchemy import create_engine, text

logger = logging.getLogger("siteline")

SCHEMA = os.environ.get("SITELINE_SCHEMA", "capeeco")
_FALLBACK_SCHEMA = "capeeco"


def _conn_string():
    raw = os.environ.get("DATABASE_URL", "")
    if raw:
        if raw.startswith("postgres://"):
            raw = raw.replace("postgres://", "postgresql://", 1)
        return raw
    pw = os.environ.get("PGPASSWORD", "")
    host = os.environ.get("PGHOST", "localhost")
    port = os.environ.get("PGPORT", "5432")
    user = os.environ.get("PGUSER", os.environ.get("USER", "postgres"))
    name = os.environ.get("PGDATABASE", "capeeco")
    return f"postgresql://{user}:{pw}@{host}:{port}/{name}" if pw else f"postgresql://{user}@{host}:{port}/{name}"


def _get_engine():
    return create_engine(_conn_string(), pool_size=3, max_overflow=5, pool_pre_ping=True)


def _get_schema(conn):
    try:
        conn.execute(text(f"SELECT 1 FROM {SCHEMA}.properties LIMIT 1"))
        return SCHEMA
    except Exception:
        return _FALLBACK_SCHEMA


# =============================================================================
# CTZS Zoning Rules (Cape Town Zoning Scheme — Table A simplified)
# =============================================================================

# Maps database zoning_primary values to zone codes
ZONING_NAME_TO_CODE = {
    "Single Residential 1 : Conventional Housing": "SR1",
    "Single Residential 2 : Incremental Housing": "SR2",
    "General Residential 1 : Group Housing": "GR1",
    "General Residential 2": "GR2",
    "General Residential 3": "GR3",
    "General Residential 4": "GR4",
    "General Residential 5": "GR5",
    "General Residential 6": "GR6",
    "General Business 1": "GB1",
    "General Business 2": "GB2",
    "General Business 3": "GB3",
    "General Business 4": "GB4",
    "General Business 5": "GB5",
    "General Business 6": "GB6",
    "General Business 7": "GB7",
    "Local Business 1 : Intermediate Business": "LB1",
    "Local Business 2 : Local Business": "LB2",
    "Mixed Use 1": "MU1",
    "Mixed Use 2": "MU2",
    "Mixed Use 3": "MU3",
    "General Industrial 1": "GI1",
    "General Industrial 2": "GI2",
    "Risk Industry": "RI",
    "Transport 1 : Transport Use": "TR1",
    "Transport 2 : Public Road and Public Parking": "TR2",
    "Open Space 1 : Environmental Conservation": "OS1",
    "Open Space 2 : Public Open Space": "OS2",
    "Open Space 3: Special Open Space": "OS3",
    "Community 1 : Local": "CO1",
    "Community 2 : Regional": "CO2",
    "Agricultural": "AG",
    "Rural": "RU",
    "Utility": "UT",
    "Limited Use Zone": "LUZ",
    "Council To Deem": "CTD",
}

# CTZS Table A development parameters
# Format: zone_code → {setback_front, setback_side, setback_rear, coverage_pct, far, height_limit, max_floors, parking_ratio, min_erf_sqm, zone_name, notes}
CTZS_RULES = {
    # Single Residential
    "SR1": {
        "zone_name": "Single Residential 1",
        "setback_front": 4.5, "setback_side": 1.5, "setback_rear": 3.0,
        "coverage_pct": 50, "far": 0.50, "height_limit": 9.0, "max_floors": 2,
        "parking_ratio": 2.0, "min_erf_sqm": 350,
        "notes": "Conventional housing. One dwelling per erf. Max 2 storeys.",
    },
    "SR2": {
        "zone_name": "Single Residential 2",
        "setback_front": 3.0, "setback_side": 0.0, "setback_rear": 2.0,
        "coverage_pct": 80, "far": 1.00, "height_limit": 8.0, "max_floors": 2,
        "parking_ratio": 1.0, "min_erf_sqm": 100,
        "notes": "Incremental housing. Higher coverage for compact sites.",
    },
    # General Residential
    "GR1": {
        "zone_name": "General Residential 1",
        "setback_front": 3.0, "setback_side": 1.5, "setback_rear": 3.0,
        "coverage_pct": 50, "far": 0.50, "height_limit": 9.0, "max_floors": 2,
        "parking_ratio": 1.5, "min_erf_sqm": 250,
        "notes": "Group housing. Allows multiple dwellings (row houses, townhouses).",
    },
    "GR2": {
        "zone_name": "General Residential 2",
        "setback_front": 3.0, "setback_side": 1.5, "setback_rear": 3.0,
        "coverage_pct": 50, "far": 0.75, "height_limit": 12.0, "max_floors": 3,
        "parking_ratio": 1.5, "min_erf_sqm": 600,
        "notes": "Medium-density residential. Flats and maisonettes up to 3 storeys.",
    },
    "GR3": {
        "zone_name": "General Residential 3",
        "setback_front": 4.5, "setback_side": 3.0, "setback_rear": 4.5,
        "coverage_pct": 50, "far": 1.00, "height_limit": 15.0, "max_floors": 4,
        "parking_ratio": 1.5, "min_erf_sqm": 800,
        "notes": "Medium-density. Flats up to 4 storeys.",
    },
    "GR4": {
        "zone_name": "General Residential 4",
        "setback_front": 4.5, "setback_side": 3.0, "setback_rear": 6.0,
        "coverage_pct": 50, "far": 1.50, "height_limit": 21.0, "max_floors": 6,
        "parking_ratio": 1.5, "min_erf_sqm": 1000,
        "notes": "Higher density residential. Flats up to 6 storeys.",
    },
    "GR5": {
        "zone_name": "General Residential 5",
        "setback_front": 6.0, "setback_side": 4.5, "setback_rear": 6.0,
        "coverage_pct": 50, "far": 2.00, "height_limit": 30.0, "max_floors": 8,
        "parking_ratio": 1.5, "min_erf_sqm": 1500,
        "notes": "High density residential. Apartment blocks up to 8 storeys.",
    },
    "GR6": {
        "zone_name": "General Residential 6",
        "setback_front": 6.0, "setback_side": 6.0, "setback_rear": 6.0,
        "coverage_pct": 50, "far": 3.00, "height_limit": 45.0, "max_floors": 12,
        "parking_ratio": 1.5, "min_erf_sqm": 2000,
        "notes": "Highest density residential. Towers up to 12+ storeys.",
    },
    # General Business
    "GB1": {
        "zone_name": "General Business 1",
        "setback_front": 0.0, "setback_side": 0.0, "setback_rear": 3.0,
        "coverage_pct": 100, "far": 2.00, "height_limit": 24.0, "max_floors": 6,
        "parking_ratio": 3.0, "min_erf_sqm": 0,
        "notes": "CBD commercial. No front/side setbacks. Parking per 100m² GFA.",
    },
    "GB2": {
        "zone_name": "General Business 2",
        "setback_front": 0.0, "setback_side": 0.0, "setback_rear": 3.0,
        "coverage_pct": 100, "far": 3.00, "height_limit": 36.0, "max_floors": 10,
        "parking_ratio": 3.0, "min_erf_sqm": 0,
        "notes": "Intensive commercial. Higher FAR for major business nodes.",
    },
    "GB3": {
        "zone_name": "General Business 3",
        "setback_front": 0.0, "setback_side": 0.0, "setback_rear": 3.0,
        "coverage_pct": 100, "far": 5.00, "height_limit": 60.0, "max_floors": 16,
        "parking_ratio": 3.5, "min_erf_sqm": 0,
        "notes": "High-rise commercial. Cape Town CBD, Foreshore.",
    },
    "GB4": {
        "zone_name": "General Business 4",
        "setback_front": 0.0, "setback_side": 0.0, "setback_rear": 3.0,
        "coverage_pct": 100, "far": 7.00, "height_limit": 80.0, "max_floors": 22,
        "parking_ratio": 3.5, "min_erf_sqm": 0,
        "notes": "High-rise commercial. Premium CBD sites.",
    },
    "GB5": {
        "zone_name": "General Business 5",
        "setback_front": 4.5, "setback_side": 3.0, "setback_rear": 3.0,
        "coverage_pct": 60, "far": 1.00, "height_limit": 15.0, "max_floors": 4,
        "parking_ratio": 4.0, "min_erf_sqm": 0,
        "notes": "Suburban business. Setbacks required.",
    },
    "GB6": {
        "zone_name": "General Business 6",
        "setback_front": 3.0, "setback_side": 0.0, "setback_rear": 3.0,
        "coverage_pct": 80, "far": 1.50, "height_limit": 18.0, "max_floors": 5,
        "parking_ratio": 3.0, "min_erf_sqm": 0,
        "notes": "Neighbourhood business.",
    },
    "GB7": {
        "zone_name": "General Business 7",
        "setback_front": 6.0, "setback_side": 3.0, "setback_rear": 3.0,
        "coverage_pct": 50, "far": 0.75, "height_limit": 12.0, "max_floors": 3,
        "parking_ratio": 4.0, "min_erf_sqm": 0,
        "notes": "Business park / office park.",
    },
    # Local Business
    "LB1": {
        "zone_name": "Local Business 1",
        "setback_front": 0.0, "setback_side": 0.0, "setback_rear": 3.0,
        "coverage_pct": 100, "far": 1.50, "height_limit": 15.0, "max_floors": 4,
        "parking_ratio": 3.0, "min_erf_sqm": 0,
        "notes": "Intermediate business zone.",
    },
    "LB2": {
        "zone_name": "Local Business 2",
        "setback_front": 0.0, "setback_side": 0.0, "setback_rear": 3.0,
        "coverage_pct": 80, "far": 1.00, "height_limit": 12.0, "max_floors": 3,
        "parking_ratio": 3.0, "min_erf_sqm": 0,
        "notes": "Local corner shops, neighbourhood retail.",
    },
    # Mixed Use
    "MU1": {
        "zone_name": "Mixed Use 1",
        "setback_front": 0.0, "setback_side": 0.0, "setback_rear": 3.0,
        "coverage_pct": 100, "far": 2.50, "height_limit": 30.0, "max_floors": 8,
        "parking_ratio": 2.0, "min_erf_sqm": 0,
        "notes": "Intensive mixed use. Residential above commercial.",
    },
    "MU2": {
        "zone_name": "Mixed Use 2",
        "setback_front": 3.0, "setback_side": 1.5, "setback_rear": 3.0,
        "coverage_pct": 75, "far": 1.50, "height_limit": 18.0, "max_floors": 5,
        "parking_ratio": 2.0, "min_erf_sqm": 0,
        "notes": "Moderate mixed use. Suburban nodes.",
    },
    "MU3": {
        "zone_name": "Mixed Use 3",
        "setback_front": 4.5, "setback_side": 1.5, "setback_rear": 3.0,
        "coverage_pct": 60, "far": 1.00, "height_limit": 12.0, "max_floors": 3,
        "parking_ratio": 2.0, "min_erf_sqm": 0,
        "notes": "Low-intensity mixed use. Residential character areas.",
    },
    # Industrial
    "GI1": {
        "zone_name": "General Industrial 1",
        "setback_front": 6.0, "setback_side": 3.0, "setback_rear": 3.0,
        "coverage_pct": 75, "far": 1.50, "height_limit": 18.0, "max_floors": 4,
        "parking_ratio": 1.0, "min_erf_sqm": 0,
        "notes": "General industrial. Warehousing, manufacturing.",
    },
    "GI2": {
        "zone_name": "General Industrial 2",
        "setback_front": 10.0, "setback_side": 5.0, "setback_rear": 5.0,
        "coverage_pct": 60, "far": 1.00, "height_limit": 15.0, "max_floors": 3,
        "parking_ratio": 1.0, "min_erf_sqm": 0,
        "notes": "Noxious or heavy industrial. Larger setbacks.",
    },
    "RI": {
        "zone_name": "Risk Industry",
        "setback_front": 15.0, "setback_side": 10.0, "setback_rear": 10.0,
        "coverage_pct": 50, "far": 0.75, "height_limit": 15.0, "max_floors": 3,
        "parking_ratio": 1.0, "min_erf_sqm": 0,
        "notes": "Hazardous industry. Large buffers required.",
    },
    # Community
    "CO1": {
        "zone_name": "Community 1",
        "setback_front": 4.5, "setback_side": 3.0, "setback_rear": 3.0,
        "coverage_pct": 50, "far": 1.00, "height_limit": 12.0, "max_floors": 3,
        "parking_ratio": 2.0, "min_erf_sqm": 0,
        "notes": "Local community facilities (schools, clinics, halls).",
    },
    "CO2": {
        "zone_name": "Community 2",
        "setback_front": 6.0, "setback_side": 4.5, "setback_rear": 4.5,
        "coverage_pct": 50, "far": 1.50, "height_limit": 18.0, "max_floors": 5,
        "parking_ratio": 3.0, "min_erf_sqm": 0,
        "notes": "Regional community facilities (hospitals, universities).",
    },
    # Open Space — generally not developable
    "OS1": {
        "zone_name": "Open Space 1",
        "setback_front": 0.0, "setback_side": 0.0, "setback_rear": 0.0,
        "coverage_pct": 2, "far": 0.02, "height_limit": 6.0, "max_floors": 1,
        "parking_ratio": 0.0, "min_erf_sqm": 0,
        "notes": "Environmental conservation. Development severely restricted.",
    },
    "OS2": {
        "zone_name": "Open Space 2",
        "setback_front": 0.0, "setback_side": 0.0, "setback_rear": 0.0,
        "coverage_pct": 5, "far": 0.05, "height_limit": 6.0, "max_floors": 1,
        "parking_ratio": 0.0, "min_erf_sqm": 0,
        "notes": "Public open space. Parks, playgrounds. Minimal structures.",
    },
    "OS3": {
        "zone_name": "Open Space 3",
        "setback_front": 3.0, "setback_side": 1.5, "setback_rear": 3.0,
        "coverage_pct": 25, "far": 0.25, "height_limit": 9.0, "max_floors": 2,
        "parking_ratio": 1.0, "min_erf_sqm": 0,
        "notes": "Special open space. Golf courses, cemeteries, sports facilities.",
    },
    # Transport
    "TR1": {
        "zone_name": "Transport 1",
        "setback_front": 0.0, "setback_side": 0.0, "setback_rear": 0.0,
        "coverage_pct": 80, "far": 1.00, "height_limit": 12.0, "max_floors": 3,
        "parking_ratio": 0.0, "min_erf_sqm": 0,
        "notes": "Transport facilities (stations, depots).",
    },
    "TR2": {
        "zone_name": "Transport 2",
        "setback_front": 0.0, "setback_side": 0.0, "setback_rear": 0.0,
        "coverage_pct": 0, "far": 0.0, "height_limit": 0.0, "max_floors": 0,
        "parking_ratio": 0.0, "min_erf_sqm": 0,
        "notes": "Public roads and parking. Not developable.",
    },
    # Agricultural / Rural
    "AG": {
        "zone_name": "Agricultural",
        "setback_front": 10.0, "setback_side": 5.0, "setback_rear": 5.0,
        "coverage_pct": 10, "far": 0.10, "height_limit": 9.0, "max_floors": 2,
        "parking_ratio": 1.0, "min_erf_sqm": 0,
        "notes": "Agricultural use. One dwelling per farm. Tourism consent possible.",
    },
    "RU": {
        "zone_name": "Rural",
        "setback_front": 10.0, "setback_side": 5.0, "setback_rear": 5.0,
        "coverage_pct": 10, "far": 0.10, "height_limit": 9.0, "max_floors": 2,
        "parking_ratio": 1.0, "min_erf_sqm": 0,
        "notes": "Rural use. Similar to agricultural, limited subdivision.",
    },
    # Utility / Other
    "UT": {
        "zone_name": "Utility",
        "setback_front": 3.0, "setback_side": 1.5, "setback_rear": 3.0,
        "coverage_pct": 60, "far": 1.00, "height_limit": 12.0, "max_floors": 3,
        "parking_ratio": 1.0, "min_erf_sqm": 0,
        "notes": "Public utility installations (substations, pump stations).",
    },
    "LUZ": {
        "zone_name": "Limited Use Zone",
        "setback_front": 4.5, "setback_side": 1.5, "setback_rear": 3.0,
        "coverage_pct": 50, "far": 0.50, "height_limit": 9.0, "max_floors": 2,
        "parking_ratio": 1.5, "min_erf_sqm": 0,
        "notes": "Limited use — specific conditions apply per property.",
    },
    "CTD": {
        "zone_name": "Council To Deem",
        "setback_front": 4.5, "setback_side": 1.5, "setback_rear": 3.0,
        "coverage_pct": 50, "far": 0.50, "height_limit": 9.0, "max_floors": 2,
        "parking_ratio": 1.5, "min_erf_sqm": 0,
        "notes": "Zoning to be determined by Council. Assumed SR1 defaults.",
    },
}

# Average unit sizes by property type (m²) for yield estimation
AVG_UNIT_SIZES = {
    "residential_single": 180,      # standalone house
    "residential_group": 120,       # townhouse / row house
    "residential_medium": 80,       # flat / apartment
    "residential_high": 65,         # high-density apartment
    "commercial": 100,              # office / retail
    "industrial": 500,              # warehouse unit
    "mixed_use": 90,                # mixed residential-commercial
}

# CBA categories that constitute no-go zones for development
NO_GO_CATEGORIES = {"PA", "CA", "CBA 1a", "CBA 1b"}

# =============================================================================
# Unit mix templates — typical SA residential unit breakdown by dev type
# =============================================================================

UNIT_MIX = {
    "residential_single": [
        {"type": "house", "label": "Detached House", "size_sqm": 180, "bedrooms": 3, "share": 1.0},
    ],
    "residential_group": [
        {"type": "townhouse_2bed", "label": "2-Bed Townhouse", "size_sqm": 90, "bedrooms": 2, "share": 0.40},
        {"type": "townhouse_3bed", "label": "3-Bed Townhouse", "size_sqm": 120, "bedrooms": 3, "share": 0.45},
        {"type": "townhouse_4bed", "label": "4-Bed Townhouse", "size_sqm": 160, "bedrooms": 4, "share": 0.15},
    ],
    "residential_medium": [
        {"type": "studio", "label": "Studio", "size_sqm": 30, "bedrooms": 0, "share": 0.10},
        {"type": "1bed", "label": "1-Bed Apartment", "size_sqm": 45, "bedrooms": 1, "share": 0.30},
        {"type": "2bed", "label": "2-Bed Apartment", "size_sqm": 70, "bedrooms": 2, "share": 0.40},
        {"type": "3bed", "label": "3-Bed Apartment", "size_sqm": 95, "bedrooms": 3, "share": 0.20},
    ],
    "residential_high": [
        {"type": "studio", "label": "Studio", "size_sqm": 28, "bedrooms": 0, "share": 0.15},
        {"type": "1bed", "label": "1-Bed Apartment", "size_sqm": 42, "bedrooms": 1, "share": 0.35},
        {"type": "2bed", "label": "2-Bed Apartment", "size_sqm": 65, "bedrooms": 2, "share": 0.35},
        {"type": "3bed", "label": "3-Bed Apartment", "size_sqm": 85, "bedrooms": 3, "share": 0.15},
    ],
    "commercial": [
        {"type": "office_small", "label": "Small Office", "size_sqm": 50, "bedrooms": 0, "share": 0.30},
        {"type": "office_medium", "label": "Medium Office", "size_sqm": 100, "bedrooms": 0, "share": 0.40},
        {"type": "retail", "label": "Retail Unit", "size_sqm": 80, "bedrooms": 0, "share": 0.30},
    ],
    "industrial": [
        {"type": "warehouse_small", "label": "Small Warehouse", "size_sqm": 300, "bedrooms": 0, "share": 0.40},
        {"type": "warehouse_large", "label": "Large Warehouse", "size_sqm": 600, "bedrooms": 0, "share": 0.40},
        {"type": "office_industrial", "label": "Industrial Office", "size_sqm": 80, "bedrooms": 0, "share": 0.20},
    ],
    "mixed_use": [
        {"type": "retail_ground", "label": "Ground Floor Retail", "size_sqm": 80, "bedrooms": 0, "share": 0.20},
        {"type": "1bed", "label": "1-Bed Apartment", "size_sqm": 45, "bedrooms": 1, "share": 0.30},
        {"type": "2bed", "label": "2-Bed Apartment", "size_sqm": 70, "bedrooms": 2, "share": 0.35},
        {"type": "3bed", "label": "3-Bed Apartment", "size_sqm": 90, "bedrooms": 3, "share": 0.15},
    ],
}

# Cape Town market values per m² by unit type (2024/2025 estimates)
MARKET_VALUES_PER_SQM = {
    "house": 18000,
    "townhouse_2bed": 22000,
    "townhouse_3bed": 20000,
    "townhouse_4bed": 18000,
    "studio": 32000,
    "1bed": 28000,
    "2bed": 24000,
    "3bed": 20000,
    "office_small": 22000,
    "office_medium": 20000,
    "retail": 25000,
    "retail_ground": 28000,
    "warehouse_small": 8000,
    "warehouse_large": 6000,
    "office_industrial": 15000,
}

# Construction costs per m² by development type (ZAR, Cape Town 2024/25)
CONSTRUCTION_COSTS_PER_SQM = {
    "residential_single": 13150,
    "residential_group": 12000,
    "residential_medium": 14000,
    "residential_high": 16000,
    "commercial": 17500,
    "industrial": 8000,
    "mixed_use": 15000,
}

# Floor efficiency — net sellable area as % of gross floor area
# Accounts for corridors, staircases, lifts, walls, service ducts
FLOOR_EFFICIENCY = {
    "residential_single": 0.95,
    "residential_group": 0.90,
    "residential_medium": 0.82,
    "residential_high": 0.78,
    "commercial": 0.80,
    "industrial": 0.90,
    "mixed_use": 0.80,
}

# Parking area per bay (m²) — includes circulation/ramps
PARKING_AREA_PER_BAY = {
    "surface": 28,      # surface parking (bay + aisle)
    "basement": 35,     # basement (bay + aisle + ramps + structure)
}

# Professional fees as % of construction cost
PROFESSIONAL_FEES_PCT = 0.12  # architect, engineer, QS, project manager
# Contingency as % of construction cost
CONTINGENCY_PCT = 0.10


def _classify_development_type(zone_code: str) -> str:
    """Classify the development type from zone code."""
    if zone_code in ("SR1", "SR2"):
        return "residential_single"
    if zone_code == "GR1":
        return "residential_group"
    if zone_code in ("GR2", "GR3"):
        return "residential_medium"
    if zone_code in ("GR4", "GR5", "GR6"):
        return "residential_high"
    if zone_code.startswith("GB") or zone_code.startswith("LB"):
        return "commercial"
    if zone_code.startswith("GI") or zone_code == "RI":
        return "industrial"
    if zone_code.startswith("MU"):
        return "mixed_use"
    return "residential_single"  # default


def seed_zoning_rules(engine, schema: str):
    """Seed the zoning_rules table with CTZS data (idempotent)."""
    with engine.connect() as conn:
        for code, rules in CTZS_RULES.items():
            conn.execute(text(f"""
                INSERT INTO {schema}.zoning_rules
                    (zone_code, zone_name, setback_front, setback_side, setback_rear,
                     coverage_pct, far, height_limit, max_floors, parking_ratio, min_erf_sqm, notes)
                VALUES (:code, :name, :sf, :ss, :sr, :cov, :far, :hl, :mf, :pr, :me, :notes)
                ON CONFLICT (zone_code) DO NOTHING
            """), {
                "code": code,
                "name": rules["zone_name"],
                "sf": rules["setback_front"],
                "ss": rules["setback_side"],
                "sr": rules["setback_rear"],
                "cov": rules["coverage_pct"],
                "far": rules["far"],
                "hl": rules["height_limit"],
                "mf": rules["max_floors"],
                "pr": rules["parking_ratio"],
                "me": rules["min_erf_sqm"],
                "notes": rules.get("notes", ""),
            })
        conn.commit()
    logger.info("Zoning rules seeded (%d zone codes)", len(CTZS_RULES))


# =============================================================================
# Core calculation
# =============================================================================

def calculate_development_potential(property_id: int) -> dict:
    """
    Calculate full development potential for a property.

    Returns:
        dict with zoning rules, buildable envelope metrics, development yield,
        constraints, feasibility flags, and recommendations.
    """
    engine = _get_engine()

    with engine.connect() as conn:
        schema = _get_schema(conn)

        # 1. Get property details
        prop = conn.execute(text(f"""
            SELECT p.id, p.erf_number, p.suburb, p.zoning_primary,
                   p.area_sqm, p.area_ha,
                   p.centroid_lat, p.centroid_lon,
                   ST_Area(p.geom::geography) AS geo_area_sqm,
                   pue.inside_urban_edge
            FROM {schema}.properties p
            LEFT JOIN {schema}.property_urban_edge pue ON p.id = pue.property_id
            WHERE p.id = :id
        """), {"id": property_id}).mappings().fetchone()

        if not prop:
            return {"error": "Property not found"}

        prop = dict(prop)
        site_area = float(prop.get("geo_area_sqm") or prop.get("area_sqm") or 0)

        if site_area <= 0:
            return {"error": "Property has no measurable area"}

        # 2. Map zoning to code and get rules
        zoning_name = prop.get("zoning_primary") or ""
        zone_code = ZONING_NAME_TO_CODE.get(zoning_name)

        # Fallback: try partial matching
        if not zone_code:
            for name, code in ZONING_NAME_TO_CODE.items():
                if name.lower().startswith(zoning_name.lower().split(":")[0].strip().lower()):
                    zone_code = code
                    break

        if not zone_code:
            zone_code = "SR1"  # default assumption

        rules = CTZS_RULES.get(zone_code, CTZS_RULES["SR1"])
        dev_type = _classify_development_type(zone_code)

        # 3. Get biodiversity constraints
        bio_overlaps = []
        try:
            bio_rows = conn.execute(text(f"""
                SELECT pb.cba_category, pb.overlap_pct,
                       pe.vegetation_type, pe.threat_status
                FROM {schema}.property_biodiversity pb
                LEFT JOIN {schema}.property_ecosystems pe ON pb.property_id = pe.property_id
                WHERE pb.property_id = :id
                ORDER BY CASE pb.cba_category
                    WHEN 'PA' THEN 1 WHEN 'CA' THEN 2
                    WHEN 'CBA 1a' THEN 3 WHEN 'CBA 1b' THEN 4 WHEN 'CBA 1c' THEN 5
                    WHEN 'CBA 2' THEN 6 WHEN 'ESA 1' THEN 7 WHEN 'ESA 2' THEN 8
                    WHEN 'ONA' THEN 9
                END
            """), {"id": property_id}).mappings().fetchall()
            bio_overlaps = [dict(r) for r in bio_rows]
        except Exception:
            pass

        # 4. Get heritage sites
        heritage_count = 0
        heritage_constraint = False
        try:
            heritage = conn.execute(text(f"""
                SELECT COUNT(*) as cnt,
                       BOOL_OR(CASE WHEN hs.city_grading IN ('I', 'II', 'III', 'IIIA') THEN TRUE ELSE FALSE END) as has_graded
                FROM {schema}.heritage_sites hs
                WHERE ST_Intersects(hs.geom, (SELECT geom FROM {schema}.properties WHERE id = :id))
            """), {"id": property_id}).mappings().fetchone()
            if heritage:
                heritage_count = int(heritage["cnt"])
                heritage_constraint = bool(heritage["has_graded"])
        except Exception:
            pass

        # 5. Calculate buildable envelope using PostGIS
        # Use minimum setback as uniform negative buffer (simplified v1)
        min_setback = min(
            rules["setback_front"],
            rules["setback_side"] if rules["setback_side"] > 0 else rules["setback_front"],
            rules["setback_rear"]
        )

        buildable_area_sqm = site_area  # start with full site
        no_go_pct = 0.0
        has_no_go = False

        # Check no-go biodiversity zones
        for bio in bio_overlaps:
            cat = bio.get("cba_category", "")
            pct = float(bio.get("overlap_pct") or 0)
            if cat in NO_GO_CATEGORIES:
                no_go_pct += pct
                has_no_go = True

        no_go_pct = min(no_go_pct, 100)

        # Try spatial buildable envelope calculation
        try:
            result = conn.execute(text(f"""
                WITH property AS (
                    SELECT geom FROM {schema}.properties WHERE id = :id
                ),
                setback AS (
                    SELECT ST_Buffer(geom::geography, -:buf)::geometry AS geom
                    FROM property
                ),
                bio_constraint AS (
                    SELECT COALESCE(ST_Union(ba.geom), ST_GeomFromText('GEOMETRYCOLLECTION EMPTY', 4326)) AS geom
                    FROM {schema}.biodiversity_areas ba
                    WHERE ba.cba_category IN ('PA', 'CA', 'CBA 1a', 'CBA 1b')
                    AND ST_Intersects(ba.geom, (SELECT geom FROM property))
                ),
                buildable AS (
                    SELECT CASE
                        WHEN ST_IsEmpty(s.geom) OR s.geom IS NULL THEN NULL
                        WHEN ST_IsEmpty(bc.geom) THEN s.geom
                        ELSE ST_Difference(s.geom, bc.geom)
                    END AS geom
                    FROM setback s, bio_constraint bc
                )
                SELECT
                    ST_Area((SELECT geom FROM property)::geography) AS total_area,
                    CASE WHEN (SELECT geom FROM buildable) IS NOT NULL AND NOT ST_IsEmpty((SELECT geom FROM buildable))
                         THEN ST_Area((SELECT geom FROM buildable)::geography)
                         ELSE 0
                    END AS buildable_area,
                    CASE WHEN (SELECT geom FROM setback) IS NOT NULL AND NOT ST_IsEmpty((SELECT geom FROM setback))
                         THEN ST_Area((SELECT geom FROM setback)::geography)
                         ELSE 0
                    END AS setback_area
            """), {"id": property_id, "buf": min_setback}).mappings().fetchone()

            if result:
                buildable_area_sqm = float(result["buildable_area"] or 0)
                site_area = float(result["total_area"] or site_area)
        except Exception as e:
            logger.warning("Spatial envelope calc failed, using coverage estimate: %s", e)
            # Fallback: estimate from coverage and no-go
            usable_pct = (100 - no_go_pct) / 100.0
            buildable_area_sqm = site_area * usable_pct * 0.8  # 80% after setbacks

        # 6. Calculate development yield
        coverage_pct = rules["coverage_pct"]
        far = rules["far"]
        height_limit = rules["height_limit"]
        max_floors_rule = rules["max_floors"]
        parking_ratio = rules["parking_ratio"]

        # Max footprint is min of buildable envelope and coverage allowance
        max_footprint_sqm = min(buildable_area_sqm, site_area * coverage_pct / 100.0)

        # Max GFA from FAR
        max_gfa_sqm = site_area * far

        # Effective floors
        if height_limit > 0:
            max_floors_from_height = int(height_limit / 3.0)  # assume 3m floor-to-floor
            effective_floors = min(max_floors_from_height, max_floors_rule) if max_floors_rule > 0 else max_floors_from_height
        else:
            effective_floors = max_floors_rule if max_floors_rule > 0 else 1

        # GFA limited by: FAR × site_area, AND footprint × floors
        footprint_gfa = max_footprint_sqm * effective_floors
        max_gfa_sqm = min(max_gfa_sqm, footprint_gfa)

        # Estimated units
        unit_size = AVG_UNIT_SIZES.get(dev_type, 100)
        if dev_type in ("residential_single",):
            estimated_units = max(1, int(max_gfa_sqm / unit_size))
        elif dev_type == "commercial" or dev_type == "industrial":
            estimated_units = max(1, int(max_gfa_sqm / unit_size))
        else:
            estimated_units = max(1, int(max_gfa_sqm / unit_size))

        # Parking
        if dev_type in ("commercial", "industrial"):
            # Commercial: parking_ratio is bays per 100m² GFA
            required_parking = max(1, int(math.ceil(max_gfa_sqm / 100.0 * parking_ratio)))
        else:
            # Residential: parking_ratio is bays per unit
            required_parking = max(1, int(math.ceil(estimated_units * parking_ratio)))

        parking_area_sqm = required_parking * 25  # ~25m² per bay (incl. circulation)

        # Site utilization
        site_utilization_pct = round(max_footprint_sqm / site_area * 100, 1) if site_area > 0 else 0

        # 7. Feasibility flags
        constraints = []
        feasibility = "Feasible"

        # Too small check
        min_erf = rules["min_erf_sqm"]
        if min_erf > 0 and site_area < min_erf:
            constraints.append({
                "type": "too_small",
                "severity": "warning",
                "message": f"Site ({int(site_area)} m²) is below minimum erf size ({int(min_erf)} m²) for {zone_code}",
            })

        # Urban edge check
        if prop.get("inside_urban_edge") is False:
            constraints.append({
                "type": "outside_urban_edge",
                "severity": "critical",
                "message": "Property is outside the urban edge — development severely restricted",
            })
            feasibility = "Restricted"

        # Biodiversity no-go check
        if has_no_go and no_go_pct > 80:
            constraints.append({
                "type": "fully_constrained",
                "severity": "critical",
                "message": f"{int(no_go_pct)}% of site in biodiversity no-go zone (PA/CA/CBA1a/CBA1b)",
            })
            feasibility = "Not Feasible"
        elif has_no_go:
            constraints.append({
                "type": "bio_constraint",
                "severity": "warning",
                "message": f"{int(no_go_pct)}% of site in biodiversity no-go zone — buildable area reduced",
            })
            if feasibility == "Feasible":
                feasibility = "Constrained"

        # Heritage check
        if heritage_constraint:
            constraints.append({
                "type": "heritage",
                "severity": "warning",
                "message": f"{heritage_count} heritage record(s) — Heritage Impact Assessment may be required",
            })
            if feasibility == "Feasible":
                feasibility = "Constrained"

        # Non-developable zones
        if zone_code in ("OS1", "OS2", "TR2"):
            constraints.append({
                "type": "non_developable",
                "severity": "critical",
                "message": f"Zone {zone_code} ({rules['zone_name']}) — not zoned for conventional development",
            })
            feasibility = "Not Feasible"

        # 8. Recommendations
        recommendations = []
        if feasibility == "Feasible" and not constraints:
            recommendations.append({
                "action": "Proceed to detailed site planning and architectural design",
                "priority": 1,
            })
        if has_no_go:
            recommendations.append({
                "action": "Commission Environmental Impact Assessment (EIA) per NEMA regulations",
                "priority": 1,
            })
            recommendations.append({
                "action": "Calculate biodiversity offset requirements using Siteline tools",
                "priority": 2,
            })
        if heritage_constraint:
            recommendations.append({
                "action": "Engage Heritage Consultant for Heritage Impact Assessment (HIA)",
                "priority": 1,
            })
        if prop.get("inside_urban_edge") is False:
            recommendations.append({
                "action": "Consider rezoning application or alternative site within urban edge",
                "priority": 1,
            })
        if dev_type in ("residential_high", "commercial", "mixed_use"):
            recommendations.append({
                "action": "Conduct traffic impact assessment for the proposed density",
                "priority": 2,
            })
        if effective_floors >= 4:
            recommendations.append({
                "action": "Verify fire department access and emergency egress requirements",
                "priority": 2,
            })

        # 9. Unit mix breakdown
        floor_eff = FLOOR_EFFICIENCY.get(dev_type, 0.82)
        net_sellable_sqm = max_gfa_sqm * floor_eff
        unit_mix_template = UNIT_MIX.get(dev_type, UNIT_MIX["residential_medium"])

        unit_mix = []
        total_units = 0
        total_bedrooms = 0
        total_sellable = 0

        for tmpl in unit_mix_template:
            allocated_sqm = net_sellable_sqm * tmpl["share"]
            count = max(1, int(allocated_sqm / tmpl["size_sqm"])) if allocated_sqm >= tmpl["size_sqm"] else 0
            actual_sqm = count * tmpl["size_sqm"]
            total_units += count
            total_bedrooms += count * tmpl["bedrooms"]
            total_sellable += actual_sqm

            unit_mix.append({
                "type": tmpl["type"],
                "label": tmpl["label"],
                "size_sqm": tmpl["size_sqm"],
                "bedrooms": tmpl["bedrooms"],
                "count": count,
                "total_sqm": round(actual_sqm, 1),
                "share_pct": round(tmpl["share"] * 100, 1),
            })

        # Recalculate parking with unit mix
        if dev_type in ("commercial", "industrial"):
            required_parking = max(1, int(math.ceil(max_gfa_sqm / 100.0 * parking_ratio)))
            visitor_parking = 0
        else:
            required_parking = max(1, int(math.ceil(total_units * parking_ratio)))
            visitor_parking = max(1, int(math.ceil(total_units * 0.25)))  # 0.25 visitor bays/unit
            required_parking += visitor_parking

        # Parking solution analysis
        surface_area = required_parking * PARKING_AREA_PER_BAY["surface"]
        basement_area = required_parking * PARKING_AREA_PER_BAY["basement"]
        surface_fits = surface_area <= (buildable_area_sqm * 0.5)  # max 50% of site for surface parking
        parking_solution = "surface" if surface_fits else "basement"

        parking_detail = {
            "total_bays": required_parking,
            "resident_bays": required_parking - visitor_parking,
            "visitor_bays": visitor_parking,
            "recommended_solution": parking_solution,
            "surface_area_sqm": round(surface_area, 1),
            "basement_area_sqm": round(basement_area, 1),
            "basement_levels": max(1, int(math.ceil(basement_area / max_footprint_sqm))) if max_footprint_sqm > 0 else 1,
        }

        # 10. Financial feasibility
        construction_cost_sqm = CONSTRUCTION_COSTS_PER_SQM.get(dev_type, 14000)
        construction_cost = max_gfa_sqm * construction_cost_sqm

        # Basement parking adds cost
        if parking_solution == "basement":
            basement_construction = basement_area * 6500  # R6,500/m² for basement construction
            construction_cost += basement_construction

        professional_fees = construction_cost * PROFESSIONAL_FEES_PCT
        contingency = construction_cost * CONTINGENCY_PCT
        total_dev_cost = construction_cost + professional_fees + contingency

        # Revenue estimate from unit sales
        total_revenue = 0
        for um in unit_mix:
            market_val = MARKET_VALUES_PER_SQM.get(um["type"], 20000)
            um["revenue_per_unit"] = round(market_val * um["size_sqm"])
            um["total_revenue"] = round(um["revenue_per_unit"] * um["count"])
            total_revenue += um["total_revenue"]

        profit = total_revenue - total_dev_cost
        margin_pct = round(profit / total_dev_cost * 100, 1) if total_dev_cost > 0 else 0
        roi_pct = round(profit / total_dev_cost * 100, 1) if total_dev_cost > 0 else 0

        # Density metrics
        site_area_ha = site_area / 10000.0
        density_units_ha = round(total_units / site_area_ha, 1) if site_area_ha > 0 else 0
        density_beds_ha = round(total_bedrooms / site_area_ha, 1) if site_area_ha > 0 else 0
        far_utilization = round(max_gfa_sqm / (site_area * rules["far"]) * 100, 1) if rules["far"] > 0 else 0
        coverage_utilization = round(max_footprint_sqm / (site_area * coverage_pct / 100) * 100, 1) if coverage_pct > 0 else 0

        financials = {
            "construction_cost_per_sqm": construction_cost_sqm,
            "construction_cost": round(construction_cost),
            "professional_fees": round(professional_fees),
            "contingency": round(contingency),
            "total_development_cost": round(total_dev_cost),
            "estimated_revenue": round(total_revenue),
            "estimated_profit": round(profit),
            "margin_pct": margin_pct,
            "roi_pct": roi_pct,
            "viable": margin_pct >= 15,
        }

        return {
            "property_id": property_id,
            "erf_number": prop["erf_number"],
            "suburb": prop["suburb"],
            "zoning": {
                "name": zoning_name,
                "code": zone_code,
                "rules": rules,
            },
            "site": {
                "total_area_sqm": round(site_area, 1),
                "total_area_ha": round(site_area_ha, 4),
                "buildable_area_sqm": round(buildable_area_sqm, 1),
                "site_utilization_pct": site_utilization_pct,
                "inside_urban_edge": prop.get("inside_urban_edge"),
            },
            "yield": {
                "max_footprint_sqm": round(max_footprint_sqm, 1),
                "max_gfa_sqm": round(max_gfa_sqm, 1),
                "net_sellable_sqm": round(net_sellable_sqm, 1),
                "floor_efficiency_pct": round(floor_eff * 100, 1),
                "effective_floors": effective_floors,
                "estimated_units": total_units,
                "total_bedrooms": total_bedrooms,
                "avg_unit_size_sqm": round(net_sellable_sqm / total_units, 1) if total_units > 0 else 0,
                "development_type": dev_type,
            },
            "unit_mix": unit_mix,
            "parking": parking_detail,
            "financials": financials,
            "density": {
                "units_per_ha": density_units_ha,
                "beds_per_ha": density_beds_ha,
                "far_utilization_pct": far_utilization,
                "coverage_utilization_pct": coverage_utilization,
            },
            "constraints": constraints,
            "biodiversity": bio_overlaps,
            "heritage_count": heritage_count,
            "feasibility": feasibility,
            "recommendations": recommendations,
            "note": "Screening-level estimate based on CTZS Table A rules. Actual development rights may differ based on overlay zones, Scheme amendments, and Council discretion.",
        }


def generate_site_plan_geojson(property_id: int) -> dict:
    """
    Generate a GeoJSON FeatureCollection representing the site plan layers.

    Layers:
    - property_boundary: Original parcel polygon
    - setback_zone: Ring between boundary and buildable envelope
    - buildable_envelope: Maximum buildable polygon
    - biodiversity_constraint: CBA/ESA overlap areas (if any)
    """
    engine = _get_engine()

    with engine.connect() as conn:
        schema = _get_schema(conn)

        # Get property
        prop = conn.execute(text(f"""
            SELECT id, erf_number, suburb, zoning_primary,
                   ST_AsGeoJSON(geom)::json AS geometry,
                   ST_Area(geom::geography) AS area_sqm
            FROM {schema}.properties
            WHERE id = :id
        """), {"id": property_id}).mappings().fetchone()

        if not prop:
            return {"error": "Property not found"}

        prop = dict(prop)
        zoning_name = prop.get("zoning_primary") or ""
        zone_code = ZONING_NAME_TO_CODE.get(zoning_name, "SR1")
        # Fallback partial match
        if zone_code == "SR1" and zoning_name:
            for name, code in ZONING_NAME_TO_CODE.items():
                if name.lower().startswith(zoning_name.lower().split(":")[0].strip().lower()):
                    zone_code = code
                    break

        rules = CTZS_RULES.get(zone_code, CTZS_RULES["SR1"])
        min_setback = min(
            rules["setback_front"],
            rules["setback_side"] if rules["setback_side"] > 0 else rules["setback_front"],
            rules["setback_rear"]
        )

        features = []

        # 1. Property boundary
        features.append({
            "type": "Feature",
            "properties": {
                "layer": "property_boundary",
                "label": f"ERF {prop['erf_number']}",
                "area_sqm": round(float(prop["area_sqm"]), 1),
                "style": {"color": "#3b82f6", "weight": 2, "fillOpacity": 0.05},
            },
            "geometry": prop["geometry"],
        })

        # 2. Buildable envelope (negative buffer)
        try:
            envelope = conn.execute(text(f"""
                SELECT ST_AsGeoJSON(
                    ST_Buffer(geom::geography, -:buf)::geometry
                )::json AS geometry,
                ST_Area(ST_Buffer(geom::geography, -:buf)) AS area_sqm
                FROM {schema}.properties WHERE id = :id
            """), {"id": property_id, "buf": min_setback}).mappings().fetchone()

            if envelope and envelope["geometry"]:
                features.append({
                    "type": "Feature",
                    "properties": {
                        "layer": "buildable_envelope",
                        "label": "Buildable Envelope",
                        "area_sqm": round(float(envelope["area_sqm"] or 0), 1),
                        "setback_m": min_setback,
                        "style": {"color": "#22c55e", "weight": 2, "fillColor": "#22c55e", "fillOpacity": 0.15},
                    },
                    "geometry": envelope["geometry"],
                })

                # 3. Setback zone (difference between property and envelope)
                setback_geom = conn.execute(text(f"""
                    SELECT ST_AsGeoJSON(
                        ST_Difference(
                            p.geom,
                            ST_Buffer(p.geom::geography, -:buf)::geometry
                        )
                    )::json AS geometry
                    FROM {schema}.properties p WHERE p.id = :id
                """), {"id": property_id, "buf": min_setback}).mappings().fetchone()

                if setback_geom and setback_geom["geometry"]:
                    features.append({
                        "type": "Feature",
                        "properties": {
                            "layer": "setback_zone",
                            "label": f"Setback ({min_setback}m)",
                            "style": {"color": "#f97316", "weight": 1, "fillColor": "#f97316", "fillOpacity": 0.2, "dashArray": "4 4"},
                        },
                        "geometry": setback_geom["geometry"],
                    })
        except Exception as e:
            logger.warning("Envelope calc failed: %s", e)

        # 4. Biodiversity constraint areas
        try:
            bio_geoms = conn.execute(text(f"""
                SELECT ba.cba_category,
                       ST_AsGeoJSON(ST_Intersection(ba.geom, p.geom))::json AS geometry,
                       ST_Area(ST_Intersection(ba.geom::geography, p.geom::geography)) AS area_sqm
                FROM {schema}.biodiversity_areas ba
                JOIN {schema}.properties p ON ST_Intersects(ba.geom, p.geom)
                WHERE p.id = :id AND ba.cba_category IN ('PA', 'CA', 'CBA 1a', 'CBA 1b', 'CBA 1c', 'CBA 2', 'ESA 1', 'ESA 2')
            """), {"id": property_id}).mappings().fetchall()

            for bg in bio_geoms:
                cat = bg["cba_category"]
                is_nogo = cat in NO_GO_CATEGORIES
                features.append({
                    "type": "Feature",
                    "properties": {
                        "layer": "biodiversity_constraint",
                        "label": cat,
                        "area_sqm": round(float(bg["area_sqm"] or 0), 1),
                        "is_no_go": is_nogo,
                        "style": {
                            "color": "#ef4444" if is_nogo else "#eab308",
                            "weight": 2,
                            "fillColor": "#ef4444" if is_nogo else "#eab308",
                            "fillOpacity": 0.3,
                        },
                    },
                    "geometry": bg["geometry"],
                })
        except Exception as e:
            logger.warning("Bio constraint geom failed: %s", e)

        return {
            "type": "FeatureCollection",
            "features": features,
            "properties": {
                "property_id": property_id,
                "zone_code": zone_code,
            },
        }


# =============================================================================
# Phase 2 — Building Massing (floor plates per level)
# =============================================================================

def generate_massing_geojson(property_id: int) -> dict:
    """
    Generate a GeoJSON FeatureCollection with per-floor building plates.

    Produces:
    - Building footprint polygon (placed within buildable envelope)
    - Per-floor plate polygons with metadata (floor number, GFA, use type)
    - Parking area polygon (surface or basement indicator)

    Floor plates are offset inward slightly per floor to visualize stacking.
    """
    engine = _get_engine()

    with engine.connect() as conn:
        schema = _get_schema(conn)

        prop = conn.execute(text(f"""
            SELECT id, erf_number, suburb, zoning_primary,
                   ST_AsGeoJSON(geom)::json AS geometry,
                   ST_Area(geom::geography) AS area_sqm
            FROM {schema}.properties
            WHERE id = :id
        """), {"id": property_id}).mappings().fetchone()

        if not prop:
            return {"error": "Property not found"}

        prop = dict(prop)
        zoning_name = prop.get("zoning_primary") or ""
        zone_code = ZONING_NAME_TO_CODE.get(zoning_name, "SR1")
        if zone_code == "SR1" and zoning_name:
            for name, code in ZONING_NAME_TO_CODE.items():
                if name.lower().startswith(zoning_name.lower().split(":")[0].strip().lower()):
                    zone_code = code
                    break

        rules = CTZS_RULES.get(zone_code, CTZS_RULES["SR1"])
        dev_type = _classify_development_type(zone_code)
        site_area = float(prop["area_sqm"])

        # Calculate setbacks
        min_setback = min(
            rules["setback_front"],
            rules["setback_side"] if rules["setback_side"] > 0 else rules["setback_front"],
            rules["setback_rear"]
        )

        features = []

        # Property boundary
        features.append({
            "type": "Feature",
            "properties": {
                "layer": "property_boundary",
                "label": f"ERF {prop['erf_number']}",
                "area_sqm": round(site_area, 1),
                "style": {"color": "#3b82f6", "weight": 2, "fillOpacity": 0.05},
            },
            "geometry": prop["geometry"],
        })

        # Get buildable envelope (after setbacks and bio constraints)
        try:
            envelope_row = conn.execute(text(f"""
                WITH property AS (
                    SELECT geom FROM {schema}.properties WHERE id = :id
                ),
                setback AS (
                    SELECT ST_Buffer(geom::geography, -:buf)::geometry AS geom
                    FROM property
                ),
                bio_constraint AS (
                    SELECT COALESCE(ST_Union(ba.geom), ST_GeomFromText('GEOMETRYCOLLECTION EMPTY', 4326)) AS geom
                    FROM {schema}.biodiversity_areas ba
                    WHERE ba.cba_category IN ('PA', 'CA', 'CBA 1a', 'CBA 1b')
                    AND ST_Intersects(ba.geom, (SELECT geom FROM property))
                ),
                buildable AS (
                    SELECT CASE
                        WHEN ST_IsEmpty(s.geom) OR s.geom IS NULL THEN NULL
                        WHEN ST_IsEmpty(bc.geom) THEN s.geom
                        ELSE ST_Difference(s.geom, bc.geom)
                    END AS geom
                    FROM setback s, bio_constraint bc
                )
                SELECT ST_AsGeoJSON(geom)::json AS geometry,
                       ST_Area(geom::geography) AS area_sqm
                FROM buildable
                WHERE geom IS NOT NULL AND NOT ST_IsEmpty(geom)
            """), {"id": property_id, "buf": min_setback}).mappings().fetchone()
        except Exception:
            envelope_row = None

        if not envelope_row or not envelope_row["geometry"]:
            return {
                "type": "FeatureCollection",
                "features": features,
                "properties": {"property_id": property_id, "error": "Could not compute buildable envelope"},
            }

        envelope_geom = envelope_row["geometry"]
        envelope_area = float(envelope_row["area_sqm"])

        # Max footprint from coverage
        coverage_area = site_area * rules["coverage_pct"] / 100.0
        building_footprint_sqm = min(envelope_area, coverage_area)

        # Calculate floors
        far = rules["far"]
        max_gfa = site_area * far
        height_limit = rules["height_limit"]
        max_floors_rule = rules["max_floors"]
        if height_limit > 0:
            floors_from_height = int(height_limit / 3.0)
            effective_floors = min(floors_from_height, max_floors_rule) if max_floors_rule > 0 else floors_from_height
        else:
            effective_floors = max_floors_rule if max_floors_rule > 0 else 1

        # For mixed use: ground floor is commercial, upper floors residential
        is_mixed = dev_type == "mixed_use"
        commercial_floors = 1 if is_mixed else 0
        residential_floors = effective_floors - commercial_floors if is_mixed else effective_floors

        # Building footprint — use the envelope scaled to coverage
        # If envelope is smaller than coverage, use full envelope
        if envelope_area <= coverage_area:
            building_geom = envelope_geom
        else:
            # Scale down — use a slightly larger inward buffer to reduce to coverage
            try:
                scale_row = conn.execute(text(f"""
                    WITH envelope AS (
                        SELECT ST_Buffer(
                            (SELECT ST_Buffer(geom::geography, -:buf)::geometry FROM {schema}.properties WHERE id = :id),
                            'quad_segs=4'
                        ) AS geom
                    )
                    SELECT ST_AsGeoJSON(
                        ST_Buffer(
                            (SELECT geom FROM envelope)::geography,
                            -:inset
                        )::geometry
                    )::json AS geometry
                """), {
                    "id": property_id,
                    "buf": min_setback,
                    "inset": max(0.5, (envelope_area - coverage_area) / (2 * math.sqrt(envelope_area) * 3.14)) if envelope_area > 0 else 0.5,
                }).mappings().fetchone()
                building_geom = scale_row["geometry"] if scale_row and scale_row["geometry"] else envelope_geom
            except Exception:
                building_geom = envelope_geom

        # Setback zone
        features.append({
            "type": "Feature",
            "properties": {
                "layer": "setback_zone",
                "label": f"Setback ({min_setback}m)",
                "style": {"color": "#f97316", "weight": 1, "fillColor": "#f97316", "fillOpacity": 0.15, "dashArray": "4 4"},
            },
            "geometry": envelope_geom,  # The full buildable envelope shows the setback boundary
        })

        # Building footprint (ground floor)
        features.append({
            "type": "Feature",
            "properties": {
                "layer": "building_footprint",
                "label": "Building Footprint",
                "floor": 0,
                "area_sqm": round(building_footprint_sqm, 1),
                "use": "commercial" if is_mixed else dev_type,
                "style": {"color": "#6366f1", "weight": 2, "fillColor": "#6366f1", "fillOpacity": 0.35},
            },
            "geometry": building_geom,
        })

        # Per-floor plates
        floor_colors = [
            "#6366f1", "#8b5cf6", "#a78bfa", "#c4b5fd",  # indigo → violet gradient
            "#818cf8", "#6366f1", "#4f46e5", "#4338ca",
            "#3730a3", "#312e81", "#1e1b4b", "#0f0a3c",
        ]

        for floor_num in range(1, effective_floors):
            # Each upper floor uses the same footprint (simplified — no tapering)
            use_type = "residential" if (is_mixed and floor_num >= commercial_floors) else ("commercial" if is_mixed else dev_type)
            color = floor_colors[min(floor_num, len(floor_colors) - 1)]

            features.append({
                "type": "Feature",
                "properties": {
                    "layer": "floor_plate",
                    "label": f"Floor {floor_num + 1}",
                    "floor": floor_num,
                    "height_m": floor_num * 3.0,
                    "area_sqm": round(building_footprint_sqm, 1),
                    "use": use_type,
                    "style": {"color": color, "weight": 1, "fillColor": color, "fillOpacity": 0.15 + (floor_num * 0.03)},
                },
                "geometry": building_geom,
            })

        # Parking area indicator
        parking_bays = int(math.ceil(
            max_gfa / 100.0 * rules["parking_ratio"]
            if dev_type in ("commercial", "industrial")
            else max_gfa / AVG_UNIT_SIZES.get(dev_type, 80) * rules["parking_ratio"]
        ))
        surface_parking_area = parking_bays * PARKING_AREA_PER_BAY["surface"]
        surface_fits = surface_parking_area <= (envelope_area * 0.5)

        features.append({
            "type": "Feature",
            "properties": {
                "layer": "parking_zone",
                "label": f"Parking ({parking_bays} bays)",
                "parking_type": "surface" if surface_fits else "basement",
                "bays": parking_bays,
                "area_sqm": round(surface_parking_area if surface_fits else parking_bays * PARKING_AREA_PER_BAY["basement"], 1),
                "style": {
                    "color": "#64748b",
                    "weight": 1,
                    "fillColor": "#64748b",
                    "fillOpacity": 0.2,
                    "dashArray": "6 3" if not surface_fits else None,
                },
            },
            "geometry": envelope_geom if surface_fits else building_geom,
        })

        return {
            "type": "FeatureCollection",
            "features": features,
            "properties": {
                "property_id": property_id,
                "zone_code": zone_code,
                "effective_floors": effective_floors,
                "building_footprint_sqm": round(building_footprint_sqm, 1),
                "total_gfa_sqm": round(min(max_gfa, building_footprint_sqm * effective_floors), 1),
                "height_m": effective_floors * 3.0,
            },
        }


# =============================================================================
# Phase 3 — Unit Packing (unit placement per floor)
# =============================================================================

def generate_unit_layout(property_id: int) -> dict:
    """
    Generate a floor-by-floor unit layout with individual unit placements.

    Returns a structured layout (not GeoJSON — coordinate-based for rendering):
    - Per-floor unit grid with positions, sizes, types
    - Corridor/core placement
    - Parking layout (surface grid or basement level)

    Uses a simple rectangular packing algorithm:
    - Calculate buildable rectangle from envelope bounding box
    - Place corridor down the center (double-loaded corridor for efficiency)
    - Pack units on both sides of corridor
    - Place lift/stair cores at ends
    """
    # Get development potential first (contains all needed metrics)
    dev = calculate_development_potential(property_id)
    if "error" in dev:
        return dev

    dev_type = dev["yield"]["development_type"]
    effective_floors = dev["yield"]["effective_floors"]
    unit_mix_data = dev.get("unit_mix", [])
    parking_data = dev.get("parking", {})
    max_footprint = dev["yield"]["max_footprint_sqm"]
    is_mixed = dev_type == "mixed_use"

    # Estimate building dimensions from footprint
    # Assume rectangular building with ~2:1 aspect ratio
    building_width = math.sqrt(max_footprint / 2.0)
    building_length = max_footprint / building_width if building_width > 0 else 0

    # Ensure reasonable proportions
    if building_width < 8:
        building_width = 8
        building_length = max_footprint / building_width if building_width > 0 else 0

    # Core dimensions
    corridor_width = 1.8 if dev_type in ("residential_single", "residential_group") else 2.0
    core_width = 6.0   # lift lobby + stairs
    core_depth = 6.0

    # Usable depth on each side of corridor (double-loaded)
    usable_depth = (building_width - corridor_width) / 2.0
    if usable_depth < 4:
        # Single-loaded corridor for narrow buildings
        usable_depth = building_width - corridor_width
        double_loaded = False
    else:
        double_loaded = True

    # Standard unit depths based on building width
    unit_depth = min(usable_depth, 12.0)  # max 12m deep for natural light

    # Distribute units across floors
    # Flatten unit mix into a queue
    unit_queue = []
    for um in unit_mix_data:
        for _ in range(um["count"]):
            unit_queue.append({
                "type": um["type"],
                "label": um["label"],
                "size_sqm": um["size_sqm"],
                "bedrooms": um["bedrooms"],
            })

    # Build floor layouts
    floors = []
    unit_idx = 0
    total_placed = 0

    for floor_num in range(effective_floors):
        floor_use = "commercial" if (is_mixed and floor_num == 0) else "residential"

        # Available length for units (minus cores at each end)
        available_length = building_length - (2 * core_width)
        if available_length < 3:
            available_length = building_length - core_width

        sides = 2 if double_loaded else 1
        placed_units = []

        # Pack units along the corridor
        for side in range(sides):
            x_offset = 0
            side_label = "north" if side == 0 else "south"

            while x_offset < available_length and unit_idx < len(unit_queue):
                unit = unit_queue[unit_idx]
                # Unit width = area / depth
                unit_width = unit["size_sqm"] / unit_depth
                if unit_width < 3.0:
                    unit_width = 3.0  # minimum 3m frontage

                if x_offset + unit_width > available_length:
                    break  # doesn't fit on this side

                placed_units.append({
                    "type": unit["type"],
                    "label": unit["label"],
                    "bedrooms": unit["bedrooms"],
                    "size_sqm": unit["size_sqm"],
                    "position": {
                        "x": round(core_width + x_offset, 1),
                        "y": round(0 if side == 0 else (unit_depth + corridor_width), 1),
                        "width": round(unit_width, 1),
                        "depth": round(unit_depth, 1),
                    },
                    "side": side_label,
                    "floor": floor_num,
                })

                x_offset += unit_width
                unit_idx += 1
                total_placed += 1

        # Add cores
        cores = [
            {
                "type": "core",
                "label": "Stair/Lift Core",
                "position": {"x": 0, "y": 0, "width": round(core_width, 1), "depth": round(building_width, 1)},
            },
        ]
        if building_length > 30:  # add second core for longer buildings
            cores.append({
                "type": "core",
                "label": "Stair Core",
                "position": {"x": round(building_length - core_width, 1), "y": 0, "width": round(core_width, 1), "depth": round(building_width, 1)},
            })

        floors.append({
            "floor": floor_num,
            "floor_label": f"{'Ground' if floor_num == 0 else f'Floor {floor_num + 1}'}",
            "use": floor_use,
            "height_m": 3.0,
            "elevation_m": floor_num * 3.0,
            "units": placed_units,
            "cores": cores,
            "corridor": {
                "y": round(unit_depth, 1) if double_loaded else 0,
                "width": corridor_width,
                "length": round(building_length, 1),
                "double_loaded": double_loaded,
            },
            "unit_count": len(placed_units),
            "floor_gfa_sqm": round(building_width * building_length, 1),
        })

    # Parking layout
    parking_bays = parking_data.get("total_bays", 0)
    parking_type = parking_data.get("recommended_solution", "surface")

    if parking_type == "surface":
        # Grid of parking bays: 2.5m × 5m bays with 6m aisle
        bay_width = 2.5
        bay_depth = 5.0
        aisle_width = 6.0
        row_depth = bay_depth * 2 + aisle_width  # double row with aisle
        bays_per_row = max(1, int(building_length / bay_width))
        rows_needed = max(1, int(math.ceil(parking_bays / (bays_per_row * 2))))

        parking_layout = {
            "type": "surface",
            "bays": parking_bays,
            "grid": {
                "bay_width": bay_width,
                "bay_depth": bay_depth,
                "aisle_width": aisle_width,
                "bays_per_row": bays_per_row,
                "rows": rows_needed,
                "total_width": round(rows_needed * row_depth, 1),
                "total_length": round(bays_per_row * bay_width, 1),
            },
        }
    else:
        # Basement parking
        bays_per_level = max(1, int(max_footprint / PARKING_AREA_PER_BAY["basement"]))
        basement_levels = max(1, int(math.ceil(parking_bays / bays_per_level)))

        parking_layout = {
            "type": "basement",
            "bays": parking_bays,
            "levels": basement_levels,
            "bays_per_level": bays_per_level,
            "area_per_level_sqm": round(max_footprint, 1),
        }

    return {
        "property_id": property_id,
        "building": {
            "width_m": round(building_width, 1),
            "length_m": round(building_length, 1),
            "footprint_sqm": round(max_footprint, 1),
            "height_m": effective_floors * 3.0,
            "floors": effective_floors,
            "double_loaded_corridor": double_loaded,
        },
        "floors": floors,
        "parking": parking_layout,
        "summary": {
            "total_units_placed": total_placed,
            "total_units_planned": len(unit_queue),
            "placement_efficiency_pct": round(total_placed / len(unit_queue) * 100, 1) if unit_queue else 0,
            "development_type": dev_type,
        },
    }


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python site_plan_engine.py <property_id> [--geojson|--massing|--layout]")
        sys.exit(1)

    pid = int(sys.argv[1])

    if "--massing" in sys.argv:
        result = generate_massing_geojson(pid)
    elif "--layout" in sys.argv:
        result = generate_unit_layout(pid)
    elif "--geojson" in sys.argv:
        result = generate_site_plan_geojson(pid)
    else:
        result = calculate_development_potential(pid)

    print(json.dumps(result, indent=2, default=str))
