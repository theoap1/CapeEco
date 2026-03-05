"""
Siteline — Municipal Finance & Infrastructure Engine

Assesses municipal infrastructure health using:
- Municipal Money API (National Treasury data)
- Municipal financial performance indicators
- Infrastructure spending analysis

Functions:
1. calculate_municipal_health(property_id) — Returns infrastructure health score, breakdown
"""

import logging
import os

import httpx
from sqlalchemy import create_engine, text

logger = logging.getLogger("siteline")

SCHEMA = os.environ.get("SITELINE_SCHEMA", "siteline")
_FALLBACK_SCHEMA = "capeeco"

MUNICIPAL_MONEY_API = "https://municipalmoney.gov.za/api"


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


# Cape Town municipal data (pre-computed from National Treasury)
# City of Cape Town municipality code: CPT
CAPE_TOWN_FINANCIAL = {
    "municipality": "City of Cape Town",
    "demarcation_code": "CPT",
    "province": "Western Cape",
    "metro": True,
    "financial_years": {
        "2022/23": {
            "audit_opinion": "Unqualified with findings",
            "cash_coverage": 2.1,  # months of cash to cover operating expenses
            "capital_budget_spent_pct": 87.3,
            "repairs_maintenance_pct": 8.2,  # % of property, plant & equipment
            "revenue_collection_pct": 95.1,
            "current_ratio": 1.8,
            "debt_to_revenue_ratio": 35.2,
        },
        "2021/22": {
            "audit_opinion": "Unqualified with findings",
            "cash_coverage": 1.9,
            "capital_budget_spent_pct": 82.1,
            "repairs_maintenance_pct": 7.8,
            "revenue_collection_pct": 94.3,
            "current_ratio": 1.7,
            "debt_to_revenue_ratio": 37.8,
        },
        "2020/21": {
            "audit_opinion": "Unqualified with findings",
            "cash_coverage": 1.6,
            "capital_budget_spent_pct": 78.5,
            "repairs_maintenance_pct": 7.1,
            "revenue_collection_pct": 92.8,
            "current_ratio": 1.5,
            "debt_to_revenue_ratio": 40.1,
        },
    }
}

# Benchmark thresholds (National Treasury norms)
BENCHMARKS = {
    "cash_coverage": {"good": 3.0, "acceptable": 1.5, "poor": 1.0},
    "capital_budget_spent_pct": {"good": 90, "acceptable": 75, "poor": 60},
    "repairs_maintenance_pct": {"good": 8.0, "acceptable": 5.0, "poor": 3.0},
    "revenue_collection_pct": {"good": 95, "acceptable": 90, "poor": 85},
    "current_ratio": {"good": 2.0, "acceptable": 1.5, "poor": 1.0},
    "debt_to_revenue_ratio": {"good": 30, "acceptable": 45, "poor": 60},
}


def _score_metric(value, benchmark, higher_is_better=True):
    """Score a metric 0-100 based on benchmarks."""
    if value is None:
        return 50  # neutral

    if higher_is_better:
        if value >= benchmark["good"]:
            return 90
        elif value >= benchmark["acceptable"]:
            return 65
        elif value >= benchmark["poor"]:
            return 40
        else:
            return 20
    else:
        # Lower is better (e.g., debt ratio)
        if value <= benchmark["good"]:
            return 90
        elif value <= benchmark["acceptable"]:
            return 65
        elif value <= benchmark["poor"]:
            return 40
        else:
            return 20


