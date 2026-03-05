"""
Siteline — Crime Risk Engine

Calculates crime risk scores for properties using:
- SAPS crime statistics per police station (29 categories)
- Police station boundary shapefiles for geographic mapping

Functions:
1. calculate_crime_risk(property_id) — Returns crime risk score, breakdown by category, trends
"""

import logging
import os

from sqlalchemy import create_engine, text

logger = logging.getLogger("siteline")

SCHEMA = os.environ.get("SITELINE_SCHEMA", "siteline")
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
    name = os.environ.get("PGDATABASE", "siteline")
    return f"postgresql://{user}:{pw}@{host}:{port}/{name}" if pw else f"postgresql://{user}@{host}:{port}/{name}"


def _get_engine():
    return create_engine(_conn_string(), pool_size=3, max_overflow=5, pool_pre_ping=True)


def _get_schema(conn):
    try:
        conn.execute(text(f"SELECT 1 FROM {SCHEMA}.properties LIMIT 1"))
        return SCHEMA
    except Exception:
        return _FALLBACK_SCHEMA


# Crime category severity weights (higher = more severe impact on property development)
CATEGORY_WEIGHTS = {
    # Contact crimes (most severe for property)
    "Murder": 10.0,
    "Attempted murder": 8.0,
    "Sexual offences": 7.0,
    "Assault with intent to inflict grievous bodily harm": 6.0,
    "Common assault": 4.0,
    "Robbery with aggravating circumstances": 8.0,
    "Common robbery": 5.0,
    "Carjacking": 7.0,

    # Property crimes (direct impact)
    "Burglary at residential premises": 8.0,
    "Burglary at non-residential premises": 7.0,
    "Theft of motor vehicle and motorcycle": 6.0,
    "Theft out of or from motor vehicle": 5.0,
    "Stock theft": 3.0,
    "Shoplifting": 2.0,
    "All theft not mentioned elsewhere": 4.0,

    # Damage to property
    "Malicious damage to property": 5.0,
    "Arson": 7.0,

    # Drug-related
    "Drug-related crime": 3.0,
    "Driving under the influence of alcohol or drugs": 3.0,

    # Other
    "Illegal possession of firearms and ammunition": 6.0,
    "Sexual offences as a result of police action": 2.0,
    "Kidnapping": 7.0,
    "Public violence": 5.0,
    "Crimen injuria": 2.0,
}

# National averages per 100k population (approximate, for benchmarking)
NATIONAL_BENCHMARKS = {
    "Murder": 45,
    "Burglary at residential premises": 400,
    "Robbery with aggravating circumstances": 250,
    "Carjacking": 30,
    "Common assault": 300,
}


def calculate_crime_risk(property_id: int) -> dict:
    """
    Calculate crime risk assessment for a property.

    Returns:
        dict with risk_level, score, breakdown by category, trends, recommendations
    """
    engine = _get_engine()

    with engine.connect() as conn:
        schema = _get_schema(conn)

        # Get property details
        prop = conn.execute(text(f"""
            SELECT p.id, p.erf_number, p.suburb, p.zoning_primary,
                   p.centroid_lat, p.centroid_lon
            FROM {schema}.properties p
            WHERE p.id = :id
        """), {"id": property_id}).mappings().fetchone()

        if not prop:
            return {"error": "Property not found"}

        prop = dict(prop)

        # Try to find crime data from police_stations table
        crime_data = None
        station_info = None
        try:
            station = conn.execute(text(f"""
                SELECT ps.id, ps.station_name, ps.province
                FROM {schema}.police_stations ps
                WHERE ST_Contains(ps.geom, (SELECT ST_Centroid(geom) FROM {schema}.properties WHERE id = :id))
                LIMIT 1
            """), {"id": property_id}).mappings().fetchone()

            if station:
                station_info = dict(station)

                # Get crime stats for this station
                stats = conn.execute(text(f"""
                    SELECT cs.category, cs.year, cs.count
                    FROM {schema}.crime_stats cs
                    WHERE cs.station_id = :sid
                    ORDER BY cs.year DESC, cs.category
                """), {"sid": station["id"]}).mappings().fetchall()

                if stats:
                    crime_data = [dict(s) for s in stats]
        except Exception:
            # Tables don't exist yet — provide estimated scores based on suburb
            pass

        # If no real data, estimate based on suburb characteristics
        if not crime_data:
            return _estimate_crime_risk(prop)

        # Calculate weighted crime score from actual data
        latest_year = max(s["year"] for s in crime_data)
        latest_stats = {s["category"]: s["count"] for s in crime_data if s["year"] == latest_year}

        total_weighted = 0
        total_weight = 0
        category_scores = []

        for category, count in latest_stats.items():
            weight = CATEGORY_WEIGHTS.get(category, 3.0)
            weighted_score = count * weight
            total_weighted += weighted_score
            total_weight += weight
            category_scores.append({
                "category": category,
                "count": count,
                "weight": weight,
                "weighted_score": round(weighted_score, 1),
            })

        # Normalize to 0-100 scale
        crime_score = min(100, round(total_weighted / max(total_weight, 1) * 10, 1))

        if crime_score > 70:
            risk_level = "Critical"
        elif crime_score > 50:
            risk_level = "High"
        elif crime_score > 30:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        # Sort by weighted score descending
        category_scores.sort(key=lambda x: x["weighted_score"], reverse=True)

        return {
            "property_id": property_id,
            "suburb": prop["suburb"],
            "station": station_info,
            "risk_level": risk_level,
            "crime_score": crime_score,
            "year": latest_year,
            "top_categories": category_scores[:10],
            "recommendations": _crime_recommendations(risk_level, prop.get("zoning_primary", "")),
        }


