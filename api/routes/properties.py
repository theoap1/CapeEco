"""Property detail and analysis endpoints."""

import sys
from pathlib import Path

from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy import text

from api.db import get_engine, SCHEMA
from api.auth import get_current_user

# Import engines
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from biodiversity_engine import calculate_offset_requirement, generate_constraint_map
from netzero_engine import calculate_solar_potential, calculate_water_harvesting, netzero_scorecard
from site_plan_engine import calculate_development_potential, generate_site_plan_geojson, generate_massing_geojson, generate_unit_layout

router = APIRouter(prefix="/api", tags=["properties"])


@router.get("/property/{property_id}")
def get_property(property_id: int, _user: dict = Depends(get_current_user)):
    """Get full property details + GeoJSON geometry."""
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(text(f"""
            SELECT p.id, p.erf_number, p.sg26_code, p.suburb, p.street_name,
                   p.street_type, p.address_number, p.full_address,
                   p.area_sqm, p.area_ha, p.zoning_primary, p.zoning_raw,
                   p.centroid_lon, p.centroid_lat,
                   pue.inside_urban_edge,
                   ST_AsGeoJSON(p.geom)::json AS geometry
            FROM {SCHEMA}.properties p
            LEFT JOIN {SCHEMA}.property_urban_edge pue ON p.id = pue.property_id
            WHERE p.id = :id
        """), {"id": property_id}).mappings().fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Property not found")

        result = dict(row)

        bio_rows = conn.execute(text(f"""
            SELECT pb.cba_category, pb.habitat_condition, pb.overlap_pct,
                   pe.vegetation_type, pe.threat_status
            FROM {SCHEMA}.property_biodiversity pb
            LEFT JOIN {SCHEMA}.property_ecosystems pe ON pb.property_id = pe.property_id
            WHERE pb.property_id = :id
            ORDER BY CASE pb.cba_category
                WHEN 'PA' THEN 1 WHEN 'CA' THEN 2
                WHEN 'CBA 1a' THEN 3 WHEN 'CBA 1b' THEN 4 WHEN 'CBA 1c' THEN 5
                WHEN 'CBA 2' THEN 6 WHEN 'ESA 1' THEN 7 WHEN 'ESA 2' THEN 8
                WHEN 'ONA' THEN 9
            END
        """), {"id": property_id}).mappings().fetchall()

        result["biodiversity"] = [dict(r) for r in bio_rows]

        heritage = conn.execute(text(f"""
            SELECT hs.site_name, hs.source, hs.heritage_category,
                   hs.nhra_status, hs.city_grading,
                   hs.resource_type_1, hs.architectural_style, hs.period,
                   hs.street_address
            FROM {SCHEMA}.heritage_sites hs
            WHERE ST_Intersects(hs.geom, (SELECT geom FROM {SCHEMA}.properties WHERE id = :id))
            LIMIT 5
        """), {"id": property_id}).mappings().fetchall()

        result["heritage"] = [dict(r) for r in heritage]

        return result


def _lookup_erf(property_id):
    """Get erf_number and suburb for a property_id."""
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(text(f"""
            SELECT erf_number, suburb, area_sqm FROM {SCHEMA}.properties WHERE id = :id
        """), {"id": property_id}).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Property not found")
    return dict(row)


@router.get("/property/{property_id}/biodiversity")
def get_biodiversity_analysis(
    property_id: int,
    footprint_sqm: float = Query(None),
    _user: dict = Depends(get_current_user),
):
    """Run biodiversity offset calculation."""
    row = _lookup_erf(property_id)
    fp = footprint_sqm or (row["area_sqm"] * 0.4)
    return calculate_offset_requirement(row["erf_number"], fp, suburb=row["suburb"])


@router.get("/property/{property_id}/netzero")
def get_netzero_analysis(property_id: int, _user: dict = Depends(get_current_user)):
    """Run net zero scorecard."""
    row = _lookup_erf(property_id)
    return netzero_scorecard(row["erf_number"], suburb=row["suburb"])


@router.get("/property/{property_id}/solar")
def get_solar_analysis(property_id: int, _user: dict = Depends(get_current_user)):
    """Run solar potential calculation."""
    row = _lookup_erf(property_id)
    return calculate_solar_potential(row["erf_number"], suburb=row["suburb"])


@router.get("/property/{property_id}/water")
def get_water_analysis(property_id: int, _user: dict = Depends(get_current_user)):
    """Run water harvesting calculation."""
    row = _lookup_erf(property_id)
    return calculate_water_harvesting(row["erf_number"], suburb=row["suburb"])


@router.get("/property/{property_id}/constraint-map")
def get_constraint_map(property_id: int, _user: dict = Depends(get_current_user)):
    """Generate GeoJSON constraint map for a property."""
    row = _lookup_erf(property_id)
    return generate_constraint_map(row["erf_number"], suburb=row["suburb"])


@router.get("/property/{property_id}/development-potential")
def get_development_potential(property_id: int, _user: dict = Depends(get_current_user)):
    """Calculate development potential including buildable envelope, yield, and constraints."""
    return calculate_development_potential(property_id)


@router.get("/property/{property_id}/site-plan")
def get_site_plan(property_id: int, _user: dict = Depends(get_current_user)):
    """Generate GeoJSON site plan for map rendering."""
    return generate_site_plan_geojson(property_id)


@router.get("/property/{property_id}/massing")
def get_massing(property_id: int, _user: dict = Depends(get_current_user)):
    """Generate GeoJSON massing with floor plates for map rendering."""
    return generate_massing_geojson(property_id)


@router.get("/property/{property_id}/unit-layout")
def get_unit_layout(property_id: int, _user: dict = Depends(get_current_user)):
    """Generate floor-by-floor unit layout with parking."""
    return generate_unit_layout(property_id)