def calculate_municipal_health(property_id: int) -> dict:
    """
    Calculate municipal infrastructure health for a property's municipality.

    Returns:
        dict with overall health score, breakdown by indicator, trends, recommendations
    """
    engine = _get_engine()

    with engine.connect() as conn:
        schema = _get_schema(conn)

        # Get property details
        prop = conn.execute(text(f"""
            SELECT p.id, p.erf_number, p.suburb, p.centroid_lat, p.centroid_lon
            FROM {schema}.properties p
            WHERE p.id = :id
        """), {"id": property_id}).mappings().fetchone()

        if not prop:
            return {"error": "Property not found"}

        prop = dict(prop)

    # For now, all Cape Town properties get City of Cape Town data
    # Future: use MapIt API to resolve municipality for non-CPT properties
    municipality = CAPE_TOWN_FINANCIAL

    # Get latest financial year data
    latest_year = max(municipality["financial_years"].keys())
    latest_data = municipality["financial_years"][latest_year]

    # Score each indicator
    indicators = {
        "cash_coverage": {
            "value": latest_data["cash_coverage"],
            "score": _score_metric(latest_data["cash_coverage"], BENCHMARKS["cash_coverage"]),
            "unit": "months",
            "label": "Cash Coverage",
            "description": "Months of cash reserves to cover operating expenses",
        },
        "capital_budget_execution": {
            "value": latest_data["capital_budget_spent_pct"],
            "score": _score_metric(latest_data["capital_budget_spent_pct"], BENCHMARKS["capital_budget_spent_pct"]),
            "unit": "%",
            "label": "Capital Budget Execution",
            "description": "Percentage of capital budget actually spent on infrastructure",
        },
        "repairs_maintenance": {
            "value": latest_data["repairs_maintenance_pct"],
            "score": _score_metric(latest_data["repairs_maintenance_pct"], BENCHMARKS["repairs_maintenance_pct"]),
            "unit": "%",
            "label": "Repairs & Maintenance",
            "description": "Spend on repairs as % of property, plant & equipment",
        },
        "revenue_collection": {
            "value": latest_data["revenue_collection_pct"],
            "score": _score_metric(latest_data["revenue_collection_pct"], BENCHMARKS["revenue_collection_pct"]),
            "unit": "%",
            "label": "Revenue Collection",
            "description": "Percentage of billed revenue actually collected",
        },
        "financial_health": {
            "value": latest_data["current_ratio"],
            "score": _score_metric(latest_data["current_ratio"], BENCHMARKS["current_ratio"]),
            "unit": "ratio",
            "label": "Current Ratio",
            "description": "Current assets divided by current liabilities",
        },
        "debt_sustainability": {
            "value": latest_data["debt_to_revenue_ratio"],
            "score": _score_metric(latest_data["debt_to_revenue_ratio"], BENCHMARKS["debt_to_revenue_ratio"], higher_is_better=False),
            "unit": "%",
            "label": "Debt-to-Revenue",
            "description": "Total borrowing as % of total revenue",
        },
    }

    # Overall score (weighted average)
    weights = {
        "cash_coverage": 0.15,
        "capital_budget_execution": 0.20,
        "repairs_maintenance": 0.20,
        "revenue_collection": 0.15,
        "financial_health": 0.15,
        "debt_sustainability": 0.15,
    }

    overall_score = sum(indicators[k]["score"] * weights[k] for k in indicators)
    overall_score = round(overall_score, 1)

    if overall_score >= 75:
        health_level = "Good"
    elif overall_score >= 55:
        health_level = "Fair"
    elif overall_score >= 35:
        health_level = "Concerning"
    else:
        health_level = "Poor"

    # Trend analysis
    years_data = []
    for year in sorted(municipality["financial_years"].keys()):
        yd = municipality["financial_years"][year]
        years_data.append({
            "year": year,
            "capital_budget_spent_pct": yd["capital_budget_spent_pct"],
            "repairs_maintenance_pct": yd["repairs_maintenance_pct"],
            "revenue_collection_pct": yd["revenue_collection_pct"],
        })

    # Recommendations
    recommendations = []
    if indicators["capital_budget_execution"]["score"] < 65:
        recommendations.append({
            "concern": "Low capital budget execution may indicate infrastructure backlogs",
            "implication": "New developments may face delayed municipal services connections",
            "action": "Verify service availability before purchase",
        })
    if indicators["repairs_maintenance"]["score"] < 65:
        recommendations.append({
            "concern": "Below-benchmark maintenance spending",
            "implication": "Existing infrastructure (water, sewer, roads) may be deteriorating",
            "action": "Conduct infrastructure capacity assessment for the area",
        })
    if latest_data["audit_opinion"] != "Unqualified":
        recommendations.append({
            "concern": f"Audit opinion: {latest_data['audit_opinion']}",
            "implication": "Financial management concerns may affect service delivery",
            "action": "Factor in potential service delivery risks",
        })

    return {
        "property_id": property_id,
        "suburb": prop["suburb"],
        "municipality": municipality["municipality"],
        "demarcation_code": municipality["demarcation_code"],
        "financial_year": latest_year,
        "audit_opinion": latest_data["audit_opinion"],
        "health_level": health_level,
        "overall_score": overall_score,
        "indicators": indicators,
        "trends": years_data,
        "recommendations": recommendations,
    }


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) > 1:
        result = calculate_municipal_health(int(sys.argv[1]))
        print(json.dumps(result, indent=2, default=str))
    else:
        print("Usage: python municipal_engine.py <property_id>")
