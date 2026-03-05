"""Search / autocomplete endpoints."""

from fastapi import APIRouter, Query, Depends
from sqlalchemy import text

from api.db import get_engine, SCHEMA
from api.auth import get_current_user

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search")
def search_properties(
    q: str = Query(..., min_length=2, max_length=200),
    limit: int = Query(10, le=50),
    _user: dict = Depends(get_current_user),
):
    """Search properties by address or ERF number. Returns top matches."""
    engine = get_engine()
    with engine.connect() as conn:
        erf_results = conn.execute(text(f"""
            SELECT p.id, p.erf_number, p.suburb, p.street_name, p.street_type,
                   p.address_number, p.full_address, p.area_sqm,
                   p.centroid_lon, p.centroid_lat, p.zoning_primary
            FROM {SCHEMA}.properties p
            WHERE p.erf_number = :q
            ORDER BY p.suburb
            LIMIT :limit
        """), {"q": q.strip(), "limit": limit}).mappings().fetchall()

        if erf_results:
            return {"results": [dict(r) for r in erf_results], "match_type": "erf"}

        addr_results = conn.execute(text(f"""
            SELECT DISTINCT ON (p.id)
                   p.id, p.erf_number, p.suburb, p.street_name, p.street_type,
                   p.address_number, p.full_address, p.area_sqm,
                   p.centroid_lon, p.centroid_lat, p.zoning_primary
            FROM {SCHEMA}.address_points ap
            JOIN {SCHEMA}.properties p ON ST_Within(ap.geom, p.geom)
            WHERE ap.full_address ILIKE :pattern
            ORDER BY p.id, ap.full_address
            LIMIT :limit
        """), {"pattern": f"%{q.strip()}%", "limit": limit}).mappings().fetchall()

        if addr_results:
            return {"results": [dict(r) for r in addr_results], "match_type": "address"}

        suburb_results = conn.execute(text(f"""
            SELECT p.id, p.erf_number, p.suburb, p.street_name, p.street_type,
                   p.address_number, p.full_address, p.area_sqm,
                   p.centroid_lon, p.centroid_lat, p.zoning_primary
            FROM {SCHEMA}.properties p
            WHERE p.suburb ILIKE :pattern
               OR p.street_name ILIKE :street_pattern
            ORDER BY p.suburb, p.erf_number
            LIMIT :limit
        """), {"pattern": f"%{q.strip()}%", "street_pattern": f"%{q.strip()}%", "limit": limit}).mappings().fetchall()

        return {"results": [dict(r) for r in suburb_results], "match_type": "suburb"}
