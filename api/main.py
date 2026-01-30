"""
CapeEco API — FastAPI backend serving PostGIS data for the web frontend.

Endpoints:
  GET /api/search?q=...           — Address/ERF autocomplete
  GET /api/property/{id}          — Property detail + geometry
  GET /api/property/{id}/biodiversity — Biodiversity assessment
  GET /api/property/{id}/netzero  — Net zero scorecard
  GET /api/property/{id}/constraint-map — GeoJSON constraint map
  GET /api/layers/biodiversity?bbox=... — CBA overlay GeoJSON for map viewport
  GET /api/layers/properties?bbox=...   — Property boundaries for map viewport
"""

import hashlib
import json
import logging
import os
import sys
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, Query, HTTPException, Header, Depends, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("capeeco")

# Add scripts directory so we can import the engines
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from biodiversity_engine import (
    calculate_offset_requirement,
    generate_constraint_map,
    find_matching_conservation_land_bank,
)
from netzero_engine import (
    calculate_solar_potential,
    calculate_water_harvesting,
    netzero_scorecard,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DB_NAME = "capeeco"
DB_USER = os.environ.get("PGUSER", os.environ.get("USER", "postgres"))
DB_HOST = os.environ.get("PGHOST", "localhost")
DB_PORT = os.environ.get("PGPORT", "5432")
DB_PASSWORD = os.environ.get("PGPASSWORD", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
SCHEMA = "capeeco"


def _conn_string():
    # Check all possible env var names for database URL
    # Railway sometimes adds whitespace to env var keys — check all variants
    raw = os.environ.get("DATABASE_URL")
    if raw is None:
        # Scan for DATABASE_URL with trailing whitespace in key
        for k, v in os.environ.items():
            if k.strip() == "DATABASE_URL":
                raw = v
                print(f"STARTUP: found DATABASE_URL with whitespace in key: repr(key)={repr(k)}", flush=True)
                break
    if raw is None:
        raw = os.environ.get("DATABASE_PRIVATE_URL")
    print(f"STARTUP: resolved DATABASE_URL len={len(raw) if raw else 0}", flush=True)
    db_url = raw or ""
    if db_url:
        # Railway uses postgres:// but SQLAlchemy requires postgresql://
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        print(f"STARTUP: Using DATABASE_URL -> {db_url.split('@')[1].split('/')[0] if '@' in db_url else '?'}", flush=True)
        return db_url
    # Fallback to individual PG* env vars
    pw = os.environ.get("PGPASSWORD", "")
    host = os.environ.get("PGHOST", "localhost")
    port = os.environ.get("PGPORT", "5432")
    user = os.environ.get("PGUSER", os.environ.get("USER", "postgres"))
    name = os.environ.get("PGDATABASE", "capeeco")
    url = f"postgresql://{user}:{pw}@{host}:{port}/{name}" if pw else f"postgresql://{user}@{host}:{port}/{name}"
    print(f"STARTUP: Using PG* vars -> {host}:{port}/{name}", flush=True)
    return url


engine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    # Debug: print all env vars containing DB/PG/DATABASE
    for k, v in sorted(os.environ.items()):
        if any(x in k.upper() for x in ['DB', 'PG', 'DATABASE', 'POSTGRES']):
            safe_v = v[:20] + '...' if len(v) > 20 else v
            print(f"STARTUP ENV: {k}={safe_v}", flush=True)
    conn_str = _conn_string()
    engine = create_engine(
        conn_str,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    # Ensure users table exists
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS capeeco.users (
                    id          BIGSERIAL PRIMARY KEY,
                    email       VARCHAR(255) UNIQUE NOT NULL,
                    hashed_password VARCHAR(255) NOT NULL,
                    full_name   VARCHAR(255),
                    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_email ON capeeco.users(email)"))
            conn.commit()
            print("STARTUP: users table ready", flush=True)
    except Exception as e:
        print(f"STARTUP: users table check failed: {e}", flush=True)
    yield
    engine.dispose()


app = FastAPI(title="CapeEco API", version="1.0.0", lifespan=lifespan)

ALLOWED_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if os.environ.get("ENVIRONMENT") == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)


# ---------------------------------------------------------------------------
# Authentication endpoints
# ---------------------------------------------------------------------------
from api.auth import (
    UserCreate, UserLogin, UserResponse, Token,
    hash_password, verify_password, create_access_token, get_current_user,
)


@app.post("/api/auth/register", response_model=Token)
def auth_register(body: UserCreate):
    """Create a new user account."""
    email = body.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "Invalid email address")
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    hashed = hash_password(body.password)
    with engine.connect() as conn:
        # Check if email already exists
        exists = conn.execute(
            text(f"SELECT id FROM {SCHEMA}.users WHERE email = :email"),
            {"email": email},
        ).fetchone()
        if exists:
            raise HTTPException(409, "Email already registered")

        row = conn.execute(
            text(f"""
                INSERT INTO {SCHEMA}.users (email, hashed_password, full_name)
                VALUES (:email, :hashed, :name)
                RETURNING id, email, full_name, is_active, created_at
            """),
            {"email": email, "hashed": hashed, "name": body.full_name},
        ).fetchone()
        conn.commit()

    user = dict(row._mapping)
    token = create_access_token({"sub": user["id"]})
    return {"access_token": token, "token_type": "bearer", "user": user}


@app.post("/api/auth/login", response_model=Token)
def auth_login(body: UserLogin):
    """Authenticate and return a JWT token."""
    email = body.email.strip().lower()
    with engine.connect() as conn:
        row = conn.execute(
            text(f"SELECT id, email, full_name, is_active, created_at, hashed_password FROM {SCHEMA}.users WHERE email = :email"),
            {"email": email},
        ).fetchone()

    if not row:
        raise HTTPException(401, "Invalid email or password")

    user = dict(row._mapping)
    if not verify_password(body.password, user.pop("hashed_password")):
        raise HTTPException(401, "Invalid email or password")

    if not user["is_active"]:
        raise HTTPException(403, "Account disabled")

    token = create_access_token({"sub": user["id"]})
    return {"access_token": token, "token_type": "bearer", "user": user}


@app.get("/api/auth/me", response_model=UserResponse)
def auth_me(current_user: dict = Depends(get_current_user)):
    """Return the current authenticated user."""
    return current_user


# ---------------------------------------------------------------------------
# Search / Autocomplete
# ---------------------------------------------------------------------------

@app.get("/api/search")
def search_properties(q: str = Query(..., min_length=2, max_length=200), limit: int = Query(10, le=50), _user: dict = Depends(get_current_user)):
    """Search properties by address or ERF number. Returns top matches."""
    with engine.connect() as conn:
        # Try ERF number match first (exact or prefix)
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

        # Address search via address_points (trigram/prefix match)
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

        # Fallback: suburb search
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


# ---------------------------------------------------------------------------
# Property detail
# ---------------------------------------------------------------------------

@app.get("/api/property/{property_id}")
def get_property(property_id: int, _user: dict = Depends(get_current_user)):
    """Get full property details + GeoJSON geometry."""
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

        # Get biodiversity designations
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

        # Heritage overlay
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


# ---------------------------------------------------------------------------
# Analysis endpoints
# ---------------------------------------------------------------------------

@app.get("/api/property/{property_id}/biodiversity")
def get_biodiversity_analysis(property_id: int, footprint_sqm: float = Query(None), _user: dict = Depends(get_current_user)):
    """Run biodiversity offset calculation."""
    with engine.connect() as conn:
        row = conn.execute(text(f"""
            SELECT erf_number, suburb, area_sqm FROM {SCHEMA}.properties WHERE id = :id
        """), {"id": property_id}).mappings().fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Property not found")

    fp = footprint_sqm or (row["area_sqm"] * 0.4)  # default 40% footprint
    result = calculate_offset_requirement(row["erf_number"], fp, suburb=row["suburb"])
    return result


@app.get("/api/property/{property_id}/netzero")
def get_netzero_analysis(property_id: int, _user: dict = Depends(get_current_user)):
    """Run net zero scorecard."""
    with engine.connect() as conn:
        row = conn.execute(text(f"""
            SELECT erf_number, suburb FROM {SCHEMA}.properties WHERE id = :id
        """), {"id": property_id}).mappings().fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Property not found")

    result = netzero_scorecard(row["erf_number"], suburb=row["suburb"])
    return result


@app.get("/api/property/{property_id}/solar")
def get_solar_analysis(property_id: int, _user: dict = Depends(get_current_user)):
    """Run solar potential calculation."""
    with engine.connect() as conn:
        row = conn.execute(text(f"""
            SELECT erf_number, suburb FROM {SCHEMA}.properties WHERE id = :id
        """), {"id": property_id}).mappings().fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Property not found")

    return calculate_solar_potential(row["erf_number"], suburb=row["suburb"])


@app.get("/api/property/{property_id}/water")
def get_water_analysis(property_id: int, _user: dict = Depends(get_current_user)):
    """Run water harvesting calculation."""
    with engine.connect() as conn:
        row = conn.execute(text(f"""
            SELECT erf_number, suburb FROM {SCHEMA}.properties WHERE id = :id
        """), {"id": property_id}).mappings().fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Property not found")

    return calculate_water_harvesting(row["erf_number"], suburb=row["suburb"])


@app.get("/api/property/{property_id}/constraint-map")
def get_constraint_map(property_id: int, _user: dict = Depends(get_current_user)):
    """Generate GeoJSON constraint map for a property."""
    with engine.connect() as conn:
        row = conn.execute(text(f"""
            SELECT erf_number, suburb FROM {SCHEMA}.properties WHERE id = :id
        """), {"id": property_id}).mappings().fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Property not found")

    return generate_constraint_map(row["erf_number"], suburb=row["suburb"])


# ---------------------------------------------------------------------------
# Map layer endpoints (viewport-based)
# ---------------------------------------------------------------------------

@app.get("/api/layers/biodiversity")
def get_biodiversity_layer(
    west: float = Query(...), south: float = Query(...),
    east: float = Query(...), north: float = Query(...),
    _user: dict = Depends(get_current_user),
):
    """Return CBA overlay polygons within the viewport as GeoJSON."""
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


@app.get("/api/layers/properties")
def get_properties_layer(
    west: float = Query(...), south: float = Query(...),
    east: float = Query(...), north: float = Query(...),
    _user: dict = Depends(get_current_user),
):
    """Return property boundaries within viewport. Only at high zoom levels."""
    # Calculate viewport area to prevent returning too many properties
    area_deg = (east - west) * (north - south)
    if area_deg > 0.01:  # roughly > 1km² — too many properties
        return {"type": "FeatureCollection", "features": [], "note": "Zoom in to see property boundaries"}

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


@app.get("/api/layers/ecosystem-types")
def get_ecosystem_layer(
    west: float = Query(...), south: float = Query(...),
    east: float = Query(...), north: float = Query(...),
    _user: dict = Depends(get_current_user),
):
    """Return ecosystem type polygons within viewport."""
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


@app.get("/api/layers/heritage")
def get_heritage_layer(
    west: float = Query(...), south: float = Query(...),
    east: float = Query(...), north: float = Query(...),
    _user: dict = Depends(get_current_user),
):
    """Return heritage sites within viewport."""
    area_deg = (east - west) * (north - south)
    if area_deg > 0.005:
        return {"type": "FeatureCollection", "features": [], "note": "Zoom in to see heritage sites"}

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


# ---------------------------------------------------------------------------
# Report endpoint — aggregates all data for PDF report generation
# ---------------------------------------------------------------------------

RULES_PATH = Path(__file__).parent.parent / "data" / "processed" / "offset_rules.json"


def _load_rules():
    with open(RULES_PATH) as f:
        return json.load(f)


def _safe_float(v, default=None):
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


@app.get("/api/property/{property_id}/report")
def get_property_report(property_id: int, _user: dict = Depends(get_current_user)):
    """Generate comprehensive Development Potential Report data."""
    rules = _load_rules()
    report_date = date.today()

    with engine.connect() as conn:
        prop_row = conn.execute(text(f"""
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

        if not prop_row:
            raise HTTPException(status_code=404, detail="Property not found")

        prop = dict(prop_row)

        bio_rows = conn.execute(text(f"""
            SELECT DISTINCT pb.cba_category, pb.habitat_condition,
                   ROUND(pb.overlap_pct::numeric, 2) AS overlap_pct,
                   CASE pb.cba_category
                       WHEN 'PA' THEN 1 WHEN 'CA' THEN 2
                       WHEN 'CBA 1a' THEN 3 WHEN 'CBA 1b' THEN 4 WHEN 'CBA 1c' THEN 5
                       WHEN 'CBA 2' THEN 6 WHEN 'ESA 1' THEN 7 WHEN 'ESA 2' THEN 8
                       WHEN 'ONA' THEN 9
                   END AS sort_order
            FROM {SCHEMA}.property_biodiversity pb
            WHERE pb.property_id = :id
            ORDER BY sort_order
        """), {"id": property_id}).mappings().fetchall()

        bio_by_cat = {}
        for r in bio_rows:
            cat = r["cba_category"]
            if cat not in bio_by_cat:
                bio_by_cat[cat] = {"cba_category": cat, "habitat_conditions": [], "total_overlap_pct": 0}
            bio_by_cat[cat]["total_overlap_pct"] += _safe_float(r["overlap_pct"], 0)
            cond = r["habitat_condition"]
            if cond and cond not in bio_by_cat[cat]["habitat_conditions"]:
                bio_by_cat[cat]["habitat_conditions"].append(cond)

        area_ha = _safe_float(prop["area_ha"], 0)
        area_sqm = _safe_float(prop["area_sqm"], 0)
        no_go_cats = {"PA", "CA", "CBA 1a"}
        offset_cats = {"CBA 1b", "CBA 1c", "CBA 2", "ESA 1", "ESA 2"}
        total_constrained_pct = 0
        biodiversity_entries = []

        for cat, data in bio_by_cat.items():
            cat_key = cat.replace(" ", "_")
            cat_rules = rules.get("cba_categories", {}).get(cat_key, {})
            overlap_pct = min(data["total_overlap_pct"], 100)
            total_constrained_pct += overlap_pct
            affected_ha = area_ha * overlap_pct / 100

            entry = {
                "designation": cat,
                "name": cat_rules.get("name", cat),
                "description": cat_rules.get("full_description", ""),
                "overlap_pct": round(overlap_pct, 2),
                "affected_area_ha": round(affected_ha, 4),
                "habitat_conditions": data["habitat_conditions"],
                "development_allowed": cat_rules.get("development_allowed", True),
                "is_no_go": cat in no_go_cats,
                "offset_applicable": cat in offset_cats,
                "base_ratio": cat_rules.get("base_ratio"),
                "sdf_category": cat_rules.get("sdf_category", ""),
            }

            if cat in offset_cats and entry["base_ratio"] is not None:
                ratio = entry["base_ratio"]
                offset_ha = affected_ha * ratio
                entry["offset_required_ha"] = round(offset_ha, 4)
                cost_rules = rules.get("cost_estimation", {})
                price_per_ha = cost_rules.get("price_per_ha_base_zar", 0)
                entry["offset_cost_estimate_zar"] = round(offset_ha * price_per_ha)
            else:
                entry["offset_required_ha"] = None
                entry["offset_cost_estimate_zar"] = None

            biodiversity_entries.append(entry)

        total_constrained_pct = min(total_constrained_pct, 100)
        developable_pct = max(0, 100 - total_constrained_pct)

        eco_rows = conn.execute(text(f"""
            SELECT DISTINCT pe.vegetation_type, pe.threat_status
            FROM {SCHEMA}.property_ecosystems pe
            WHERE pe.property_id = :id
        """), {"id": property_id}).mappings().fetchall()
        ecosystems = [{"vegetation_type": r["vegetation_type"], "threat_status": r["threat_status"]} for r in eco_rows]

        heritage_rows = conn.execute(text(f"""
            SELECT hs.site_name, hs.source, hs.heritage_category,
                   hs.nhra_status, hs.city_grading,
                   hs.resource_type_1, hs.architectural_style, hs.period,
                   hs.street_address
            FROM {SCHEMA}.heritage_sites hs
            WHERE ST_Intersects(hs.geom, (SELECT geom FROM {SCHEMA}.properties WHERE id = :id))
            LIMIT 10
        """), {"id": property_id}).mappings().fetchall()
        heritage = [dict(r) for r in heritage_rows]

    solar = calculate_solar_potential(prop["erf_number"], suburb=prop["suburb"])
    water = calculate_water_harvesting(prop["erf_number"], suburb=prop["suburb"])
    scorecard = netzero_scorecard(prop["erf_number"], suburb=prop["suburb"])

    footprint_sqm = area_sqm * 0.4
    bio_analysis = calculate_offset_requirement(prop["erf_number"], footprint_sqm, suburb=prop["suburb"])

    if any(e["is_no_go"] for e in biodiversity_entries):
        bio_risk_level, bio_risk_color = "Critical", "red"
    elif any(e["designation"] in ("CBA 1b", "CBA 1c") for e in biodiversity_entries):
        bio_risk_level, bio_risk_color = "High", "orange"
    elif any(e["offset_applicable"] for e in biodiversity_entries):
        bio_risk_level, bio_risk_color = "Medium", "amber"
    else:
        bio_risk_level, bio_risk_color = "Low", "green"

    zoning = prop["zoning_primary"] or "Not classified"
    zoning_analysis = _build_zoning_analysis(zoning, area_sqm)

    address_parts = []
    if prop.get("address_number"):
        address_parts.append(str(prop["address_number"]))
    if prop.get("street_name"):
        s = prop["street_name"]
        if prop.get("street_type"):
            s += f" {prop['street_type']}"
        address_parts.append(s)
    if prop.get("suburb"):
        address_parts.append(prop["suburb"])
    address = ", ".join(address_parts) if address_parts else f"ERF {prop['erf_number']}"

    return {
        "report_date": report_date.strftime("%d %B %Y"),
        "report_id": f"CE-{property_id}-{report_date.strftime('%Y%m%d')}",
        "property": {
            "id": property_id,
            "erf_number": prop["erf_number"],
            "address": address,
            "suburb": prop["suburb"] or "Unknown",
            "area_sqm": round(area_sqm, 1) if area_sqm else None,
            "area_ha": round(area_ha, 4) if area_ha else None,
            "zoning": zoning,
            "inside_urban_edge": prop["inside_urban_edge"],
            "coordinates": {"lat": _safe_float(prop["centroid_lat"]), "lon": _safe_float(prop["centroid_lon"])},
            "geometry": prop["geometry"],
        },
        "executive_summary": {
            "biodiversity_risk": bio_risk_level,
            "biodiversity_risk_color": bio_risk_color,
            "developable_area_pct": round(developable_pct, 1),
            "netzero_score": scorecard.get("total_score") if "error" not in scorecard else None,
            "greenstar_rating": scorecard.get("greenstar_rating") if "error" not in scorecard else None,
            "offset_cost_range": _calc_offset_cost_range(biodiversity_entries),
        },
        "biodiversity": {
            "designations": biodiversity_entries,
            "total_constrained_pct": round(total_constrained_pct, 1),
            "developable_pct": round(developable_pct, 1),
            "ecosystems": ecosystems,
            "offset_analysis": bio_analysis if "error" not in bio_analysis else None,
            "regulatory_references": [
                {"name": s["name"], "reference": s.get("reference", ""), "authority": s.get("authority", "")}
                for s in rules.get("_metadata", {}).get("sources", [])
            ],
        },
        "heritage": {"sites": heritage, "has_heritage": len(heritage) > 0, "count": len(heritage)},
        "zoning_analysis": zoning_analysis,
        "netzero": {
            "scorecard": scorecard if "error" not in scorecard else None,
            "solar": solar if "error" not in solar else None,
            "water": water if "error" not in water else None,
        },
        "action_items": _build_action_items(
            bio_risk_level, biodiversity_entries, heritage,
            solar, water, scorecard, prop["inside_urban_edge"],
        ),
        "disclaimer": rules.get("_metadata", {}).get("disclaimer", ""),
    }


def _build_zoning_analysis(zoning, area_sqm):
    z = zoning.upper() if zoning else ""
    params_map = {
        "SINGLE RESIDENTIAL 1": {"max_height_m": 8, "max_floors": 2, "max_coverage_pct": 50, "far": 0.5},
        "SINGLE RESIDENTIAL 2": {"max_height_m": 6, "max_floors": 1, "max_coverage_pct": 80, "far": 0.5},
        "GENERAL RESIDENTIAL 1": {"max_height_m": 11, "max_floors": 3, "max_coverage_pct": 60, "far": 1.0},
        "GENERAL RESIDENTIAL 2": {"max_height_m": 14, "max_floors": 4, "max_coverage_pct": 60, "far": 1.5},
        "GENERAL RESIDENTIAL 3": {"max_height_m": 18, "max_floors": 5, "max_coverage_pct": 60, "far": 2.0},
        "GENERAL RESIDENTIAL 4": {"max_height_m": 28, "max_floors": 8, "max_coverage_pct": 75, "far": 3.0},
        "GENERAL BUSINESS 1": {"max_height_m": 14, "max_floors": 4, "max_coverage_pct": 80, "far": 2.0},
        "MIXED USE 2": {"max_height_m": 18, "max_floors": 5, "max_coverage_pct": 80, "far": 2.5},
        "GENERAL INDUSTRIAL 1": {"max_height_m": 14, "max_floors": 3, "max_coverage_pct": 75, "far": 1.5},
        "AGRICULTURAL": {"max_height_m": 8, "max_floors": 2, "max_coverage_pct": 10, "far": 0.1},
    }
    params = None
    for key, val in params_map.items():
        if key in z:
            params = val
            break
    if not params:
        params = {"max_height_m": None, "max_floors": None, "max_coverage_pct": None, "far": None}
    max_fp = area_sqm * params["max_coverage_pct"] / 100 if params["max_coverage_pct"] else None
    max_gfa = area_sqm * params["far"] if params["far"] else None
    return {
        "zoning_classification": zoning, "max_height_m": params["max_height_m"],
        "max_floors": params["max_floors"], "max_coverage_pct": params["max_coverage_pct"],
        "floor_area_ratio": params["far"],
        "max_footprint_sqm": round(max_fp, 1) if max_fp else None,
        "max_gfa_sqm": round(max_gfa, 1) if max_gfa else None,
        "property_area_sqm": round(area_sqm, 1),
    }


def _calc_offset_cost_range(entries):
    costs = [e["offset_cost_estimate_zar"] for e in entries
             if e.get("offset_cost_estimate_zar") and e["offset_cost_estimate_zar"] > 0]
    if not costs:
        return None
    total = sum(costs)
    def _sr(v):
        if v < 10_000: return max(1_000, round(v / 1_000) * 1_000)
        if v < 1_000_000: return round(v / 10_000) * 10_000
        return round(v / 100_000) * 100_000
    def _fmt(v):
        if v >= 1_000_000: return f"ZAR {v / 1_000_000:,.1f}M"
        return f"ZAR {round(v):,}"
    return {"low_zar": _sr(total * 0.7), "high_zar": _sr(total * 1.5),
            "formatted_low": _fmt(_sr(total * 0.7)), "formatted_high": _fmt(_sr(total * 1.5))}


def _build_action_items(risk_level, bio_entries, heritage, solar, water, scorecard, inside_urban_edge):
    items = []
    if risk_level == "Critical":
        items.append({"priority": 1, "category": "Biodiversity",
            "action": "Site falls within a Protected Area or Conservation Area. Development is not permitted. Seek alternative sites or engage the City of Cape Town Biodiversity Management Branch.",
            "specialist": "Environmental Assessment Practitioner (EAP), registered with EAPASA", "timeline_days": 0})
    elif risk_level == "High":
        items.append({"priority": 1, "category": "Biodiversity",
            "action": "Appoint an EAP to conduct a Basic Assessment or Scoping & EIR under NEMA. Biodiversity offset will be required.",
            "specialist": "EAP, Botanist, Faunal Specialist", "timeline_days": 90})
    elif risk_level == "Medium":
        items.append({"priority": 2, "category": "Biodiversity",
            "action": "Commission a biodiversity impact assessment. Offset requirements apply but authorisation is achievable with appropriate mitigation.",
            "specialist": "Environmental Assessment Practitioner (EAP)", "timeline_days": 60})
    else:
        items.append({"priority": 3, "category": "Biodiversity",
            "action": "No significant biodiversity constraints identified. Standard environmental screening required for developments exceeding NEMA thresholds.",
            "specialist": None, "timeline_days": 30})

    if heritage:
        has_nhra = any(h.get("source") == "nhra" for h in heritage)
        has_graded = any(h.get("city_grading") in ("I", "II", "III", "IIIA") for h in heritage)
        if has_nhra:
            items.append({"priority": 1, "category": "Heritage",
                "action": "NHRA-protected site. Heritage Impact Assessment (HIA) mandatory. Apply to Heritage Western Cape.",
                "specialist": "Heritage Consultant (ASAPA / APHP)", "timeline_days": 120})
        elif has_graded:
            items.append({"priority": 2, "category": "Heritage",
                "action": "Locally graded heritage site. Section 34 permit required from Heritage Western Cape for demolition or substantial alteration.",
                "specialist": "Heritage Consultant", "timeline_days": 60})
        else:
            items.append({"priority": 3, "category": "Heritage",
                "action": "Heritage survey area. Submit NID to Heritage Western Cape if building is older than 60 years.",
                "specialist": None, "timeline_days": 30})

    if solar and "error" not in solar:
        if solar.get("netzero_energy_feasible"):
            items.append({"priority": 3, "category": "Energy",
                "action": f"Strong solar potential ({solar['system_size_kwp']} kWp). Apply to CoCT for SSEG embedded generation approval.",
                "specialist": "Solar PV installer (CoCT accredited)", "timeline_days": 45})
        else:
            items.append({"priority": 2, "category": "Energy",
                "action": "On-site solar insufficient for net zero. Consider energy-efficient design (SANS 10400-XA), heat pumps, renewable energy certificates.",
                "specialist": "Energy consultant", "timeline_days": 30})

    if water and "error" not in water:
        items.append({"priority": 3, "category": "Water",
            "action": f"Install rainwater harvesting ({water.get('recommended_tank_size_kl', 'N/A')} kl recommended tank). Day Zero resilience measure.",
            "specialist": "Plumber (PIRB registered)", "timeline_days": 30})

    if not inside_urban_edge:
        items.append({"priority": 1, "category": "Planning",
            "action": "Outside urban edge. Development requires exceptional motivation. Engage City Spatial Planning department.",
            "specialist": "Town Planner (SACPLAN registered)", "timeline_days": 180})

    items.sort(key=lambda x: x["priority"])
    return items


# ---------------------------------------------------------------------------
# AI Analysis endpoint — DeepSeek-powered contextual insights
# ---------------------------------------------------------------------------

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-16bc811b5f114517970b55fdec8dcd91")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

AI_SYSTEM_PROMPTS = {
    "executive_summary": (
        "You are a South African environmental property analyst. Given a property's data, "
        "write a clear 2-3 sentence plain-English interpretation of the overall development "
        "potential. Mention the biodiversity risk level, developable percentage, and Green Star "
        "rating in practical terms a property developer would understand. Do NOT give legal or "
        "investment advice. Do NOT speculate beyond the data provided. Stay under 100 words."
    ),
    "biodiversity": (
        "You are a Cape Town biodiversity specialist. Given the CBA/ESA designations overlapping "
        "a property, explain what they mean for development in 2-3 sentences. Reference the City "
        "of Cape Town BioNet and NEMA regulations where relevant. Do NOT give legal advice. "
        "Do NOT speculate beyond the data. Stay under 120 words."
    ),
    "heritage": (
        "You are a South African heritage consultant. Given heritage site records near a property, "
        "explain the implications for development in 2-3 sentences. Reference Section 34 of the "
        "NHRA and Heritage Western Cape where relevant. Do NOT give legal advice. Stay under 100 words."
    ),
    "netzero": (
        "You are a Green Star SA sustainability consultant. Given a property's net zero scorecard "
        "scores (energy, water, ecology, location, materials out of their maximums), interpret what "
        "the rating means practically. Suggest which score category has the most room for improvement. "
        "Do NOT give investment advice. Stay under 120 words."
    ),
    "solar": (
        "You are a Cape Town solar energy analyst. Given a property's solar potential data (system "
        "size, annual generation, net zero ratio, carbon offset, payback period), provide a practical "
        "assessment of whether rooftop solar is worthwhile for this property. Reference Cape Town's "
        "average 5.5 peak sun hours and SSEG programme. Do NOT give investment advice. Stay under 120 words."
    ),
    "water": (
        "You are a Cape Town water resilience analyst. Given a property's rainwater harvesting data "
        "(rainfall zone, annual harvest, demand met percentage, tank size), assess the water "
        "resilience potential. Reference Cape Town's Day Zero experience and seasonal rainfall "
        "patterns. Do NOT give investment advice. Stay under 120 words."
    ),
    "actions": (
        "You are a South African development planning advisor. Given a list of recommended actions "
        "with priorities, categories, and timelines, provide a concise plain-English summary of "
        "the most critical next steps and why they matter. Group related actions together. "
        "Do NOT give legal or investment advice. Stay under 130 words."
    ),
}


class AiAnalyzeRequest(BaseModel):
    section: str
    context: dict


@app.post("/api/ai/analyze")
async def ai_analyze(req: AiAnalyzeRequest, _user: dict = Depends(get_current_user)):
    """Get AI-powered analysis for a report section."""
    system_prompt = AI_SYSTEM_PROMPTS.get(req.section)
    if not system_prompt:
        raise HTTPException(status_code=400, detail=f"Unknown section: {req.section}")

    if not DEEPSEEK_API_KEY:
        return {"analysis": None, "error": "AI not configured"}

    user_content = json.dumps(req.context, default=str, ensure_ascii=False)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                DEEPSEEK_URL,
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    "max_tokens": 300,
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text_out = data["choices"][0]["message"]["content"].strip()
            return {"analysis": text_out}
    except Exception as e:
        logger.warning("DeepSeek API error: %s", e)
        return {"analysis": None, "error": "AI temporarily unavailable"}


# ===========================================================================
# Phase 4: Public API (v1) — auth, rate limiting, unified analysis
# ===========================================================================

# ---------------------------------------------------------------------------
# API Key management
# ---------------------------------------------------------------------------
# For now, keys stored as env var CSV. Production would use DB table.
# Format: "key1:tier,key2:tier" e.g. "abc123:free,xyz789:paid"
API_KEYS_RAW = os.environ.get("CAPEECO_API_KEYS", "")
API_KEYS: dict[str, str] = {}  # key -> tier
for entry in API_KEYS_RAW.split(","):
    entry = entry.strip()
    if ":" in entry:
        k, tier = entry.split(":", 1)
        API_KEYS[k.strip()] = tier.strip()

# Default demo key for development
if not API_KEYS:
    API_KEYS["demo-key-capeeco-2026"] = "free"

RATE_LIMITS = {"free": 100, "paid": 10_000}  # requests per day


class _RateLimiter:
    """Simple in-memory sliding-window rate limiter per API key."""

    def __init__(self):
        self._counters: dict[str, list[float]] = defaultdict(list)

    def check(self, api_key: str, tier: str) -> tuple[bool, int]:
        """Returns (allowed, remaining)."""
        now = time.time()
        window = 86_400  # 24h
        limit = RATE_LIMITS.get(tier, 100)

        times = self._counters[api_key]
        # Prune old entries
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
                "message": f"Daily limit of {RATE_LIMITS.get(tier, 100)} requests exceeded. Upgrade to paid tier for higher limits.",
                "tier": tier,
            },
        )
    return key, tier


# ---------------------------------------------------------------------------
# v1 Router
# ---------------------------------------------------------------------------
v1 = APIRouter(prefix="/api/v1", tags=["v1"])


# --- Helper: resolve property from erf_number OR address ---
def _resolve_property(erf_number: str = None, address: str = None, suburb: str = None):
    """Find property ID from erf_number+suburb or address. Returns dict or raises."""
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
                q += f" AND p.suburb ILIKE :suburb"
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

    # Verify inside CCT boundary (simple lat/lon check)
    lat = _safe_float(row["centroid_lat"])
    lon = _safe_float(row["centroid_lon"])
    if lat and lon:
        if not (-34.4 <= lat <= -33.4 and 18.2 <= lon <= 19.0):
            raise HTTPException(status_code=422, detail={
                "error": "outside_cct_boundary",
                "message": "Property coordinates fall outside the City of Cape Town municipal boundary",
            })

    return dict(row)


# --- Pydantic models ---
class BuildingType(str, Enum):
    residential = "residential"
    commercial = "commercial"
    industrial = "industrial"


class AnalyzeRequest(BaseModel):
    erf_number: Optional[str] = Field(None, description="ERF number (pair with suburb for uniqueness)")
    address: Optional[str] = Field(None, description="Street address to geocode")
    suburb: Optional[str] = Field(None, description="Suburb to disambiguate ERF numbers")
    proposed_footprint_sqm: Optional[float] = Field(None, gt=0, description="Proposed development footprint in m²")
    proposed_building_type: BuildingType = BuildingType.residential


class ConservationQuery(BaseModel):
    ecosystem_type: str = Field(..., description="Vegetation type to match (e.g. 'Cape Flats Sand Fynbos')")
    min_hectares: float = Field(0.1, gt=0, description="Minimum offset area needed in hectares")
    max_distance_km: Optional[float] = Field(None, gt=0, description="Max distance from origin property in km")
    origin_property_id: Optional[int] = Field(None, description="Property ID for distance calculation")


# --- POST /api/v1/analyze ---
@v1.post("/analyze")
def v1_analyze(req: AnalyzeRequest, auth: tuple = Depends(_verify_api_key)):
    """Unified property analysis: biodiversity + zoning + net zero + offsets."""
    api_key, tier = auth
    prop = _resolve_property(req.erf_number, req.address, req.suburb)

    erf = prop["erf_number"]
    suburb = prop["suburb"]
    area_sqm = _safe_float(prop["area_sqm"], 0)
    footprint = req.proposed_footprint_sqm or (area_sqm * 0.4)

    # Run all analyses
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
        "map_layers": {
            "constraint_map": constraint if "error" not in constraint else None,
        },
        "report_url": f"/api/property/{prop['id']}/report",
        "api": {"tier": tier, "key_prefix": api_key[:8] + "..."},
    }


# --- GET /api/v1/conservation-land-bank ---
@v1.get("/conservation-land-bank")
def v1_conservation_land_bank(
    ecosystem_type: str = Query(..., description="Vegetation type to match"),
    min_hectares: float = Query(0.1, gt=0),
    max_distance_km: float = Query(None, gt=0),
    origin_property_id: int = Query(None),
    auth: tuple = Depends(_verify_api_key),
):
    """Find candidate offset parcels from the conservation land bank."""
    result = find_matching_conservation_land_bank(
        required_ha=min_hectares,
        ecosystem_type=ecosystem_type,
        origin_property_id=origin_property_id,
    )

    # Filter by distance if requested
    if max_distance_km and result.get("candidates"):
        result["candidates"] = [
            c for c in result["candidates"]
            if c.get("distance_km") is None or c["distance_km"] <= max_distance_km
        ]
        result["candidates_found"] = len(result["candidates"])

    return result


# --- GET /api/v1/bionet/layers ---
@v1.get("/bionet/layers")
def v1_bionet_layers(
    west: float = Query(...), south: float = Query(...),
    east: float = Query(...), north: float = Query(...),
    auth: tuple = Depends(_verify_api_key),
):
    """Return CBA overlay GeoJSON for map display (authenticated)."""
    return get_biodiversity_layer(west=west, south=south, east=east, north=north)


# --- POST /api/v1/reports/generate ---
@v1.post("/reports/generate")
def v1_generate_report(req: AnalyzeRequest, auth: tuple = Depends(_verify_api_key)):
    """Generate a full Development Potential Report. Returns data + report URL."""
    prop = _resolve_property(req.erf_number, req.address, req.suburb)
    report = get_property_report(prop["id"])
    return {
        "report_id": report["report_id"],
        "report_date": report["report_date"],
        "property_id": prop["id"],
        "download_url": f"/api/property/{prop['id']}/report",
        "data": report,
    }


# --- Health / info ---
@v1.get("/health")
def v1_health():
    """API health check (no auth required). Verifies DB, PostGIS, and data."""
    checks = {"version": "1.0.0", "database": "disconnected", "postgis": False, "data_loaded": False}
    try:
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
    return checks  # Always HTTP 200 — Railway needs this for healthcheck


# Mount v1 router
app.include_router(v1)


# ---------------------------------------------------------------------------
# Serve frontend static files in production (single-service deploy)
# ---------------------------------------------------------------------------
_FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"
if _FRONTEND_DIR.is_dir():
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file = _FRONTEND_DIR / full_path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(_FRONTEND_DIR / "index.html")

    logger.info("Serving frontend from %s", _FRONTEND_DIR)
