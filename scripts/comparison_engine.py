#!/usr/bin/env python3
"""
Cape Town Property Comparison Engine

Provides:
  1. compare_radius(property_id, radius_km) — find cheapest/most expensive in radius
  2. compare_suburb(property_id) — find cheapest/most expensive in same suburb
  3. get_construction_costs(zoning_primary) — Cape Town construction cost benchmarks
"""

import logging
import os
import statistics
from contextlib import contextmanager

from sqlalchemy import create_engine, text

log = logging.getLogger(__name__)

SCHEMA = "capeeco"

# Cape Town construction cost benchmarks (ZAR/m², 2024/2025)
# Sources: AECOM Africa Cost Guide 2024/25, Ooba, StatsSA
CONSTRUCTION_COSTS = {
    "residential_economic": {"label": "Residential (Economic)", "cost_per_sqm": 6500, "range": [5500, 8000]},
    "residential_standard": {"label": "Residential (Standard)", "cost_per_sqm": 13150, "range": [10000, 17000]},
    "residential_high_end": {"label": "Residential (High-end)", "cost_per_sqm": 20000, "range": [17000, 30000]},
    "residential_luxury":   {"label": "Residential (Luxury)", "cost_per_sqm": 35000, "range": [30000, 75000]},
    "commercial_office":    {"label": "Commercial (Office)", "cost_per_sqm": 17500, "range": [15000, 20000]},
    "commercial_retail":    {"label": "Commercial (Retail)", "cost_per_sqm": 15000, "range": [12000, 18000]},
    "industrial":           {"label": "Industrial", "cost_per_sqm": 8000, "range": [6000, 12000]},
    "mixed_use":            {"label": "Mixed Use", "cost_per_sqm": 15000, "range": [12000, 20000]},
}

# Map zoning codes to construction cost categories
ZONING_TO_COST = {
    "Single Residential": "residential_standard",
    "General Residential": "residential_standard",
    "Community Residential": "residential_economic",
    "Incremental Development": "residential_economic",
    "General Business": "commercial_retail",
    "Local Business": "commercial_retail",
    "Mixed Use": "mixed_use",
    "General Industry": "industrial",
    "Light Industry": "industrial",
    "Risk Industry": "industrial",
    "Transport": "industrial",
    "Utility": "industrial",
    "Open Space": None,
    "Community": "commercial_office",
    "Authority": "commercial_office",
}


def _conn_string():
    db_url = os.environ.get("DATABASE_URL")
    if db_url is None:
        for k, v in os.environ.items():
            if k.strip() == "DATABASE_URL":
                db_url = v
                break
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return db_url
    pw = os.environ.get("PGPASSWORD", "")
    host = os.environ.get("PGHOST", "localhost")
    port = os.environ.get("PGPORT", "5432")
    user = os.environ.get("PGUSER", os.environ.get("USER", "postgres"))
    name = os.environ.get("PGDATABASE", "capeeco")
    return f"postgresql://{user}:{pw}@{host}:{port}/{name}" if pw else f"postgresql://{user}@{host}:{port}/{name}"


_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(_conn_string(), pool_pre_ping=True)
    return _engine


@contextmanager
def _connection():
    eng = _get_engine()
    with eng.connect() as conn:
        yield conn


def _zoning_cost_key(zoning_primary: str | None) -> str | None:
    """Map a zoning_primary string to a construction cost category key."""
    if not zoning_primary:
        return "residential_standard"
    zp = zoning_primary.split(":")[0].strip()
    for prefix, key in ZONING_TO_COST.items():
        if zp.startswith(prefix):
            return key
    # Default to residential standard
    return "residential_standard"


