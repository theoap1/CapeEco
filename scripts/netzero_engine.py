#!/usr/bin/env python3
"""
Cape Town Eco-Property Intelligence: Net Zero Feasibility Calculator

Provides three core functions:
  1. calculate_solar_potential(erf_number, suburb=None)
  2. calculate_water_harvesting(erf_number, suburb=None)
  3. netzero_scorecard(erf_number, suburb=None, proposed_gfa_sqm=None)

Uses real Cape Town solar irradiance data (from CCT Smart Facility solar
installations), published rainfall averages by rainfall zone, and SANS 10400-XA
energy performance benchmarks.

All calculations are indicative/screening-level only.
"""

import json
import logging
import math
import os
from pathlib import Path

from sqlalchemy import create_engine, text

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DB_NAME = "capeeco"
DB_USER = os.environ.get("PGUSER", os.environ.get("USER", "postgres"))
DB_HOST = os.environ.get("PGHOST", "localhost")
DB_PORT = os.environ.get("PGPORT", "5432")
DB_PASSWORD = os.environ.get("PGPASSWORD", "")
SCHEMA = "capeeco"

# ---------------------------------------------------------------------------
# Cape Town Solar Constants
#
# Cape Town GHI (Global Horizontal Irradiance): ~1900–2100 kWh/m²/year
# Average peak sun hours (PSH): 5.5 h/day (annual avg across CT)
# Source: SolarGIS, CSIR, Dept of Mineral Resources & Energy SA
#
# Validated against CCT Smart Facility data:
#   - Omni Forum: 5568m² building, 90616 kWh/yr → 16.3 kWh/m²/yr
#   - Gugulethu Depot: 4075m², 82479 kWh/yr → 20.2 kWh/m²/yr
#   - Harare Office: 399m², 11521 kWh/yr → 28.9 kWh/m²/yr
# Avg ~16-20 kWh/m² roof/yr for typical installations at ~15% panel efficiency.
# ---------------------------------------------------------------------------
PEAK_SUN_HOURS = 5.5           # hours/day annual average for Cape Town
PANEL_EFFICIENCY = 0.20        # modern panels ~20% efficiency (2024+)
PANEL_POWER_DENSITY = 200      # W/m² (conservative for 20% eff panels)
SYSTEM_PERFORMANCE_RATIO = 0.80  # accounts for inverter loss, soiling, wiring, temp
ROOF_UTILISATION_FACTOR = 0.60   # % of roof usable for PV (excludes shadows, vents, access)
GRID_EXPORT_FRACTION = 0.30    # typical residential surplus exported to grid
ESKOM_EMISSION_FACTOR = 1.04   # kg CO₂/kWh (Eskom grid 2023 — one of world's highest)

# ---------------------------------------------------------------------------
# Cape Town Rainfall Constants
#
# Cape Town has a Mediterranean climate with winter rainfall (May–Aug).
# Annual averages vary significantly by zone:
#   - Southern suburbs/Constantia: 1000-1200 mm
#   - Table Mountain slopes: 1500+ mm
#   - Cape Flats (Khayelitsha, Mitchell's Plain): 500-600 mm
#   - Atlantic seaboard: 500-600 mm
#   - Northern suburbs (Durbanville, Bellville): 500-600 mm
#   - Kommetjie/Noordhoek valley: 700-800 mm
# Source: CCT Water & Sanitation, SA Weather Service
#
# Mapping suburbs to approximate rainfall zones based on geographic position.
# ---------------------------------------------------------------------------
RAINFALL_ZONES = {
    # Zone: (annual_mm, description)
    "high": (1100, "Southern suburbs, mountain slopes"),
    "medium_high": (800, "Deep South (Noordhoek, Kommetjie, Fish Hoek)"),
    "medium": (650, "Central/inner suburbs"),
    "low": (550, "Cape Flats, Atlantic seaboard, Northern suburbs"),
}

