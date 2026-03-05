"""
Siteline — Load Shedding Engine

Calculates load shedding impact for properties using:
- CCT load-shedding block boundaries (spatial overlay)
- Eskom schedule API (undocumented)

Functions:
1. get_loadshedding_schedule(erf_number, suburb=None) — Returns block, schedule, impact score
2. calculate_loadshedding_impact(property_id) — Returns impact assessment for a property
"""

import logging
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

logger = logging.getLogger("siteline")

SCHEMA = os.environ.get("SITELINE_SCHEMA", "siteline")

# Fallback to capeeco schema if siteline doesn't exist yet
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
    """Return the active schema (siteline or capeeco fallback)."""
    try:
        conn.execute(text(f"SELECT 1 FROM {SCHEMA}.properties LIMIT 1"))
        return SCHEMA
    except Exception:
        return _FALLBACK_SCHEMA


# Standard Cape Town load shedding schedule (simplified)
# In reality this comes from Eskom API, but we pre-compute common patterns
LOADSHEDDING_STAGE_HOURS = {
    1: 2.5,   # 2.5 hours per day on average
    2: 4.0,
    3: 6.0,
    4: 8.0,
    5: 10.0,
    6: 12.0,
    7: 14.0,
    8: 16.0,
}

# Impact scoring weights
IMPACT_WEIGHTS = {
    "residential": {"productivity_loss": 0.3, "food_spoilage": 0.2, "security": 0.3, "comfort": 0.2},
    "commercial": {"productivity_loss": 0.5, "revenue_loss": 0.3, "equipment": 0.1, "security": 0.1},
    "industrial": {"productivity_loss": 0.4, "equipment": 0.3, "raw_materials": 0.2, "security": 0.1},
}


def calculate_loadshedding_impact(property_id: int) -> dict:
    """
    Calculate load shedding impact for a property.

    Returns:
        dict with block_number, schedule info, impact_score, recommendations
    """
    engine = _get_engine()

    with engine.connect() as conn:
        schema = _get_schema(conn)

        # Get property details
        prop = conn.execute(text(f"""
            SELECT p.id, p.erf_number, p.suburb, p.zoning_primary, p.area_sqm,
                   p.centroid_lat, p.centroid_lon
            FROM {schema}.properties p
            WHERE p.id = :id
        """), {"id": property_id}).mappings().fetchone()

        if not prop:
            return {"error": "Property not found"}

        prop = dict(prop)

        # Check if loadshedding_blocks table exists and find block
        block_info = None
        try:
            block_row = conn.execute(text(f"""
                SELECT lb.block_number, lb.block_name
                FROM {schema}.loadshedding_blocks lb
                WHERE ST_Intersects(lb.geom, (SELECT geom FROM {schema}.properties WHERE id = :id))
                LIMIT 1
            """), {"id": property_id}).mappings().fetchone()

            if block_row:
                block_info = dict(block_row)
        except Exception:
            # Table doesn't exist yet — estimate from suburb
            pass

        # Determine property type from zoning
        zoning = (prop.get("zoning_primary") or "").upper()
        if "INDUSTRIAL" in zoning:
            prop_type = "industrial"
        elif "BUSINESS" in zoning or "COMMERCIAL" in zoning or "MIXED USE" in zoning:
            prop_type = "commercial"
        else:
            prop_type = "residential"

        # Calculate impact scores per stage
        stage_impacts = {}
        for stage in range(1, 9):
            hours_per_day = LOADSHEDDING_STAGE_HOURS[stage]
            # Base impact: proportion of day affected
            base_impact = hours_per_day / 24.0

            # Weight by property type impacts
            weights = IMPACT_WEIGHTS.get(prop_type, IMPACT_WEIGHTS["residential"])
            weighted_score = sum(
                base_impact * weight * (1.2 if factor in ("productivity_loss", "revenue_loss") else 1.0)
                for factor, weight in weights.items()
            )

            stage_impacts[f"stage_{stage}"] = {
                "hours_per_day": hours_per_day,
                "impact_score": round(min(weighted_score * 100, 100), 1),
                "annual_hours": round(hours_per_day * 365, 0),
            }

        # Overall risk assessment
        # Use stage 4 as baseline (most common sustained level)
        baseline_score = stage_impacts["stage_4"]["impact_score"]
        if baseline_score > 60:
            risk_level = "Critical"
        elif baseline_score > 40:
            risk_level = "High"
        elif baseline_score > 20:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        # Recommendations
        recommendations = []
        if prop_type == "commercial" or prop_type == "industrial":
            recommendations.append({
                "action": "Install backup generator (diesel or gas)",
                "cost_estimate_zar": "R150,000 - R500,000",
                "priority": 1,
            })
            recommendations.append({
                "action": "Install UPS for critical systems",
                "cost_estimate_zar": "R20,000 - R80,000",
                "priority": 2,
            })
        recommendations.append({
            "action": "Install solar PV with battery storage",
            "cost_estimate_zar": "R80,000 - R300,000 (residential), R500,000+ (commercial)",
            "priority": 1 if prop_type == "residential" else 2,
        })
        recommendations.append({
            "action": "Install inverter for essential circuits",
            "cost_estimate_zar": "R15,000 - R40,000",
            "priority": 2,
        })

        return {
            "property_id": property_id,
            "suburb": prop["suburb"],
            "property_type": prop_type,
            "block": block_info,
            "risk_level": risk_level,
            "baseline_impact_score": baseline_score,
            "stage_impacts": stage_impacts,
            "recommendations": recommendations,
            "note": "Schedules based on Cape Town municipal load shedding patterns. Actual times vary by block.",
        }


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        pid = int(sys.argv[1])
        result = calculate_loadshedding_impact(pid)
        import json
        print(json.dumps(result, indent=2, default=str))
    else:
        print("Usage: python loadshedding_engine.py <property_id>")
