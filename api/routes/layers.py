"""Map layer endpoints (viewport-based GeoJSON)."""

from fastapi import APIRouter, Query, Depends
from sqlalchemy import text

from api.db import get_engine, SCHEMA
from api.auth import get_current_user

router = APIRouter(prefix="/api", tags=["layers"])


@router.get("/layers/biodiversity")
def get_biodiversity_layer(
    west: float = Query(...), south: float = Query(...),
    east: float = Query(...), north: float = Query(...),
    _user: dict = Depends(get_current_user),
):
    """Return CBA overlay polygons within the viewport as GeoJSON."""
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT ba.id, ba.cba_category, ba.habitat_cond, ba.area_ha,
                   ST_AsGeoJSON(
                       ST_Intersection(
                           ba.geom,
                           ST_MakeEnvelope(:west, :south, :east, :north, 4326)
                       )
                   )::json AS geometry
            FROM {SCHEMA}.biodiversity_areas ba
            WHERE ST_Intersects(ba.geom, ST_MakeEnvelope(:west, :south, :east, :north, 4326))
            LIMIT 2000
        """), {"west": west, "south": south, "east": east, "north": north}).mappings().fetchall()

    features = []
    for r in rows:
        features.append({
            "type": "Feature",
            "properties": {
                "id": r["id"],
                "cba_category": r["cba_category"],
                "habitat_condition": r["habitat_cond"],
                "area_ha": float(r["area_ha"]) if r["area_ha"] else None,
            },
            "geometry": r["geometry"],
        })

    return {"type": "FeatureCollection", "features": features}


@router.get("/layers/properties")
def get_properties_layer(
    west: float = Query(...), south: float = Query(...),
    east: float = Query(...), north: float = Query(...),
    _user: dict = Depends(get_current_user),
):
    """Return property boundaries within viewport. Only at high zoom levels."""
    area_deg = (east - west) * (north - south)
    if area_deg > 0.01:
        return {"type": "FeatureCollection", "features": [], "note": "Zoom in to see property boundaries"}

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT p.id, p.erf_number, p.suburb, p.zoning_primary, p.area_sqm,
                   ST_AsGeoJSON(p.geom)::json AS geometry
            FROM {SCHEMA}.properties p
            WHERE ST_Intersects(p.geom, ST_MakeEnvelope(:west, :south, :east, :north, 4326))
            LIMIT 500
        """), {"west": west, "south": south, "east": east, "north": north}).mappings().fetchall()

    features = []
    for r in rows:
        features.append({
            "type": "Feature",
            "properties": {
                "id": r["id"],
                "erf_number": r["erf_number"],
                "suburb": r["suburb"],
                "zoning": r["zoning_primary"],
                "area_sqm": float(r["area_sqm"]) if r["area_sqm"] else None,
            },
            "geometry": r["geometry"],
        })

    return {"type": "FeatureCollection", "features": features}


@router.get("/layers/ecosystem-types")
def get_ecosystem_layer(
    west: float = Query(...), south: float = Query(...),
    east: float = Query(...), north: float = Query(...),
    _user: dict = Depends(get_current_user),
):
    """Return ecosystem type polygons within viewport."""
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT et.id, et.vegetation_type, et.threat_status, et.area_ha,
                   ST_AsGeoJSON(
                       ST_Intersection(
                           et.geom,
                           ST_MakeEnvelope(:west, :south, :east, :north, 4326)
                       )
                   )::json AS geometry
            FROM {SCHEMA}.ecosystem_types et
            WHERE ST_Intersects(et.geom, ST_MakeEnvelope(:west, :south, :east, :north, 4326))
            LIMIT 500
        """), {"west": west, "south": south, "east": east, "north": north}).mappings().fetchall()

    features = []
    for r in rows:
        features.append({
            "type": "Feature",
            "properties": {
                "id": r["id"],
                "vegetation_type": r["vegetation_type"],
                "threat_status": r["threat_status"],
                "area_ha": float(r["area_ha"]) if r["area_ha"] else None,
            },
            "geometry": r["geometry"],
        })

    return {"type": "FeatureCollection", "features": features}


@router.get("/layers/heritage")
def get_heritage_layer(
    west: float = Query(...), south: float = Query(...),
    east: float = Query(...), north: float = Query(...),
    _user: dict = Depends(get_current_user),
):
    """Return heritage sites within viewport."""
    area_deg = (east - west) * (north - south)
    if area_deg > 0.005:
        return {"type": "FeatureCollection", "features": [], "note": "Zoom in to see heritage sites"}

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT hs.id, hs.site_name, hs.source, hs.heritage_category,
                   hs.nhra_status, hs.city_grading,
                   ST_AsGeoJSON(hs.geom)::json AS geometry
            FROM {SCHEMA}.heritage_sites hs
            WHERE ST_Intersects(hs.geom, ST_MakeEnvelope(:west, :south, :east, :north, 4326))
            LIMIT 500
        """), {"west": west, "south": south, "east": east, "north": north}).mappings().fetchall()

    features = []
    for r in rows:
        features.append({
            "type": "Feature",
            "properties": {
                "id": r["id"],
                "site_name": r["site_name"],
                "source": r["source"],
                "heritage_category": r["heritage_category"],
                "nhra_status": r["nhra_status"],
                "city_grading": r["city_grading"],
            },
            "geometry": r["geometry"],
        })

    return {"type": "FeatureCollection", "features": features}