# Suburb → rainfall zone mapping (UPPER CASE keys for matching)
# Based on CCT geographic zones and published rainfall data
SUBURB_RAINFALL_ZONE = {
    # High rainfall — southern suburbs, mountain-adjacent
    "CONSTANTIA": "high", "BISHOPSCOURT": "high", "NEWLANDS": "high",
    "CLAREMONT": "high", "KENILWORTH": "high", "WYNBERG": "high",
    "TOKAI": "high", "KIRSTENBOSCH": "high", "CECILIA": "high",
    "RONDEBOSCH": "high", "MOWBRAY": "high", "OBSERVATORY": "high",
    "HOUT BAY": "high", "CAMPS BAY": "high",
    # Medium-high — deep south
    "NOORDHOEK": "medium_high", "KOMMETJIE": "medium_high",
    "FISH HOEK": "medium_high", "SIMON'S TOWN": "medium_high",
    "SIMONS TOWN": "medium_high", "GLENCAIRN": "medium_high",
    "KALK BAY": "medium_high", "MUIZENBERG": "medium_high",
    "ST JAMES": "medium_high", "SCARBOROUGH": "medium_high",
    "OCEAN VIEW": "medium_high", "SUN VALLEY": "medium_high",
    "CLOVELLY": "medium_high", "LAKESIDE": "medium_high",
    # Medium — central
    "PINELANDS": "medium", "THORNTON": "medium", "GOODWOOD": "medium",
    "PAROW": "medium", "BELLVILLE": "medium", "DURBANVILLE": "medium",
    "EDGEMEAD": "medium", "BOTHASIG": "medium", "PLATTEKLOOF": "medium",
    "STELLENBERG": "medium", "WELGEMOED": "medium",
    "KENRIDGE": "medium", "TYGER VALLEY": "medium",
    "BRACKENFELL": "medium", "KRAAIFONTEIN": "medium",
    "KUILSRIVER": "medium", "KUILS RIVER": "medium",
    "SOMERSET WEST": "medium", "STRAND": "medium",
    "GORDON'S BAY": "medium", "GORDONS BAY": "medium",
    # Low rainfall — cape flats, atlantic coast, north
    "KHAYELITSHA": "low", "MITCHELLS PLAIN": "low", "MITCHELL'S PLAIN": "low",
    "GRASSY PARK": "low", "OTTERY": "low", "PHILIPPI": "low",
    "ATHLONE": "low", "GUGULETHU": "low", "LANGA": "low",
    "NYANGA": "low", "MANENBERG": "low", "HANOVER PARK": "low",
    "LAVENDER HILL": "low", "RETREAT": "low", "STEENBERG": "low",
    "PARKLANDS": "low", "BLOUBERGSTRAND": "low", "TABLE VIEW": "low",
    "MILNERTON": "low", "CENTURY CITY": "low", "MONTAGUE GARDENS": "low",
    "SEA POINT": "low", "GREEN POINT": "low", "MOUILLE POINT": "low",
    "WATERFRONT": "low", "WOODSTOCK": "low", "SALT RIVER": "low",
    "CAPE TOWN": "low", "CITY BOWL": "low",
    "ATLANTIS": "low", "MELKBOSSTRAND": "low", "MAMRE": "low",
    "DUNOON": "low", "JOE SLOVO PARK": "low",
}

RAINWATER_COLLECTION_EFFICIENCY = 0.85  # first-flush diversion + filter losses
STORAGE_LOSS_FACTOR = 0.95              # evaporation + overflow losses

# ---------------------------------------------------------------------------
# SANS 10400-XA / GBCSA Energy Benchmarks (kWh/m²/year by building type)
# Source: SANS 10400-XA:2021, GBCSA Net Zero guidelines
# ---------------------------------------------------------------------------
ENERGY_BENCHMARKS = {
    "residential": {
        "average_consumption_kwh_per_sqm": 80,   # typical SA house
        "efficient_consumption_kwh_per_sqm": 50,  # SANS 10400-XA compliant
        "netzero_target_kwh_per_sqm": 40,         # net zero target
    },
    "commercial": {
        "average_consumption_kwh_per_sqm": 200,
        "efficient_consumption_kwh_per_sqm": 120,
        "netzero_target_kwh_per_sqm": 80,
    },
    "industrial": {
        "average_consumption_kwh_per_sqm": 300,
        "efficient_consumption_kwh_per_sqm": 200,
        "netzero_target_kwh_per_sqm": 150,
    },
}

# SANS 10252-1 water demand (litres/person/day)
WATER_DEMAND_LPCD = 200       # SA average domestic
OCCUPANCY_DENSITY_SQM = 30    # m² GFA per occupant (residential)

