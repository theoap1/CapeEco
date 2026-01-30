#!/usr/bin/env python3
"""
Cape Town Eco-Property Intelligence: Biodiversity Calculation Engine

Provides three core functions:
  1. calculate_offset_requirement(erf_number, development_footprint_sqm, suburb=None)
  2. generate_constraint_map(erf_number, suburb=None)
  3. find_matching_conservation_land_bank(required_ha, ecosystem_type)

All calculations are indicative/screening-level only and do not substitute
for a formal Environmental Impact Assessment.
"""

import json
import logging
import os
from contextlib import contextmanager
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

RULES_PATH = Path(__file__).parent.parent / "data" / "processed" / "offset_rules.json"

# Buffer distances (metres) by CBA category for constraint mapping
BUFFER_DISTANCES_M = {
    "PA": 30,
    "CA": 30,
    "CBA 1a": 30,
    "CBA 1b": 30,
    "CBA 1c": 30,
    "CBA 2": 15,
    "ESA 1": 10,
    "ESA 2": 10,
    "ONA": 0,
}


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


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            _conn_string(), pool_size=3, max_overflow=5, pool_pre_ping=True
        )
    return _engine


def load_rules():
    with open(RULES_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalise_cba_key(cba_category: str) -> str:
    """Convert DB enum value to offset_rules.json key.

    DB stores: 'CBA 1a', 'ESA 1', etc.
    JSON keys: 'CBA_1a', 'ESA_1', etc.
    """
    return cba_category.replace(" ", "_")


def _lookup_property(engine, erf_number: str, suburb: str | None = None):
    """Find a property by erf_number (+ optional suburb).

    Returns dict with property columns or None.
    """
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


def _get_biodiversity_overlays(engine, property_id: int):
    """Return all biodiversity designations overlapping this property.

    Ordered by severity (worst first): PA > CA > CBA 1a > CBA 1b > ...
    """
    severity_order = {
        "PA": 0, "CA": 1, "CBA 1a": 2, "CBA 1b": 3, "CBA 1c": 4,
        "CBA 2": 5, "ESA 1": 6, "ESA 2": 7, "ONA": 8,
    }

    query = f"""
        SELECT pb.cba_category, pb.habitat_condition,
               pb.overlap_area_sqm, pb.overlap_pct,
               ba.cba_name, ba.subtype, ba.significance, ba.esa_significance,
               ba.protected_area
        FROM {SCHEMA}.property_biodiversity pb
        JOIN {SCHEMA}.biodiversity_areas ba ON pb.biodiversity_area_id = ba.id
        WHERE pb.property_id = :pid
    """
    with engine.connect() as conn:
        rows = conn.execute(text(query), {"pid": property_id}).mappings().fetchall()

    results = [dict(r) for r in rows]
    results.sort(key=lambda r: severity_order.get(r["cba_category"], 99))
    return results


def _get_ecosystem_overlays(engine, property_id: int):
    """Return ecosystem types overlapping this property, ordered by threat severity."""
    severity = {"CR": 0, "EN": 1, "VU": 2, "LT": 3}

    query = f"""
        SELECT pe.vegetation_type, pe.threat_status,
               pe.overlap_area_sqm, pe.overlap_pct
        FROM {SCHEMA}.property_ecosystems pe
        WHERE pe.property_id = :pid
    """
    with engine.connect() as conn:
        rows = conn.execute(text(query), {"pid": property_id}).mappings().fetchall()

    results = [dict(r) for r in rows]
    results.sort(key=lambda r: severity.get(r["threat_status"], 99))
    return results


# ---------------------------------------------------------------------------
# Function 1: calculate_offset_requirement
# ---------------------------------------------------------------------------

def calculate_offset_requirement(
    erf_number: str,
    development_footprint_sqm: float,
    suburb: str | None = None,
) -> dict:
    """Calculate the biodiversity offset requirement for a proposed development.

    Args:
        erf_number: Property erf number (e.g. '1043', '719', '10-RE').
        development_footprint_sqm: Proposed development footprint in m².
        suburb: Optional suburb to disambiguate erf numbers.

    Returns:
        Dict with offset calculation results.
    """
    engine = get_engine()
    rules = load_rules()

    # --- Locate property ---
    prop = _lookup_property(engine, erf_number, suburb)
    if prop is None:
        return {
            "error": f"Property not found: erf_number={erf_number}"
            + (f", suburb={suburb}" if suburb else ""),
            "erf_number": erf_number,
        }

    footprint_ha = development_footprint_sqm / 10_000
    property_area_sqm = prop["area_sqm"] or 0

    if development_footprint_sqm > property_area_sqm:
        return {
            "error": f"Development footprint ({development_footprint_sqm:.0f} m²) "
            f"exceeds property area ({property_area_sqm:.0f} m²)",
            "erf_number": erf_number,
            "suburb": prop["suburb"],
        }

    # --- Get overlays ---
    bio_overlays = _get_biodiversity_overlays(engine, prop["id"])
    eco_overlays = _get_ecosystem_overlays(engine, prop["id"])
    inside_urban_edge = prop["inside_urban_edge"]

    # If no biodiversity overlays, no offset required
    if not bio_overlays:
        return {
            "erf_number": erf_number,
            "suburb": prop["suburb"],
            "property_area_ha": prop["area_ha"],
            "development_footprint_ha": footprint_ha,
            "designation": None,
            "ecosystem_type": eco_overlays[0]["vegetation_type"] if eco_overlays else None,
            "ecosystem_threat_status": eco_overlays[0]["threat_status"] if eco_overlays else None,
            "is_no_go": False,
            "offset_applicable": False,
            "base_ratio": 0,
            "condition_multiplier": 1.0,
            "urban_edge_adjustment": 1.0,
            "final_ratio": 0,
            "required_offset_ha": 0,
            "trade_down_eligible": False,
            "conservation_land_bank_option": False,
            "offset_cost_estimate_zar": 0,
            "inside_urban_edge": inside_urban_edge,
            "notes": "No biodiversity designation. Standard EIA conditions apply.",
        }

    # --- Use the most restrictive (first) overlay ---
    primary_bio = bio_overlays[0]
    cba_cat = primary_bio["cba_category"]
    cba_key = _normalise_cba_key(cba_cat)
    habitat_condition = primary_bio["habitat_condition"]

    cba_rules = rules["cba_categories"].get(cba_key, {})

    # --- Determine ecosystem threat status ---
    threat_status = None
    vegetation_type = None
    if eco_overlays:
        vegetation_type = eco_overlays[0]["vegetation_type"]
        threat_status = eco_overlays[0]["threat_status"]

    # --- Check no-go ---
    no_go_cats = rules["calculation_engine"]["special_rules"]["no_go_categories"]
    exceptional_cats = rules["calculation_engine"]["special_rules"]["exceptional_only_categories"]

    is_no_go = cba_key in no_go_cats
    is_exceptional = cba_key in exceptional_cats
    no_go_reason = None

    if is_no_go:
        no_go_reason = (
            f"{cba_rules.get('name', cba_cat)}: "
            f"{cba_rules.get('note', 'Development not permitted.')}"
        )

    # CR ecosystem with low remaining extent → flag as potential no-go
    if threat_status == "CR" and not is_no_go:
        cr_warning = rules["calculation_engine"]["special_rules"].get("cr_ecosystem_warning", "")
        if cr_warning:
            if no_go_reason:
                no_go_reason += f" Additionally: {cr_warning}"
            else:
                no_go_reason = f"WARNING: {cr_warning}"

    # --- Calculate ratio ---
    base_ratio = cba_rules.get("base_ratio")

    # If base_ratio is not set (None), fall back to ecosystem threat status ratio.
    # Do NOT fall back when base_ratio is explicitly 0 (e.g. ONA).
    if base_ratio is None and threat_status:
        ts_rules = rules["ecosystem_threat_status_ratios"].get(threat_status, {})
        base_ratio = ts_rules.get("basic_ratio", 0)

    base_ratio = base_ratio or 0

    # Condition multiplier
    condition_mult = 1.0
    if habitat_condition:
        cond_rules = rules["condition_multipliers"].get(habitat_condition, {})
        condition_mult = cond_rules.get("multiplier", 1.0)

    # Urban edge adjustment
    ue_rules = rules["urban_edge_rules"]
    if inside_urban_edge:
        ue_adjustment = ue_rules["inside_urban_edge"]["ratio_adjustment"]
    else:
        ue_adjustment = ue_rules["outside_urban_edge"]["ratio_adjustment"]

    # Final calculation
    final_ratio = base_ratio * condition_mult * ue_adjustment
    required_offset_ha = footprint_ha * final_ratio

    # Trade-down eligibility
    trade_down = bool(
        cba_rules.get("can_trade_down", False) and inside_urban_edge
    )

    # Conservation land bank eligibility
    offset_cats = rules["calculation_engine"]["special_rules"]["offset_required_categories"]
    offset_applicable = cba_key in offset_cats
    clb_eligible = offset_applicable and not is_no_go

    # Cost estimate
    cost_rules = rules["offset_cost_estimation"]
    if clb_eligible:
        # Use conservation land bank midpoint cost
        clb_range = cost_rules["land_acquisition_cost_per_ha"]["conservation_land_bank"]["estimated_range_zar"]
        land_cost_per_ha = sum(clb_range) / 2
    else:
        # Use private land CBA1 midpoint
        priv_range = cost_rules["land_acquisition_cost_per_ha"]["private_land_cba1"]["estimated_range_zar"]
        land_cost_per_ha = sum(priv_range) / 2

    mgmt_per_ha = cost_rules["management_endowment_per_ha"]["estimated_zar"]
    total_cost = required_offset_ha * (land_cost_per_ha + mgmt_per_ha)

    # Compile all biodiversity overlays for reference
    all_designations = [
        {
            "cba_category": o["cba_category"],
            "habitat_condition": o["habitat_condition"],
            "overlap_pct": round(o["overlap_pct"] or 0, 2),
            "cba_name": o["cba_name"],
        }
        for o in bio_overlays
    ]

    notes = []
    if is_no_go:
        notes.append(f"NO-GO: {no_go_reason}")
    elif is_exceptional:
        notes.append(
            f"EXCEPTIONAL CIRCUMSTANCES ONLY: {cba_rules.get('note', '')}"
        )
    elif no_go_reason and no_go_reason.startswith("WARNING"):
        notes.append(no_go_reason)

    if trade_down:
        notes.append(
            "Trade-down eligible: offset may secure higher-priority habitat "
            "outside the urban edge."
        )

    if condition_mult < 1.0 and condition_mult > 0:
        notes.append(
            f"Condition multiplier of {condition_mult} applied "
            f"(habitat condition: {habitat_condition})."
        )

    return {
        "erf_number": erf_number,
        "suburb": prop["suburb"],
        "sg26_code": prop["sg26_code"],
        "property_area_ha": round(prop["area_ha"] or 0, 4),
        "development_footprint_ha": round(footprint_ha, 4),
        "zoning": prop["zoning_primary"],
        "designation": cba_cat,
        "all_designations": all_designations,
        "ecosystem_type": vegetation_type,
        "ecosystem_threat_status": threat_status,
        "habitat_condition": habitat_condition,
        "inside_urban_edge": inside_urban_edge,
        "is_no_go": is_no_go,
        "is_exceptional_only": is_exceptional,
        "offset_applicable": offset_applicable,
        "base_ratio": base_ratio,
        "condition_multiplier": condition_mult,
        "urban_edge_adjustment": ue_adjustment,
        "final_ratio": round(final_ratio, 2),
        "required_offset_ha": round(required_offset_ha, 4),
        "trade_down_eligible": trade_down,
        "conservation_land_bank_option": clb_eligible,
        "offset_cost_estimate_zar": round(total_cost, 2),
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# Function 2: generate_constraint_map
# ---------------------------------------------------------------------------

def generate_constraint_map(
    erf_number: str,
    suburb: str | None = None,
) -> dict:
    """Generate a GeoJSON FeatureCollection showing development constraints.

    Returns a FeatureCollection with features:
      - property_boundary: The parcel polygon
      - cba_overlay: Each biodiversity area overlapping the property
      - buffer_zone: Buffer around each CBA overlay
      - developable_area: Property minus buffer zones

    Args:
        erf_number: Property erf number.
        suburb: Optional suburb for disambiguation.

    Returns:
        GeoJSON FeatureCollection dict.
    """
    engine = get_engine()

    prop = _lookup_property(engine, erf_number, suburb)
    if prop is None:
        return {"error": f"Property not found: {erf_number}"}

    features = []

    # 1. Property boundary
    with engine.connect() as conn:
        row = conn.execute(
            text(f"""
                SELECT ST_AsGeoJSON(geom)::json as geojson,
                       ST_Area(geom::geography) as area_sqm
                FROM {SCHEMA}.properties WHERE id = :pid
            """),
            {"pid": prop["id"]},
        ).mappings().fetchone()

    if row:
        features.append({
            "type": "Feature",
            "properties": {
                "layer": "property_boundary",
                "erf_number": erf_number,
                "suburb": prop["suburb"],
                "area_sqm": round(row["area_sqm"], 2),
                "area_ha": round(row["area_sqm"] / 10000, 4),
                "zoning": prop["zoning_primary"],
            },
            "geometry": row["geojson"],
        })

    # 2. CBA overlays + buffer zones
    with engine.connect() as conn:
        bio_rows = conn.execute(
            text(f"""
                SELECT ba.cba_category, ba.cba_name, ba.habitat_cond,
                       ST_AsGeoJSON(ST_Intersection(p.geom, ba.geom))::json as geojson,
                       ST_Area(ST_Intersection(p.geom, ba.geom)::geography) as overlap_sqm
                FROM {SCHEMA}.properties p
                JOIN {SCHEMA}.property_biodiversity pb ON p.id = pb.property_id
                JOIN {SCHEMA}.biodiversity_areas ba ON pb.biodiversity_area_id = ba.id
                WHERE p.id = :pid
                AND ST_Intersects(p.geom, ba.geom)
            """),
            {"pid": prop["id"]},
        ).mappings().fetchall()

    total_buffer_sqm = 0
    buffer_geojsons = []

    for br in bio_rows:
        cat = br["cba_category"]
        features.append({
            "type": "Feature",
            "properties": {
                "layer": "cba_overlay",
                "cba_category": cat,
                "cba_name": br["cba_name"],
                "habitat_condition": br["habitat_cond"],
                "overlap_sqm": round(br["overlap_sqm"], 2),
            },
            "geometry": br["geojson"],
        })

        # Generate buffer zone (within property boundary)
        buffer_m = BUFFER_DISTANCES_M.get(cat, 0)
        if buffer_m > 0:
            with engine.connect() as conn:
                buf_row = conn.execute(
                    text(f"""
                        SELECT ST_AsGeoJSON(
                            ST_Intersection(
                                p.geom,
                                ST_Buffer(ST_Intersection(p.geom, ba.geom)::geography, :buf_m)::geometry
                            )
                        )::json as geojson,
                        ST_Area(
                            ST_Intersection(
                                p.geom,
                                ST_Buffer(ST_Intersection(p.geom, ba.geom)::geography, :buf_m)::geometry
                            )::geography
                        ) as buffer_sqm
                        FROM {SCHEMA}.properties p
                        JOIN {SCHEMA}.biodiversity_areas ba ON ba.id = :ba_id
                        WHERE p.id = :pid
                        AND ST_Intersects(p.geom, ba.geom)
                    """),
                    {"pid": prop["id"], "ba_id": br.get("ba_id", 0), "buf_m": buffer_m},
                ).mappings().fetchone()

            # Fallback: buffer using the already-computed intersection
            if buf_row is None or buf_row["geojson"] is None:
                with engine.connect() as conn:
                    buf_row = conn.execute(
                        text(f"""
                            WITH cba_clip AS (
                                SELECT ST_Intersection(p.geom, ba.geom) as clipped
                                FROM {SCHEMA}.properties p
                                JOIN {SCHEMA}.property_biodiversity pb ON p.id = pb.property_id
                                JOIN {SCHEMA}.biodiversity_areas ba ON pb.biodiversity_area_id = ba.id
                                WHERE p.id = :pid AND ba.cba_category = :cat
                                LIMIT 1
                            )
                            SELECT ST_AsGeoJSON(
                                ST_Intersection(
                                    (SELECT geom FROM {SCHEMA}.properties WHERE id = :pid),
                                    ST_Buffer(clipped::geography, :buf_m)::geometry
                                )
                            )::json as geojson,
                            ST_Area(
                                ST_Intersection(
                                    (SELECT geom FROM {SCHEMA}.properties WHERE id = :pid),
                                    ST_Buffer(clipped::geography, :buf_m)::geometry
                                )::geography
                            ) as buffer_sqm
                            FROM cba_clip
                        """),
                        {"pid": prop["id"], "cat": cat, "buf_m": buffer_m},
                    ).mappings().fetchone()

            if buf_row and buf_row["geojson"]:
                features.append({
                    "type": "Feature",
                    "properties": {
                        "layer": "buffer_zone",
                        "cba_category": cat,
                        "buffer_m": buffer_m,
                        "buffer_sqm": round(buf_row["buffer_sqm"], 2),
                    },
                    "geometry": buf_row["geojson"],
                })
                total_buffer_sqm += buf_row["buffer_sqm"] or 0
                buffer_geojsons.append(buf_row["geojson"])

    # 3. Developable area (property minus all buffer zones)
    if buffer_geojsons:
        with engine.connect() as conn:
            dev_row = conn.execute(
                text(f"""
                    WITH buffers AS (
                        SELECT ST_Union(
                            ST_Buffer(
                                ST_Intersection(p.geom, ba.geom)::geography,
                                :default_buf
                            )::geometry
                        ) as buf_union
                        FROM {SCHEMA}.properties p
                        JOIN {SCHEMA}.property_biodiversity pb ON p.id = pb.property_id
                        JOIN {SCHEMA}.biodiversity_areas ba ON pb.biodiversity_area_id = ba.id
                        WHERE p.id = :pid
                    )
                    SELECT ST_AsGeoJSON(
                        ST_Difference(p.geom, COALESCE(b.buf_union, ST_GeomFromText('GEOMETRYCOLLECTION EMPTY', 4326)))
                    )::json as geojson,
                    ST_Area(
                        ST_Difference(p.geom, COALESCE(b.buf_union, ST_GeomFromText('GEOMETRYCOLLECTION EMPTY', 4326)))::geography
                    ) as dev_sqm
                    FROM {SCHEMA}.properties p, buffers b
                    WHERE p.id = :pid
                """),
                {"pid": prop["id"], "default_buf": 30},
            ).mappings().fetchone()

        if dev_row and dev_row["geojson"]:
            features.append({
                "type": "Feature",
                "properties": {
                    "layer": "developable_area",
                    "area_sqm": round(dev_row["dev_sqm"], 2),
                    "area_ha": round(dev_row["dev_sqm"] / 10000, 4),
                },
                "geometry": dev_row["geojson"],
            })
    else:
        # No buffers — entire property is developable
        if row:
            features.append({
                "type": "Feature",
                "properties": {
                    "layer": "developable_area",
                    "area_sqm": round(row["area_sqm"], 2),
                    "area_ha": round(row["area_sqm"] / 10000, 4),
                },
                "geometry": row["geojson"],
            })

    # 4. Ecosystem type overlays
    with engine.connect() as conn:
        eco_rows = conn.execute(
            text(f"""
                SELECT et.vegetation_type, et.threat_status,
                       ST_AsGeoJSON(ST_Intersection(p.geom, et.geom))::json as geojson,
                       ST_Area(ST_Intersection(p.geom, et.geom)::geography) as overlap_sqm
                FROM {SCHEMA}.properties p
                JOIN {SCHEMA}.property_ecosystems pe ON p.id = pe.property_id
                JOIN {SCHEMA}.ecosystem_types et ON pe.ecosystem_type_id = et.id
                WHERE p.id = :pid
                AND ST_Intersects(p.geom, et.geom)
            """),
            {"pid": prop["id"]},
        ).mappings().fetchall()

    for er in eco_rows:
        features.append({
            "type": "Feature",
            "properties": {
                "layer": "ecosystem_type",
                "vegetation_type": er["vegetation_type"],
                "threat_status": er["threat_status"],
                "overlap_sqm": round(er["overlap_sqm"], 2),
            },
            "geometry": er["geojson"],
        })

    return {
        "type": "FeatureCollection",
        "properties": {
            "erf_number": erf_number,
            "suburb": prop["suburb"],
            "property_area_sqm": round(prop["area_sqm"] or 0, 2),
            "total_buffer_sqm": round(total_buffer_sqm, 2),
            "developable_area_sqm": round((prop["area_sqm"] or 0) - total_buffer_sqm, 2),
        },
        "features": features,
    }


# ---------------------------------------------------------------------------
# Function 3: find_matching_conservation_land_bank
# ---------------------------------------------------------------------------

def find_matching_conservation_land_bank(
    required_ha: float,
    ecosystem_type: str,
    origin_property_id: int | None = None,
) -> list[dict]:
    """Find conservation land bank parcels matching offset requirements.

    Searches for properties in CBA or PA areas that share the same ecosystem
    type and could serve as offset sites. Since there is no dedicated
    Conservation Land Bank table yet, this queries existing properties that
    are zoned as Open Space and fall within high-priority biodiversity areas.

    Args:
        required_ha: Required offset area in hectares.
        ecosystem_type: Target vegetation type to match.
        origin_property_id: ID of the development property (for distance calc).

    Returns:
        List of candidate offset parcels.
    """
    engine = get_engine()

    # Find properties that:
    # 1. Are in CBA 1a, PA, or CA (high conservation value)
    # 2. Have the matching ecosystem type
    # 3. Are zoned as Open Space or Conservation
    # 4. Have sufficient area
    query = f"""
        SELECT DISTINCT ON (p.id)
            p.id, p.erf_number, p.suburb, p.area_ha,
            p.zoning_primary,
            pb.cba_category, pb.habitat_condition,
            pe.vegetation_type, pe.threat_status,
            ST_X(ST_Centroid(p.geom)) as lon,
            ST_Y(ST_Centroid(p.geom)) as lat
    """

    if origin_property_id:
        query += f""",
            ST_Distance(
                p.geom::geography,
                (SELECT geom::geography FROM {SCHEMA}.properties WHERE id = :origin_id)
            ) / 1000 as distance_km
        """

    query += f"""
        FROM {SCHEMA}.properties p
        JOIN {SCHEMA}.property_biodiversity pb ON p.id = pb.property_id
        JOIN {SCHEMA}.property_ecosystems pe ON p.id = pe.property_id
        WHERE pe.vegetation_type = :eco_type
        AND pb.cba_category IN ('PA', 'CA', 'CBA 1a', 'CBA 1b')
        AND p.area_ha >= :min_ha
        AND p.zoning_primary ILIKE '%%Open Space%%'
    """

    if origin_property_id:
        query += " AND p.id != :origin_id"

    query += " ORDER BY p.id, p.area_ha DESC"

    if origin_property_id:
        query += ", distance_km ASC"

    query += " LIMIT 20"

    params = {
        "eco_type": ecosystem_type,
        "min_ha": required_ha * 0.1,  # Allow parcels at least 10% of required
    }
    if origin_property_id:
        params["origin_id"] = origin_property_id

    with engine.connect() as conn:
        rows = conn.execute(text(query), params).mappings().fetchall()

    rules = load_rules()
    cost_rules = rules["offset_cost_estimation"]
    clb_range = cost_rules["land_acquisition_cost_per_ha"]["conservation_land_bank"]["estimated_range_zar"]
    mgmt_per_ha = cost_rules["management_endowment_per_ha"]["estimated_zar"]

    candidates = []
    for r in rows:
        area = r["area_ha"] or 0
        low_cost = area * (clb_range[0] + mgmt_per_ha)
        high_cost = area * (clb_range[1] + mgmt_per_ha)

        candidate = {
            "property_id": r["id"],
            "erf_number": r["erf_number"],
            "suburb": r["suburb"],
            "area_ha": round(area, 4),
            "cba_category": r["cba_category"],
            "habitat_condition": r["habitat_condition"],
            "vegetation_type": r["vegetation_type"],
            "threat_status": r["threat_status"],
            "zoning": r["zoning_primary"],
            "estimated_cost_range_zar": [round(low_cost, 2), round(high_cost, 2)],
            "coordinates": [round(r["lon"], 6), round(r["lat"], 6)],
        }
        if "distance_km" in r:
            candidate["distance_km"] = round(r["distance_km"], 2)
        candidates.append(candidate)

    return {
        "required_ha": required_ha,
        "ecosystem_type": ecosystem_type,
        "candidates_found": len(candidates),
        "candidates": candidates,
        "note": (
            "These are indicative matches from publicly zoned open-space "
            "properties in high-priority biodiversity areas. Actual conservation "
            "land bank availability must be confirmed with the City of Cape Town "
            "Biodiversity Management Branch."
        ),
    }


# ---------------------------------------------------------------------------
# CLI interface
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(description="Biodiversity Offset Calculator")
    sub = parser.add_subparsers(dest="command")

    # calculate
    calc = sub.add_parser("calculate", help="Calculate offset requirement")
    calc.add_argument("erf_number", help="Property ERF number")
    calc.add_argument("footprint_sqm", type=float, help="Development footprint in m²")
    calc.add_argument("--suburb", help="Suburb (for disambiguation)")

    # map
    cmap = sub.add_parser("map", help="Generate constraint map (GeoJSON)")
    cmap.add_argument("erf_number", help="Property ERF number")
    cmap.add_argument("--suburb", help="Suburb (for disambiguation)")
    cmap.add_argument("--output", "-o", help="Output file path")

    # landbank
    lb = sub.add_parser("landbank", help="Find conservation land bank matches")
    lb.add_argument("required_ha", type=float, help="Required offset in hectares")
    lb.add_argument("ecosystem_type", help="Target vegetation type")

    args = parser.parse_args()

    if args.command == "calculate":
        result = calculate_offset_requirement(
            args.erf_number, args.footprint_sqm, suburb=args.suburb
        )
        print(json.dumps(result, indent=2, default=str))

    elif args.command == "map":
        result = generate_constraint_map(args.erf_number, suburb=args.suburb)
        output = json.dumps(result, indent=2, default=str)
        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
            print(f"Written to {args.output}")
        else:
            print(output)

    elif args.command == "landbank":
        result = find_matching_conservation_land_bank(
            args.required_ha, args.ecosystem_type
        )
        print(json.dumps(result, indent=2, default=str))

    else:
        parser.print_help()
