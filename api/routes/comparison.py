"""Property comparison endpoints."""

import sys
from pathlib import Path

from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy import text

from api.db import get_engine, SCHEMA
from api.auth import get_current_user

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from comparison_engine import compare_radius, compare_suburb, get_construction_costs

router = APIRouter(prefix="/api", tags=["comparison"])


@router.get("/property/{property_id}/compare/radius")
def compare_property_radius(
    property_id: int,
    radius_km: float = Query(1.0, ge=0.1, le=10.0),
    _user: dict = Depends(get_current_user),
):
    """Compare property valuations within a radius."""
    result = compare_radius(property_id, radius_km)
    if result.get("error") == "Property not found":
        raise HTTPException(status_code=404, detail="Property not found")
    return result


@router.get("/property/{property_id}/compare/suburb")
def compare_property_suburb(property_id: int, _user: dict = Depends(get_current_user)):
    """Compare property valuations within the same suburb."""
    result = compare_suburb(property_id)
    if result.get("error") == "Property not found":
        raise HTTPException(status_code=404, detail="Property not found")
    return result


@router.get("/property/{property_id}/construction-cost")
def get_property_construction_cost(property_id: int, _user: dict = Depends(get_current_user)):
    """Get construction cost benchmarks for the property's zoning type."""
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(text(f"""
            SELECT zoning_primary FROM {SCHEMA}.properties WHERE id = :id
        """), {"id": property_id}).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Property not found")
    return get_construction_costs(row["zoning_primary"])