# GBCSA Green Star SA rating thresholds
GREENSTAR_THRESHOLDS = {
    "6-star": {"min_score": 85, "label": "World Leadership"},
    "5-star": {"min_score": 65, "label": "South African Excellence"},
    "4-star": {"min_score": 45, "label": "Best Practice"},
    "3-star": {"min_score": 25, "label": "Good Practice"},
}

# ---------------------------------------------------------------------------
# DB helpers (shared pattern with biodiversity_engine.py)
# ---------------------------------------------------------------------------

_engine = None


def _conn_string(dbname=None):
    # Check DATABASE_URL first (Railway deployment)
    db_url = os.environ.get("DATABASE_URL")
    if db_url is None:
        for k, v in os.environ.items():
            if k.strip() == "DATABASE_URL":
                db_url = v
                break
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return db_url
    db = dbname or DB_NAME
    if DB_PASSWORD:
        return f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{db}"
    return f"postgresql://{DB_USER}@{DB_HOST}:{DB_PORT}/{db}"


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            _conn_string(), pool_size=3, max_overflow=5, pool_pre_ping=True
        )
    return _engine


def _lookup_property(engine, erf_number: str, suburb: str | None = None):
    """Find a property by erf_number (+ optional suburb)."""
    query = f"""
        SELECT p.id, p.sg26_code, p.erf_number, p.suburb,
               p.area_sqm, p.area_ha, p.zoning_primary, p.zoning_raw,
               p.centroid_lon, p.centroid_lat,
               pue.inside_urban_edge
        FROM {SCHEMA}.properties p
        LEFT JOIN {SCHEMA}.property_urban_edge pue ON p.id = pue.property_id
        WHERE p.erf_number = :erf
    """
    params = {"erf": erf_number}
    if suburb:
        query += " AND UPPER(p.suburb) = UPPER(:suburb)"
        params["suburb"] = suburb

    query += " LIMIT 1"

    with engine.connect() as conn:
        row = conn.execute(text(query), params).mappings().fetchone()
        return dict(row) if row else None


def _classify_building_type(zoning_primary: str | None) -> str:
    """Map CCT zoning to building type category."""
    if not zoning_primary:
        return "residential"
    z = zoning_primary.upper()
    if any(k in z for k in ("RESIDENTIAL", "HOUSING")):
        return "residential"
    if any(k in z for k in ("INDUSTRIAL", "NOXIOUS")):
        return "industrial"
    if any(k in z for k in ("BUSINESS", "COMMERCIAL", "MIXED USE", "OFFICE", "RETAIL")):
        return "commercial"
    return "residential"


def _get_rainfall_zone(suburb: str | None, lat: float | None = None) -> str:
    """Determine rainfall zone from suburb name, falling back to latitude."""
    if suburb:
        zone = SUBURB_RAINFALL_ZONE.get(suburb.upper())
        if zone:
            return zone

    # Latitude-based fallback for Cape Town
    if lat is not None:
        if lat < -34.1:
            return "medium_high"   # deep south
        if lat < -33.95:
            return "medium"        # central-south
        return "low"               # northern / cape flats

    return "medium"  # conservative default


def _estimate_roof_area(area_sqm: float, zoning_primary: str | None) -> float:
    """Estimate roof/catchment area from property area and zoning.

    Uses coverage ratios from CCT zoning scheme:
    - SR1: max 50% coverage
    - GR1-4: 50-60% coverage
    - GB/MU: 80-100% coverage
    - Industrial: 60-80% coverage
    """
    if not zoning_primary:
        return area_sqm * 0.40  # conservative

    z = zoning_primary.upper()
    if "SINGLE RESIDENTIAL 1" in z:
        return area_sqm * 0.40
    if "SINGLE RESIDENTIAL 2" in z:
        return area_sqm * 0.50
    if "GENERAL RESIDENTIAL" in z:
        return area_sqm * 0.55
    if any(k in z for k in ("BUSINESS", "MIXED USE", "RETAIL")):
        return area_sqm * 0.75
    if "INDUSTRIAL" in z:
        return area_sqm * 0.65
    if "AGRICULTURAL" in z or "RURAL" in z:
        return area_sqm * 0.10
    if "OPEN SPACE" in z:
        return area_sqm * 0.05
    return area_sqm * 0.40


