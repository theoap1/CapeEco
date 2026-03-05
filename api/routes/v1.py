"""Public API v1 — Bearer token auth, rate limiting, unified analysis."""

import os
import sys
import time
from collections import defaultdict
from enum import Enum
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query, HTTPException, Header, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text

from api.db import get_engine, SCHEMA
from api.routes.reports import _build_zoning_analysis, _safe_float, get_property_report

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from biodiversity_engine import (
    calculate_offset_requirement,
    generate_constraint_map,
    find_matching_conservation_land_bank,
)
from netzero_engine import calculate_solar_potential, calculate_water_harvesting, netzero_scorecard

router = APIRouter(prefix="/api/v1", tags=["v1"])

# ---------------------------------------------------------------------------
# API Key management
# ---------------------------------------------------------------------------
API_KEYS_RAW = os.environ.get("SITELINE_API_KEYS", os.environ.get("CAPEECO_API_KEYS", ""))
API_KEYS: dict[str, str] = {}
for entry in API_KEYS_RAW.split(","):
    entry = entry.strip()
    if ":" in entry:
        k, tier = entry.split(":", 1)
        API_KEYS[k.strip()] = tier.strip()

if not API_KEYS:
    API_KEYS["demo-key-siteline-2026"] = "free"

RATE_LIMITS = {"free": 100, "paid": 10_000}


class _RateLimiter:
    """Simple in-memory sliding-window rate limiter per API key."""

    def __init__(self):
        self._counters: dict[str, list[float]] = defaultdict(list)

    def check(self, api_key: str, tier: str) -> tuple[bool, int]:
        now = time.time()
        window = 86_400
        limit = RATE_LIMITS.get(tier, 100)
        times = self._counters[api_key]
        cutoff = now - window
        self._counters[api_key] = [t for t in times if t > cutoff]
        times = self._counters[api_key]
        if len(times) >= limit:
            return False, 0
        times.append(now)
        return True, limit - len(times)


_rate_limiter = _RateLimiter()


def _verify_api_key(authorization: str = Header(None)) -> tuple[str, str]:
    """Dependency: extract and verify Bearer token. Returns (key, tier)."""
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail={"error": "missing_api_key", "message": "Include Authorization: Bearer <api_key> header"},
        )
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_auth_format", "message": "Use Authorization: Bearer <api_key>"},
        )
    key = parts[1]
    tier = API_KEYS.get(key)
    if tier is None:
        raise HTTPException(
            status_code=403,
            detail={"error": "invalid_api_key", "message": "API key not recognised"},
        )
    allowed, remaining = _rate_limiter.check(key, tier)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": f"Daily limit of {RATE_LIMITS.get(tier, 100)} requests exceeded.",
                "tier": tier,
            },
        )
    return key, tier


# ---------------------------------------------------------------------------
# Helper: resolve property
# ---------------------------------------------------------------------------
def _resolve_property(erf_number: str = None, address: str = None, suburb: str = None):
    engine = get_engine()
    with engine.connect() as conn:
        if erf_number:
            q = f"""
                SELECT p.id, p.erf_number, p.suburb, p.area_sqm, p.area_ha,
                       p.zoning_primary, p.centroid_lon, p.centroid_lat,
                       pue.inside_urban_edge
                FROM {SCHEMA}.properties p
                LEFT JOIN {SCHEMA}.property_urban_edge pue ON p.id = pue.property_id
                WHERE p.erf_number = :erf
            """
            params = {"erf": erf_number}
            if suburb:
                q += " AND p.suburb ILIKE :suburb"
                params["suburb"] = suburb
            q += " LIMIT 1"
            row = conn.execute(text(q), params).mappings().fetchone()
        elif address:
            row = conn.execute(text(f"""
                SELECT DISTINCT ON (p.id)
                       p.id, p.erf_number, p.suburb, p.area_sqm, p.area_ha,
                       p.zoning_primary, p.centroid_lon, p.centroid_lat,
                       pue.inside_urban_edge
                FROM {SCHEMA}.address_points ap
                JOIN {SCHEMA}.properties p ON ST_Within(ap.geom, p.geom)
                LEFT JOIN {SCHEMA}.property_urban_edge pue ON p.id = pue.property_id
                WHERE ap.full_address ILIKE :pattern
                ORDER BY p.id
                LIMIT 1
            """), {"pattern": f"%{address.strip()}%"}).mappings().fetchone()
        else:
            raise HTTPException(status_code=422, detail={
                "error": "missing_identifier",
                "message": "Provide erf_number or address",
            })

    if not row:
        raise HTTPException(status_code=404, detail={
            "error": "property_not_found",
            "message": "No matching property found in the City of Cape Town cadastral data",
        })

    lat = _safe_float(row["centroid_lat"])
    lon = _safe_float(row["centroid_lon"])
    if lat and lon:
        if not (-34.4 <= lat <= -33.4 and 18.2 <= lon <= 19.0):
            raise HTTPException(status_code=422, detail={
                "error": "outside_cct_boundary",
                "message": "Property coordinates fall outside the City of Cape Town municipal boundary",
            })

    return dict(row)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class BuildingType(str, Enum):
    residential = "residential"
    commercial = "commercial"
    industrial = "industrial"