def compare_radius(property_id: int, radius_km: float = 1.0, max_properties: int = 200) -> dict:
    """
    Find properties within radius_km of the given property, fetch their
    valuations, and return cheapest/most expensive + stats.
    """
    from valuation_scraper import fetch_and_cache_valuations

    radius_m = radius_km * 1000

    with _connection() as conn:
        # Get the selected property
        prop = conn.execute(text(f"""
            SELECT id, erf_number, suburb, area_sqm, zoning_primary,
                   centroid_lon, centroid_lat, ST_AsText(ST_Centroid(geom)) as centroid_wkt
            FROM {SCHEMA}.properties WHERE id = :id
        """), {"id": property_id}).mappings().fetchone()

        if not prop:
            return {"error": "Property not found"}

        # Find nearby properties using PostGIS ST_DWithin (geography for metres)
        nearby = conn.execute(text(f"""
            SELECT p.id, p.erf_number, p.suburb, p.area_sqm, p.zoning_primary,
                   p.full_address, p.centroid_lon, p.centroid_lat,
                   ST_Distance(
                       p.geom::geography,
                       (SELECT geom::geography FROM {SCHEMA}.properties WHERE id = :id)
                   ) AS distance_m
            FROM {SCHEMA}.properties p
            WHERE p.id != :id
              AND ST_DWithin(
                  p.geom::geography,
                  (SELECT geom::geography FROM {SCHEMA}.properties WHERE id = :id),
                  :radius
              )
              AND p.area_sqm > 0
            ORDER BY distance_m
            LIMIT :max_props
        """), {"id": property_id, "radius": radius_m, "max_props": max_properties}).mappings().fetchall()

        nearby_list = [dict(r) for r in nearby]

    if not nearby_list:
        return {
            "error": None,
            "selected_property": _format_property(prop, None),
            "radius_km": radius_km,
            "count": 0,
            "cheapest": None,
            "most_expensive": None,
            "stats": None,
            "properties": [],
        }

    # Fetch valuations for all nearby + selected
    all_ids = [property_id] + [n["id"] for n in nearby_list]
    valuations = fetch_and_cache_valuations(all_ids)

    # Attach values and filter to properties with valuations
    selected_val = valuations.get(property_id)
    valued_nearby = []
    for n in nearby_list:
        val = valuations.get(n["id"])
        if val and val > 0:
            n["market_value_zar"] = val
            n["value_per_sqm"] = val / n["area_sqm"] if n["area_sqm"] else None
            valued_nearby.append(n)

    if not valued_nearby:
        return {
            "error": None,
            "selected_property": _format_property(prop, selected_val),
            "radius_km": radius_km,
            "count": 0,
            "cheapest": None,
            "most_expensive": None,
            "stats": None,
            "properties": [],
        }

    # Sort by value
    valued_nearby.sort(key=lambda x: x["market_value_zar"])
    cheapest = valued_nearby[0]
    most_expensive = valued_nearby[-1]

    # Stats
    values = [n["market_value_zar"] for n in valued_nearby]
    per_sqm_values = [n["value_per_sqm"] for n in valued_nearby if n.get("value_per_sqm")]

    return {
        "error": None,
        "selected_property": _format_property(prop, selected_val),
        "radius_km": radius_km,
        "count": len(valued_nearby),
        "total_in_radius": len(nearby_list),
        "cheapest": _format_nearby(cheapest),
        "most_expensive": _format_nearby(most_expensive),
        "stats": {
            "median_value": round(statistics.median(values)),
            "mean_value": round(statistics.mean(values)),
            "min_value": round(min(values)),
            "max_value": round(max(values)),
            "median_per_sqm": round(statistics.median(per_sqm_values)) if per_sqm_values else None,
            "count_valued": len(valued_nearby),
        },
        "properties": [_format_nearby(n) for n in valued_nearby],
    }


def compare_suburb(property_id: int, max_properties: int = 500) -> dict:
    """
    Find cheapest/most expensive properties in the same suburb.
    """
    from valuation_scraper import fetch_and_cache_valuations

    with _connection() as conn:
        prop = conn.execute(text(f"""
            SELECT id, erf_number, suburb, area_sqm, zoning_primary,
                   centroid_lon, centroid_lat
            FROM {SCHEMA}.properties WHERE id = :id
        """), {"id": property_id}).mappings().fetchone()

        if not prop:
            return {"error": "Property not found"}

        if not prop["suburb"]:
            return {"error": "Property has no suburb", "selected_property": _format_property(prop, None)}

        # Get properties in same suburb
        suburb_props = conn.execute(text(f"""
            SELECT id, erf_number, suburb, area_sqm, zoning_primary,
                   full_address, centroid_lon, centroid_lat
            FROM {SCHEMA}.properties
            WHERE suburb = :suburb AND id != :id AND area_sqm > 0
            ORDER BY area_sqm DESC
            LIMIT :max_props
        """), {"suburb": prop["suburb"], "id": property_id, "max_props": max_properties}).mappings().fetchall()

        suburb_list = [dict(r) for r in suburb_props]

    if not suburb_list:
        return {
            "error": None,
            "selected_property": _format_property(prop, None),
            "suburb": prop["suburb"],
            "count": 0,
            "cheapest": None,
            "most_expensive": None,
            "stats": None,
            "properties": [],
        }

    all_ids = [property_id] + [s["id"] for s in suburb_list]
    valuations = fetch_and_cache_valuations(all_ids)

    selected_val = valuations.get(property_id)
    valued = []
    for s in suburb_list:
        val = valuations.get(s["id"])
        if val and val > 0:
            s["market_value_zar"] = val
            s["value_per_sqm"] = val / s["area_sqm"] if s["area_sqm"] else None
            valued.append(s)

    if not valued:
        return {
            "error": None,
            "selected_property": _format_property(prop, selected_val),
            "suburb": prop["suburb"],
            "count": 0,
            "cheapest": None,
            "most_expensive": None,
            "stats": None,
            "properties": [],
        }

    valued.sort(key=lambda x: x["market_value_zar"])
    values = [v["market_value_zar"] for v in valued]
    per_sqm = [v["value_per_sqm"] for v in valued if v.get("value_per_sqm")]

    return {
        "error": None,
        "selected_property": _format_property(prop, selected_val),
        "suburb": prop["suburb"],
        "count": len(valued),
        "cheapest": _format_nearby(valued[0]),
        "most_expensive": _format_nearby(valued[-1]),
        "stats": {
            "median_value": round(statistics.median(values)),
            "mean_value": round(statistics.mean(values)),
            "min_value": round(min(values)),
            "max_value": round(max(values)),
            "median_per_sqm": round(statistics.median(per_sqm)) if per_sqm else None,
            "count_valued": len(valued),
        },
        "properties": [_format_nearby(v) for v in valued[:50]],  # limit response size
    }