def _estimate_floors(zoning_primary: str | None) -> int:
    """Estimate typical number of floors from zoning.

    Based on CCT zoning scheme height restrictions and typical development:
    - SR1: 1-2 storeys (max 8m) → 1.5 avg
    - SR2: 1 storey (incremental) → 1
    - GR1: 2-3 storeys → 2
    - GR2: 3-4 storeys (max 14m) → 3
    - GR3: 4-5 storeys → 4
    - GR4: 5-8 storeys → 5
    - Business: 3-6 storeys → 4
    - Industrial: 1-2 storeys → 1
    """
    if not zoning_primary:
        return 1

    z = zoning_primary.upper()
    if "SINGLE RESIDENTIAL 1" in z:
        return 2
    if "SINGLE RESIDENTIAL 2" in z:
        return 1
    if "GENERAL RESIDENTIAL 1" in z:
        return 2
    if "GENERAL RESIDENTIAL 2" in z:
        return 3
    if "GENERAL RESIDENTIAL 3" in z:
        return 4
    if "GENERAL RESIDENTIAL 4" in z:
        return 5
    if any(k in z for k in ("BUSINESS", "MIXED USE")):
        return 4
    if "INDUSTRIAL" in z:
        return 1
    return 1


# ---------------------------------------------------------------------------
# Function 1: Solar Potential
# ---------------------------------------------------------------------------