class AnalyzeRequest(BaseModel):
    erf_number: Optional[str] = Field(None, description="ERF number")
    address: Optional[str] = Field(None, description="Street address to geocode")
    suburb: Optional[str] = Field(None, description="Suburb to disambiguate ERF numbers")
    proposed_footprint_sqm: Optional[float] = Field(None, gt=0)
    proposed_building_type: BuildingType = BuildingType.residential


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/analyze")
def v1_analyze(req: AnalyzeRequest, auth: tuple = Depends(_verify_api_key)):
    api_key, tier = auth
    prop = _resolve_property(req.erf_number, req.address, req.suburb)
    erf = prop["erf_number"]
    suburb = prop["suburb"]
    area_sqm = _safe_float(prop["area_sqm"], 0)
    footprint = req.proposed_footprint_sqm or (area_sqm * 0.4)

    bio = calculate_offset_requirement(erf, footprint, suburb=suburb)
    constraint = generate_constraint_map(erf, suburb=suburb)
    solar = calculate_solar_potential(erf, suburb=suburb)
    water = calculate_water_harvesting(erf, suburb=suburb)
    scorecard = netzero_scorecard(erf, suburb=suburb)
    zoning = _build_zoning_analysis(prop["zoning_primary"] or "", area_sqm)

    return {
        "property_id": prop["id"],
        "erf_number": erf,
        "suburb": suburb,
        "area_sqm": area_sqm,
        "inside_urban_edge": prop["inside_urban_edge"],
        "biodiversity": bio if "error" not in bio else {"error": bio.get("error")},
        "zoning": zoning,
        "netzero": {
            "scorecard": scorecard if "error" not in scorecard else None,
            "solar": solar if "error" not in solar else None,
            "water": water if "error" not in water else None,
        },
        "offset_requirements": {
            "footprint_sqm": footprint,
            "building_type": req.proposed_building_type.value,
            **(bio if "error" not in bio else {}),
        },
        "map_layers": {"constraint_map": constraint if "error" not in constraint else None},
        "report_url": f"/api/property/{prop['id']}/report",
        "api": {"tier": tier, "key_prefix": api_key[:8] + "..."},
    }


@router.get("/conservation-land-bank")
def v1_conservation_land_bank(
    ecosystem_type: str = Query(...),
    min_hectares: float = Query(0.1, gt=0),
    max_distance_km: float = Query(None, gt=0),
    origin_property_id: int = Query(None),
    auth: tuple = Depends(_verify_api_key),
):
    result = find_matching_conservation_land_bank(
        required_ha=min_hectares,
        ecosystem_type=ecosystem_type,
        origin_property_id=origin_property_id,
    )
    if max_distance_km and result.get("candidates"):
        result["candidates"] = [
            c for c in result["candidates"]
            if c.get("distance_km") is None or c["distance_km"] <= max_distance_km
        ]
        result["candidates_found"] = len(result["candidates"])
    return result


@router.get("/bionet/layers")
def v1_bionet_layers(
    west: float = Query(...), south: float = Query(...),
    east: float = Query(...), north: float = Query(...),
    auth: tuple = Depends(_verify_api_key),
):
    from api.routes.layers import get_biodiversity_layer
    return get_biodiversity_layer(west=west, south=south, east=east, north=north)


@router.post("/reports/generate")
def v1_generate_report(req: AnalyzeRequest, auth: tuple = Depends(_verify_api_key)):
    prop = _resolve_property(req.erf_number, req.address, req.suburb)
    report = get_property_report(prop["id"])
    return {
        "report_id": report["report_id"],
        "report_date": report["report_date"],
        "property_id": prop["id"],
        "download_url": f"/api/property/{prop['id']}/report",
        "data": report,
    }


@router.get("/health")
def v1_health():
    checks = {"version": "1.0.0", "database": "disconnected", "postgis": False, "data_loaded": False}
    try:
        engine = get_engine()
        if engine:
            with engine.connect() as conn:
                checks["database"] = "connected"
                row = conn.execute(text("SELECT PostGIS_Version()")).scalar()
                checks["postgis"] = bool(row)
                try:
                    count = conn.execute(text(f"SELECT COUNT(*) FROM {SCHEMA}.properties")).scalar()
                    checks["data_loaded"] = count > 0
                    checks["property_count"] = count
                except Exception:
                    checks["data_loaded"] = False
                    checks["property_count"] = 0
    except Exception as e:
        checks["error"] = str(e)
    checks["status"] = "ok" if all([
        checks["database"] == "connected", checks["postgis"], checks["data_loaded"]
    ]) else "degraded"
    return checks