def get_construction_costs(zoning_primary: str | None = None) -> dict:
    """Return construction cost benchmarks for a given zoning type."""
    key = _zoning_cost_key(zoning_primary)
    if key and key in CONSTRUCTION_COSTS:
        matched = CONSTRUCTION_COSTS[key]
        return {
            "zoning": zoning_primary,
            "matched_category": key,
            "cost_per_sqm": matched["cost_per_sqm"],
            "cost_range": matched["range"],
            "label": matched["label"],
            "all_categories": CONSTRUCTION_COSTS,
        }
    return {
        "zoning": zoning_primary,
        "matched_category": None,
        "cost_per_sqm": None,
        "cost_range": None,
        "label": None,
        "all_categories": CONSTRUCTION_COSTS,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _format_property(prop, market_value):
    area = prop["area_sqm"] or 0
    return {
        "id": prop["id"],
        "erf_number": prop["erf_number"],
        "suburb": prop["suburb"],
        "area_sqm": round(area, 1) if area else None,
        "zoning_primary": prop["zoning_primary"],
        "market_value_zar": round(market_value) if market_value else None,
        "value_per_sqm": round(market_value / area) if market_value and area else None,
        "centroid_lat": prop.get("centroid_lat"),
        "centroid_lon": prop.get("centroid_lon"),
    }


def _format_nearby(n):
    return {
        "id": n["id"],
        "erf_number": n["erf_number"],
        "suburb": n["suburb"],
        "area_sqm": round(n["area_sqm"], 1) if n.get("area_sqm") else None,
        "zoning_primary": n.get("zoning_primary"),
        "full_address": n.get("full_address"),
        "market_value_zar": round(n["market_value_zar"]) if n.get("market_value_zar") else None,
        "value_per_sqm": round(n["value_per_sqm"]) if n.get("value_per_sqm") else None,
        "distance_m": round(n["distance_m"]) if n.get("distance_m") else None,
        "centroid_lat": n.get("centroid_lat"),
        "centroid_lon": n.get("centroid_lon"),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 2:
        print("Usage: python comparison_engine.py <property_id> [radius_km]")
        sys.exit(1)

    pid = int(sys.argv[1])
    radius = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0

    print(f"\n--- Radius comparison ({radius} km) ---")
    r = compare_radius(pid, radius)
    if r.get("cheapest"):
        c = r["cheapest"]
        print(f"Cheapest:        R {c['market_value_zar']:>12,}  ({c['value_per_sqm']:,}/m²)  {c['full_address']}")
    if r.get("most_expensive"):
        e = r["most_expensive"]
        print(f"Most expensive:  R {e['market_value_zar']:>12,}  ({e['value_per_sqm']:,}/m²)  {e['full_address']}")
    if r.get("stats"):
        print(f"Median value:    R {r['stats']['median_value']:>12,}")
        print(f"Properties with values: {r['stats']['count_valued']}")

    print(f"\n--- Suburb comparison ---")
    s = compare_suburb(pid)
    if s.get("cheapest"):
        c = s["cheapest"]
        print(f"Cheapest:        R {c['market_value_zar']:>12,}  ({c['value_per_sqm']:,}/m²)")
    if s.get("most_expensive"):
        e = s["most_expensive"]
        print(f"Most expensive:  R {e['market_value_zar']:>12,}  ({e['value_per_sqm']:,}/m²)")

    print(f"\n--- Construction costs ---")
    sel = r.get("selected_property", {})
    cc = get_construction_costs(sel.get("zoning_primary"))
    if cc["cost_per_sqm"]:
        print(f"Zoning: {cc['label']}  →  R {cc['cost_per_sqm']:,}/m²  (range: R {cc['cost_range'][0]:,}–{cc['cost_range'][1]:,})")