def calculate_solar_potential(erf_number: str, suburb: str | None = None) -> dict:
    """Calculate rooftop solar PV potential for a Cape Town property.

    Uses property area and zoning to estimate roof area, then calculates
    PV system sizing and annual generation based on Cape Town's solar
    irradiance (validated against CCT Smart Facility real-world data).

    Args:
        erf_number: Property ERF number (e.g. "9785", "10-RE").
        suburb: Optional suburb to disambiguate non-unique ERF numbers.

    Returns:
        dict with solar potential metrics, or {"error": ...} on failure.
    """
    engine = get_engine()
    prop = _lookup_property(engine, erf_number, suburb)
    if not prop:
        return {"error": f"Property not found: ERF {erf_number}" + (f" in {suburb}" if suburb else "")}

    area_sqm = prop["area_sqm"]
    if not area_sqm or area_sqm <= 0:
        return {"error": f"Property has no valid area: ERF {erf_number}"}

    zoning = prop["zoning_primary"]
    building_type = _classify_building_type(zoning)
    roof_area = _estimate_roof_area(area_sqm, zoning)

    # PV array sizing
    usable_roof = roof_area * ROOF_UTILISATION_FACTOR
    system_kwp = usable_roof * PANEL_POWER_DENSITY / 1000  # kW peak
    annual_kwh = system_kwp * PEAK_SUN_HOURS * 365 * SYSTEM_PERFORMANCE_RATIO

    # Estimated operational energy demand
    # GFA = roof_area × floors (solar is only from roof, but demand scales with floor area)
    benchmarks = ENERGY_BENCHMARKS[building_type]
    floors = _estimate_floors(zoning)
    estimated_gfa = roof_area * floors
    avg_demand_kwh = estimated_gfa * benchmarks["average_consumption_kwh_per_sqm"]
    efficient_demand_kwh = estimated_gfa * benchmarks["efficient_consumption_kwh_per_sqm"]
    netzero_demand_kwh = estimated_gfa * benchmarks["netzero_target_kwh_per_sqm"]

    # Net zero ratio (generation / demand)
    netzero_ratio_avg = round(annual_kwh / avg_demand_kwh, 2) if avg_demand_kwh > 0 else 0
    netzero_ratio_efficient = round(annual_kwh / efficient_demand_kwh, 2) if efficient_demand_kwh > 0 else 0

    # Grid export potential
    self_consumption_kwh = min(annual_kwh, avg_demand_kwh)
    export_kwh = max(0, annual_kwh - self_consumption_kwh) * GRID_EXPORT_FRACTION

    # Carbon offset
    carbon_offset_kg = round(annual_kwh * ESKOM_EMISSION_FACTOR, 1)
    carbon_offset_tonnes = round(carbon_offset_kg / 1000, 2)

    # Cost estimate (2024 SA solar market: R12,000-18,000/kWp installed)
    install_cost_low = round(system_kwp * 12000)
    install_cost_high = round(system_kwp * 18000)

    # Payback (using City of Cape Town 2024 residential tariff ~R3.50/kWh)
    tariff_per_kwh = 3.50
    annual_savings_zar = annual_kwh * tariff_per_kwh
    payback_years = round(((install_cost_low + install_cost_high) / 2) / annual_savings_zar, 1) if annual_savings_zar > 0 else None

    notes = []
    if netzero_ratio_avg >= 1.0:
        notes.append("Solar generation exceeds average energy demand — Net Zero Energy feasible with PV alone.")
    elif netzero_ratio_efficient >= 1.0:
        notes.append("Net Zero feasible with energy-efficient building design (SANS 10400-XA compliant).")
    else:
        deficit_pct = round((1 - netzero_ratio_efficient) * 100)
        notes.append(f"Solar covers {round(netzero_ratio_efficient * 100)}% of efficient demand. "
                     f"{deficit_pct}% shortfall — consider energy efficiency measures or off-site renewables.")

    if building_type == "industrial":
        notes.append("Industrial buildings typically require additional renewable sources beyond rooftop PV.")

    if system_kwp > 1000:
        notes.append("System >1 MWp — requires NERSA generation licence and CCT grid connection agreement.")
    elif system_kwp > 100:
        notes.append("System >100 kWp — requires CCT embedded generation application.")

    return {
        "erf_number": erf_number,
        "suburb": prop["suburb"],
        "property_area_sqm": round(area_sqm, 1),
        "building_type": building_type,
        "estimated_floors": floors,
        "estimated_gfa_sqm": round(estimated_gfa, 1),
        "estimated_roof_area_sqm": round(roof_area, 1),
        "usable_pv_area_sqm": round(usable_roof, 1),
        "system_size_kwp": round(system_kwp, 2),
        "annual_generation_kwh": round(annual_kwh, 0),
        "annual_demand_average_kwh": round(avg_demand_kwh, 0),
        "annual_demand_efficient_kwh": round(efficient_demand_kwh, 0),
        "netzero_ratio_average": netzero_ratio_avg,
        "netzero_ratio_efficient": netzero_ratio_efficient,
        "netzero_energy_feasible": netzero_ratio_efficient >= 1.0,
        "grid_export_potential_kwh": round(export_kwh, 0),
        "carbon_offset_tonnes_per_year": carbon_offset_tonnes,
        "install_cost_range_zar": [install_cost_low, install_cost_high],
        "estimated_payback_years": payback_years,
        "cct_tariff_assumed_zar_per_kwh": tariff_per_kwh,
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# Function 2: Water Harvesting
# ---------------------------------------------------------------------------

def calculate_water_harvesting(erf_number: str, suburb: str | None = None) -> dict:
    """Calculate rainwater harvesting potential for a Cape Town property.

    Uses property roof area as catchment, suburb-based rainfall zone data,
    and SANS 10252-1 water demand benchmarks.

    Args:
        erf_number: Property ERF number.
        suburb: Optional suburb for disambiguation and rainfall zone lookup.

    Returns:
        dict with water harvesting metrics, or {"error": ...} on failure.
    """
    engine = get_engine()
    prop = _lookup_property(engine, erf_number, suburb)
    if not prop:
        return {"error": f"Property not found: ERF {erf_number}" + (f" in {suburb}" if suburb else "")}

    area_sqm = prop["area_sqm"]
    if not area_sqm or area_sqm <= 0:
        return {"error": f"Property has no valid area: ERF {erf_number}"}

    zoning = prop["zoning_primary"]
    building_type = _classify_building_type(zoning)
    roof_area = _estimate_roof_area(area_sqm, zoning)

    # Rainfall zone
    rainfall_zone = _get_rainfall_zone(prop["suburb"], prop["centroid_lat"])
    annual_rainfall_mm, zone_description = RAINFALL_ZONES[rainfall_zone]

    # Harvestable water
    # Formula: catchment_area_m² × rainfall_m × collection_efficiency × storage_efficiency
    annual_harvest_kl = (
        roof_area * (annual_rainfall_mm / 1000)
        * RAINWATER_COLLECTION_EFFICIENCY
        * STORAGE_LOSS_FACTOR
    )

    # Monthly distribution (Cape Town winter rainfall pattern)
    # Percentage of annual rainfall by month (based on SA Weather Service data)
    monthly_pct = {
        "Jan": 0.02, "Feb": 0.02, "Mar": 0.03, "Apr": 0.07,
        "May": 0.13, "Jun": 0.17, "Jul": 0.18, "Aug": 0.14,
        "Sep": 0.09, "Oct": 0.06, "Nov": 0.05, "Dec": 0.04,
    }
    monthly_harvest_kl = {
        month: round(annual_harvest_kl * pct, 2) for month, pct in monthly_pct.items()
    }

    # Water demand estimate (SANS 10252-1)
    floors = _estimate_floors(zoning)
    estimated_gfa = roof_area * floors
    if building_type == "residential":
        occupants = max(1, estimated_gfa / OCCUPANCY_DENSITY_SQM)
        daily_demand_litres = occupants * WATER_DEMAND_LPCD
    elif building_type == "commercial":
        occupants = max(1, estimated_gfa / 15)  # 15 m²/person for offices
        daily_demand_litres = occupants * 50     # 50 L/person/day office
    else:
        # Industrial — highly variable, use conservative 5 L/m²/day
        daily_demand_litres = estimated_gfa * 5

    annual_demand_kl = daily_demand_litres * 365 / 1000
    demand_met_pct = round((annual_harvest_kl / annual_demand_kl) * 100, 1) if annual_demand_kl > 0 else 0

    # Recommended tank size (capture 2 months of peak winter harvest)
    peak_months_harvest = sum(sorted(monthly_harvest_kl.values(), reverse=True)[:2])
    recommended_tank_kl = math.ceil(peak_months_harvest)

    # Cape Town municipal water tariff (2024/25): ~R45/kl for domestic >10.5 kl/month
    water_tariff_per_kl = 45.0
    annual_savings_zar = round(min(annual_harvest_kl, annual_demand_kl) * water_tariff_per_kl)

    # Tank cost estimate (JoJo tanks: ~R2,500/kl for 5kl tanks)
    tank_cost_per_kl = 2500
    tank_cost_estimate = round(recommended_tank_kl * tank_cost_per_kl)

    notes = []
    if demand_met_pct >= 100:
        notes.append("Rainwater harvesting can meet 100% of estimated water demand.")
    elif demand_met_pct >= 50:
        notes.append(f"Rainwater can supplement {demand_met_pct:.0f}% of water demand. "
                     "Consider greywater recycling for remaining demand.")
    else:
        notes.append(f"Rainwater covers only {demand_met_pct:.0f}% of demand. "
                     "Building-scale water recycling (greywater + blackwater) recommended.")

    if rainfall_zone == "low":
        notes.append("Property is in a low-rainfall zone. Water efficiency measures are critical.")

    # Day Zero resilience note
    notes.append(f"Recommended tank provides {recommended_tank_kl} kl buffer "
                 f"(~{round(recommended_tank_kl * 1000 / daily_demand_litres)} days supply at current demand).")

    return {
        "erf_number": erf_number,
        "suburb": prop["suburb"],
        "property_area_sqm": round(area_sqm, 1),
        "building_type": building_type,
        "estimated_roof_catchment_sqm": round(roof_area, 1),
        "rainfall_zone": rainfall_zone,
        "rainfall_zone_description": zone_description,
        "annual_rainfall_mm": annual_rainfall_mm,
        "annual_harvestable_kl": round(annual_harvest_kl, 1),
        "monthly_harvest_kl": monthly_harvest_kl,
        "annual_demand_kl": round(annual_demand_kl, 1),
        "demand_met_pct": demand_met_pct,
        "recommended_tank_size_kl": recommended_tank_kl,
        "tank_cost_estimate_zar": tank_cost_estimate,
        "annual_savings_zar": annual_savings_zar,
        "water_tariff_assumed_zar_per_kl": water_tariff_per_kl,
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# Function 3: Net Zero Scorecard
# ---------------------------------------------------------------------------

def netzero_scorecard(
    erf_number: str,
    suburb: str | None = None,
    proposed_gfa_sqm: float | None = None,
) -> dict:
    """Generate a Net Zero feasibility scorecard with GBCSA Green Star rating.

    Aggregates solar potential, water harvesting, and biodiversity data
    into a unified score mapped to GBCSA Green Star SA equivalents.

    Args:
        erf_number: Property ERF number.
        suburb: Optional suburb.
        proposed_gfa_sqm: Optional proposed gross floor area. If not provided,
            estimated from property area and zoning.

    Returns:
        dict with scorecard, or {"error": ...} on failure.
    """
    # Get solar and water results
    solar = calculate_solar_potential(erf_number, suburb)
    if "error" in solar:
        return solar

    water = calculate_water_harvesting(erf_number, suburb)
    if "error" in water:
        return water

    # Get biodiversity data
    engine = get_engine()
    prop = _lookup_property(engine, erf_number, suburb)
    building_type = _classify_building_type(prop["zoning_primary"])

    # Biodiversity score from DB
    bio_data = _get_biodiversity_summary(engine, prop["id"])

    # --- Scoring (out of 100) ---
    scores = {}

    # 1. Energy (max 35 points)
    # Scaled so that only truly net-positive buildings (>150%) get full marks.
    # This differentiates SR1 (high ratio) from GR4 (low ratio — roof can't serve all floors).
    nz_ratio = solar["netzero_ratio_efficient"]
    if nz_ratio >= 1.5:
        scores["energy"] = 35
    elif nz_ratio >= 1.2:
        scores["energy"] = 30 + round((nz_ratio - 1.2) / 0.3 * 5)
    elif nz_ratio >= 1.0:
        scores["energy"] = 25 + round((nz_ratio - 1.0) / 0.2 * 5)
    elif nz_ratio >= 0.75:
        scores["energy"] = 18 + round((nz_ratio - 0.75) / 0.25 * 7)
    elif nz_ratio >= 0.5:
        scores["energy"] = 10 + round((nz_ratio - 0.5) / 0.25 * 8)
    elif nz_ratio >= 0.25:
        scores["energy"] = 5 + round((nz_ratio - 0.25) / 0.25 * 5)
    else:
        scores["energy"] = round(nz_ratio / 0.25 * 5)

    # 2. Water (max 25 points)
    water_pct = water["demand_met_pct"]
    if water_pct >= 100:
        scores["water"] = 25
    elif water_pct >= 50:
        scores["water"] = round(15 + (water_pct - 50) / 50 * 10)
    else:
        scores["water"] = round(water_pct / 50 * 15)

    # 3. Biodiversity / Ecology (max 20 points)
    if bio_data["designation"] is None:
        # No biodiversity constraints — full points for unconstrained development
        scores["ecology"] = 15
    elif bio_data["is_no_go"]:
        # Cannot develop — ecology score depends on whether they respect the constraint
        scores["ecology"] = 20  # maximum if site is preserved
    elif bio_data["offset_applicable"]:
        scores["ecology"] = 10  # partial — offset needed
    else:
        scores["ecology"] = 12

    # 4. Location & Transport (max 10 points)
    inside_urban_edge = prop.get("inside_urban_edge")
    if inside_urban_edge:
        scores["location"] = 8  # urban infill is better for transport/density
    else:
        scores["location"] = 3  # outside urban edge = car dependent

    # 5. Materials & Innovation potential (max 10 points)
    # Baseline score — actual score depends on design choices
    scores["materials_innovation"] = 5

    total_score = sum(scores.values())

    # Map to Green Star rating
    rating = None
    rating_label = None
    for star, info in sorted(GREENSTAR_THRESHOLDS.items(), key=lambda x: x[1]["min_score"], reverse=True):
        if total_score >= info["min_score"]:
            rating = star
            rating_label = info["label"]
            break

    if rating is None:
        rating = "Below rated"
        rating_label = "Does not meet minimum Green Star threshold"

    # Recommendations
    recommendations = []
    if scores["energy"] < 30:
        recommendations.append("Install maximum rooftop PV and consider SANS 10400-XA compliant building envelope.")
    if scores["water"] < 20:
        recommendations.append("Install rainwater harvesting and greywater recycling systems.")
    if bio_data["offset_applicable"]:
        recommendations.append(f"Biodiversity offset required: {bio_data['designation']}. "
                               "Engage Environmental Assessment Practitioner (EAP).")
    if bio_data["is_no_go"]:
        recommendations.append(f"Site is {bio_data['designation']} — development not permitted. "
                               "Seek alternative sites.")
    if not inside_urban_edge:
        recommendations.append("Property is outside the urban edge. Development requires strong motivation "
                               "and is unlikely to achieve high sustainability ratings.")
    if total_score < 45:
        recommendations.append("Consider energy-efficient design (double glazing, insulation, heat pumps) "
                               "to improve score.")

    # Missing components for net zero certification
    missing_for_netzero = []
    if solar["netzero_ratio_efficient"] < 1.0:
        missing_for_netzero.append("Insufficient on-site renewable energy generation")
    if water["demand_met_pct"] < 50:
        missing_for_netzero.append("Inadequate water independence")
    if bio_data["is_no_go"]:
        missing_for_netzero.append("Site is a no-go biodiversity area")

    return {
        "erf_number": erf_number,
        "suburb": prop["suburb"],
        "property_area_sqm": round(prop["area_sqm"], 1),
        "building_type": building_type,
        "scores": scores,
        "total_score": total_score,
        "max_score": 100,
        "greenstar_rating": rating,
        "greenstar_label": rating_label,
        "solar_summary": {
            "system_kwp": solar["system_size_kwp"],
            "annual_kwh": solar["annual_generation_kwh"],
            "netzero_ratio": solar["netzero_ratio_efficient"],
            "carbon_offset_tonnes": solar["carbon_offset_tonnes_per_year"],
        },
        "water_summary": {
            "annual_harvest_kl": water["annual_harvestable_kl"],
            "demand_met_pct": water["demand_met_pct"],
            "recommended_tank_kl": water["recommended_tank_size_kl"],
        },
        "biodiversity_summary": bio_data,
        "recommendations": recommendations,
        "missing_for_netzero": missing_for_netzero,
        "note": "Scores are indicative only. Formal GBCSA certification requires "
                "registered Green Star AP assessment with full building design documentation.",
    }


def _get_biodiversity_summary(engine, property_id: int) -> dict:
    """Get biodiversity designation summary for a property."""
    query = f"""
        SELECT pb.cba_category, pb.habitat_condition, pb.overlap_pct
        FROM {SCHEMA}.property_biodiversity pb
        WHERE pb.property_id = :pid
        ORDER BY CASE pb.cba_category
            WHEN 'PA' THEN 1 WHEN 'CA' THEN 2
            WHEN 'CBA 1a' THEN 3 WHEN 'CBA 1b' THEN 4 WHEN 'CBA 1c' THEN 5
            WHEN 'CBA 2' THEN 6 WHEN 'ESA 1' THEN 7 WHEN 'ESA 2' THEN 8
            WHEN 'ONA' THEN 9
        END
        LIMIT 1
    """
    no_go_categories = {"PA", "CA", "CBA 1a"}
    offset_categories = {"CBA 1b", "CBA 1c", "CBA 2", "ESA 1", "ESA 2"}

    with engine.connect() as conn:
        row = conn.execute(text(query), {"pid": property_id}).mappings().fetchone()

    if not row:
        return {
            "designation": None,
            "is_no_go": False,
            "offset_applicable": False,
        }

    cat = row["cba_category"]
    return {
        "designation": cat,
        "habitat_condition": row["habitat_condition"],
        "overlap_pct": round(float(row["overlap_pct"]), 1) if row["overlap_pct"] else None,
        "is_no_go": cat in no_go_categories,
        "offset_applicable": cat in offset_categories,
    }


# ---------------------------------------------------------------------------
# CLI interface
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import pprint

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Net Zero Feasibility Calculator")
    parser.add_argument("function", choices=["solar", "water", "scorecard"])
    parser.add_argument("erf_number", help="Property ERF number")
    parser.add_argument("--suburb", help="Suburb name")
    parser.add_argument("--gfa", type=float, help="Proposed GFA in sqm (scorecard only)")

    args = parser.parse_args()

    if args.function == "solar":
        result = calculate_solar_potential(args.erf_number, args.suburb)
    elif args.function == "water":
        result = calculate_water_harvesting(args.erf_number, args.suburb)
    elif args.function == "scorecard":
        result = netzero_scorecard(args.erf_number, args.suburb, args.gfa)

    pprint.pprint(result)
