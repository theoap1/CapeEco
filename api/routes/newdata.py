"""API endpoints for new data sources: load shedding, crime, municipal finance."""

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends

from api.auth import get_current_user

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from loadshedding_engine import calculate_loadshedding_impact
from crime_engine import calculate_crime_risk
from municipal_engine import calculate_municipal_health

router = APIRouter(prefix="/api", tags=["risk-data"])


@router.get("/property/{property_id}/loadshedding")
def get_loadshedding(property_id: int, _user: dict = Depends(get_current_user)):
    """Get load shedding impact assessment for a property."""
    result = calculate_loadshedding_impact(property_id)
    if result.get("error") == "Property not found":
        raise HTTPException(status_code=404, detail="Property not found")
    return result


@router.get("/property/{property_id}/crime")
def get_crime(property_id: int, _user: dict = Depends(get_current_user)):
    """Get crime risk assessment for a property."""
    result = calculate_crime_risk(property_id)
    if result.get("error") == "Property not found":
        raise HTTPException(status_code=404, detail="Property not found")
    return result


@router.get("/property/{property_id}/municipal")
def get_municipal(property_id: int, _user: dict = Depends(get_current_user)):
    """Get municipal infrastructure health assessment for a property."""
    result = calculate_municipal_health(property_id)
    if result.get("error") == "Property not found":
        raise HTTPException(status_code=404, detail="Property not found")
    return result