def _estimate_crime_risk(prop: dict) -> dict:
    """Estimate crime risk when no station data is available."""
    suburb = (prop.get("suburb") or "").upper()

    # Rough suburb-level risk tiers for Cape Town (simplified)
    low_risk = {"CONSTANTIA", "BISHOPSCOURT", "NEWLANDS", "CLAREMONT", "CAMPS BAY",
                "BANTRY BAY", "CLIFTON", "LLANDUDNO", "HOUT BAY", "TOKAI",
                "BERGVLIET", "PLUMSTEAD", "RONDEBOSCH", "DURBANVILLE"}
    medium_risk = {"OBSERVATORY", "WOODSTOCK", "SALT RIVER", "MOWBRAY",
                   "SEA POINT", "GREEN POINT", "FISH HOEK", "SIMON'S TOWN",
                   "MUIZENBERG", "MILNERTON", "TABLE VIEW", "PARKLANDS"}

    if suburb in low_risk:
        score, level = 25, "Low"
    elif suburb in medium_risk:
        score, level = 45, "Medium"
    else:
        score, level = 55, "Medium"

    return {
        "property_id": prop["id"],
        "suburb": prop["suburb"],
        "station": None,
        "risk_level": level,
        "crime_score": score,
        "year": None,
        "top_categories": [],
        "estimated": True,
        "note": "Estimate based on suburb profile. Load SAPS crime data for precise station-level analysis.",
        "recommendations": _crime_recommendations(level, prop.get("zoning_primary", "")),
    }


def _crime_recommendations(risk_level: str, zoning: str) -> list:
    """Generate crime-related recommendations for property development."""
    recs = []

    if risk_level in ("Critical", "High"):
        recs.append({
            "action": "Install perimeter security (electric fencing, CCTV, access control)",
            "priority": 1,
            "cost_estimate_zar": "R50,000 - R200,000",
        })
        recs.append({
            "action": "Engage private security patrol service",
            "priority": 1,
            "cost_estimate_zar": "R2,000 - R5,000/month",
        })
        recs.append({
            "action": "Consider CPTED (Crime Prevention Through Environmental Design) principles",
            "priority": 2,
            "cost_estimate_zar": "Included in architectural design",
        })

    recs.append({
        "action": "Install alarm system linked to armed response",
        "priority": 2 if risk_level in ("Critical", "High") else 3,
        "cost_estimate_zar": "R5,000 - R15,000 + R500-R1,500/month",
    })

    if "RESIDENTIAL" in zoning.upper():
        recs.append({
            "action": "Join or establish neighbourhood watch / community policing forum",
            "priority": 3,
            "cost_estimate_zar": "Minimal",
        })

    return recs


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) > 1:
        result = calculate_crime_risk(int(sys.argv[1]))
        print(json.dumps(result, indent=2, default=str))
    else:
        print("Usage: python crime_engine.py <property_id>")
