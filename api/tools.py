"""
Siteline AI Tools — Functions available to the AI chat agent.

Each tool wraps an existing engine/database query and returns structured data
that gets sent back to the AI for interpretation.
"""

import sys
from pathlib import Path

from sqlalchemy import text
from api.db import get_engine, SCHEMA

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from biodiversity_engine import calculate_offset_requirement, generate_constraint_map
from netzero_engine import calculate_solar_potential, calculate_water_harvesting, netzero_scorecard
from comparison_engine import compare_radius, compare_suburb, get_construction_costs
from loadshedding_engine import calculate_loadshedding_impact
from crime_engine import calculate_crime_risk
from municipal_engine import calculate_municipal_health
from site_plan_engine import calculate_development_potential, generate_site_plan_geojson, generate_massing_geojson, generate_unit_layout


# Tool definitions for DeepSeek function calling
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_property",
            "description": "Search for a property by address, ERF number, or suburb. Returns matching properties with IDs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Address, ERF number, or suburb to search for"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_property_details",
            "description": "Get full details for a property including area, zoning, biodiversity overlays, and heritage sites.",
            "parameters": {
                "type": "object",
                "properties": {
                    "property_id": {"type": "integer", "description": "Property ID from search results"}
                },
                "required": ["property_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_biodiversity",
            "description": "Calculate biodiversity offset requirements for a property. Returns offset ratio, required hectares, cost estimate, and no-go flags.",
            "parameters": {
                "type": "object",
                "properties": {
                    "property_id": {"type": "integer", "description": "Property ID"},
                    "footprint_sqm": {"type": "number", "description": "Proposed development footprint in m². Defaults to 40% of property area."}
                },
                "required": ["property_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_netzero",
            "description": "Run full net zero analysis including Green Star rating, solar potential, and water harvesting for a property.",
            "parameters": {
                "type": "object",
                "properties": {
                    "property_id": {"type": "integer", "description": "Property ID"}
                },
                "required": ["property_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_properties",
            "description": "Compare property valuations within a radius. Returns cheapest, most expensive, and statistics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "property_id": {"type": "integer", "description": "Property ID"},
                    "radius_km": {"type": "number", "description": "Search radius in km (default 1.0)", "default": 1.0}
                },
                "required": ["property_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_constraint_map",
            "description": "Generate a constraint map showing developable vs constrained areas on a property.",
            "parameters": {
                "type": "object",
                "properties": {
                    "property_id": {"type": "integer", "description": "Property ID"}
                },
                "required": ["property_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_loadshedding",
            "description": "Get load shedding impact assessment for a property. Returns block assignment, stage impacts, risk level, and backup power recommendations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "property_id": {"type": "integer", "description": "Property ID"}
                },
                "required": ["property_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_crime_stats",
            "description": "Get crime risk assessment for a property based on SAPS police station data. Returns risk score, breakdown by crime category, and security recommendations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "property_id": {"type": "integer", "description": "Property ID"}
                },
                "required": ["property_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_municipal_health",
            "description": "Get municipal infrastructure health assessment based on National Treasury financial data. Returns scores for cash coverage, capital budget execution, maintenance spending, and service delivery capacity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "property_id": {"type": "integer", "description": "Property ID"}
                },
                "required": ["property_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_development_potential",
            "description": "Calculate full development potential for a property: buildable envelope, yield (GFA, units, floors), unit mix breakdown (studios, 1-bed, 2-bed, 3-bed with counts and sizes), parking (resident + visitor bays, surface vs basement), financial feasibility (construction cost, revenue, profit margin, ROI), and density metrics (units/ha, beds/ha). Based on Cape Town Zoning Scheme (CTZS) regulations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "property_id": {"type": "integer", "description": "Property ID"}
                },
                "required": ["property_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_site_massing",
            "description": "Generate building massing with per-floor plates showing the 3D building layout on the site. Returns GeoJSON with building footprint, floor plates (with use type per floor), and parking zone. Also provides floor-by-floor unit layout with individual unit placement, corridor/core positions, and parking grid.",
            "parameters": {
                "type": "object",
                "properties": {
                    "property_id": {"type": "integer", "description": "Property ID"}
                },
                "required": ["property_id"]
            }
        }
    },
]


def _lookup_erf(property_id):
    """Get erf_number, suburb, area_sqm for a property_id."""
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(text(f"""
            SELECT erf_number, suburb, area_sqm FROM {SCHEMA}.properties WHERE id = :id
        """), {"id": property_id}).mappings().fetchone()
    return dict(row) if row else None


def execute_tool(name: str, args: dict) -> dict:
    """Execute a tool by name with given arguments. Returns result dict."""
    import logging
    log = logging.getLogger("siteline")

    try:
        if name == "search_property":
            return _tool_search(args.get("query", ""))

        elif name == "get_property_details":
            return _tool_property_details(args.get("property_id"))

        elif name == "analyze_biodiversity":
            return _tool_biodiversity(args.get("property_id"), args.get("footprint_sqm"))

        elif name == "analyze_netzero":
            return _tool_netzero(args.get("property_id"))

        elif name == "compare_properties":
            return _tool_compare(args.get("property_id"), args.get("radius_km", 1.0))

        elif name == "get_constraint_map":
            return _tool_constraint_map(args.get("property_id"))

        elif name == "get_loadshedding":
            return calculate_loadshedding_impact(args.get("property_id"))

        elif name == "get_crime_stats":
            return calculate_crime_risk(args.get("property_id"))

        elif name == "get_municipal_health":
            return calculate_municipal_health(args.get("property_id"))

        elif name == "get_development_potential":
            return _tool_development_potential(args.get("property_id"))

        elif name == "get_site_massing":
            return _tool_site_massing(args.get("property_id"))

        else:
            return {"error": f"Unknown tool: {name}"}
    except Exception as e:
        log.exception("Tool %s failed: %s", name, e)
        return {"error": f"Tool {name} failed: {str(e)}"}


def _parse_erf_query(query: str):
    """Parse common ERF query patterns and extract erf_number + optional suburb.

    Handles: "35268", "ERF 35268", "erf 35268 Table View",
             "35268 in Table View", "ERF 35268, CONSTANTIA",
             "erf number 35268", "ERF no. 35268 in Constantia", etc.
    """
    import re
    q = query.strip()

    # Strip common ERF prefixes: "ERF", "erf number", "erf no.", "erf no", "erf #"
    erf_match = re.match(
        r'^(?:erf\s*(?:number|no\.?|#)?\s+)?(\d+)\s*(?:[,\s]+(?:in\s+)?(.+))?$',
        q, re.IGNORECASE
    )
    if erf_match:
        erf_num = erf_match.group(1)
        suburb = erf_match.group(2).strip().rstrip('.') if erf_match.group(2) else None
        return erf_num, suburb

    # Fallback: find any number in the string and extract suburb context
    nums = re.findall(r'\b(\d{3,})\b', q)
    if nums:
        erf_num = nums[0]
        # Remove the number and common prefixes to get suburb
        remainder = re.sub(r'\b(?:erf|number|no\.?|#)\b', '', q, flags=re.IGNORECASE)
        remainder = re.sub(r'\b' + erf_num + r'\b', '', remainder)
        remainder = re.sub(r'\b(?:in|at|of|for)\b', '', remainder, flags=re.IGNORECASE)
        remainder = remainder.strip(' ,.-')
        suburb = remainder if remainder else None
        return erf_num, suburb

    return None, None


def _tool_search(query: str) -> dict:
    """Search properties by address or ERF number."""
    import logging
    log = logging.getLogger("siteline")
    engine = get_engine()

    # Parse ERF number and optional suburb from query
    erf_num, suburb_hint = _parse_erf_query(query)
    log.info("search_property query=%r → erf=%r, suburb=%r", query, erf_num, suburb_hint)

    with engine.connect() as conn:
        # Try ERF number + suburb if both provided
        if erf_num and suburb_hint:
            rows = conn.execute(text(f"""
                SELECT p.id, p.erf_number, p.suburb, p.full_address, p.area_sqm,
                       p.zoning_primary, p.centroid_lon, p.centroid_lat
                FROM {SCHEMA}.properties p
                WHERE p.erf_number = :erf AND p.suburb ILIKE :suburb
                ORDER BY p.suburb LIMIT 5
            """), {"erf": erf_num, "suburb": f"%{suburb_hint}%"}).mappings().fetchall()

            if rows:
                return {"results": [dict(r) for r in rows], "match_type": "erf_suburb", "count": len(rows)}

        # Try ERF number only (parsed or raw)
        erf_to_try = erf_num or query.strip()
        rows = conn.execute(text(f"""
            SELECT p.id, p.erf_number, p.suburb, p.full_address, p.area_sqm,
                   p.zoning_primary, p.centroid_lon, p.centroid_lat
            FROM {SCHEMA}.properties p
            WHERE p.erf_number = :q
            ORDER BY p.suburb LIMIT 5
        """), {"q": erf_to_try}).mappings().fetchall()

        if rows:
            return {"results": [dict(r) for r in rows], "match_type": "erf", "count": len(rows)}

        # Address search
        rows = conn.execute(text(f"""
            SELECT DISTINCT ON (p.id)
                   p.id, p.erf_number, p.suburb, p.full_address, p.area_sqm,
                   p.zoning_primary, p.centroid_lon, p.centroid_lat
            FROM {SCHEMA}.address_points ap
            JOIN {SCHEMA}.properties p ON ST_Within(ap.geom, p.geom)
            WHERE ap.full_address ILIKE :pattern
            ORDER BY p.id LIMIT 5
        """), {"pattern": f"%{query.strip()}%"}).mappings().fetchall()

        if rows:
            return {"results": [dict(r) for r in rows], "match_type": "address", "count": len(rows)}

        # Suburb fallback
        suburb_q = suburb_hint or query.strip()
        rows = conn.execute(text(f"""
            SELECT p.id, p.erf_number, p.suburb, p.full_address, p.area_sqm,
                   p.zoning_primary
            FROM {SCHEMA}.properties p
            WHERE p.suburb ILIKE :pattern
            ORDER BY p.suburb, p.erf_number LIMIT 5
        """), {"pattern": f"%{suburb_q}%"}).mappings().fetchall()

        return {"results": [dict(r) for r in rows], "match_type": "suburb", "count": len(rows)}


def _tool_property_details(property_id: int) -> dict:
    """Get full property details with biodiversity and heritage."""
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(text(f"""
            SELECT p.id, p.erf_number, p.suburb, p.full_address,
                   p.area_sqm, p.area_ha, p.zoning_primary,
                   p.centroid_lon, p.centroid_lat,
                   ST_AsGeoJSON(p.geom)::json AS geometry,
                   pue.inside_urban_edge
            FROM {SCHEMA}.properties p
            LEFT JOIN {SCHEMA}.property_urban_edge pue ON p.id = pue.property_id
            WHERE p.id = :id
        """), {"id": property_id}).mappings().fetchone()

        if not row:
            return {"error": "Property not found"}

        result = dict(row)

        bio_rows = conn.execute(text(f"""
            SELECT pb.cba_category, pb.habitat_condition, pb.overlap_pct
            FROM {SCHEMA}.property_biodiversity pb
            WHERE pb.property_id = :id
            ORDER BY CASE pb.cba_category
                WHEN 'PA' THEN 1 WHEN 'CA' THEN 2
                WHEN 'CBA 1a' THEN 3 WHEN 'CBA 1b' THEN 4 WHEN 'CBA 1c' THEN 5
                WHEN 'CBA 2' THEN 6 WHEN 'ESA 1' THEN 7 WHEN 'ESA 2' THEN 8
                WHEN 'ONA' THEN 9
            END
        """), {"id": property_id}).mappings().fetchall()
        result["biodiversity"] = [dict(r) for r in bio_rows]

        heritage = conn.execute(text(f"""
            SELECT hs.site_name, hs.source, hs.heritage_category,
                   hs.nhra_status, hs.city_grading
            FROM {SCHEMA}.heritage_sites hs
            WHERE ST_Intersects(hs.geom, (SELECT geom FROM {SCHEMA}.properties WHERE id = :id))
            LIMIT 5
        """), {"id": property_id}).mappings().fetchall()
        result["heritage"] = [dict(r) for r in heritage]

        # Valuation
        val_row = conn.execute(text(f"""
            SELECT market_value_zar, valuation_date, rating_category
            FROM {SCHEMA}.property_valuations
            WHERE property_id = :id
            LIMIT 1
        """), {"id": property_id}).mappings().fetchone()
        if val_row:
            result["valuation"] = dict(val_row)

        return result


def _tool_biodiversity(property_id: int, footprint_sqm: float = None) -> dict:
    """Run biodiversity offset calculation."""
    prop = _lookup_erf(property_id)
    if not prop:
        return {"error": "Property not found"}
    fp = footprint_sqm or (float(prop["area_sqm"]) * 0.4)
    return calculate_offset_requirement(prop["erf_number"], fp, suburb=prop["suburb"])


def _tool_netzero(property_id: int) -> dict:
    """Run net zero analysis (solar + water + scorecard)."""
    prop = _lookup_erf(property_id)
    if not prop:
        return {"error": "Property not found"}
    erf, suburb = prop["erf_number"], prop["suburb"]

    scorecard = netzero_scorecard(erf, suburb=suburb)
    solar = calculate_solar_potential(erf, suburb=suburb)
    water = calculate_water_harvesting(erf, suburb=suburb)

    return {
        "scorecard": scorecard if "error" not in scorecard else None,
        "solar": solar if "error" not in solar else None,
        "water": water if "error" not in water else None,
    }


def _tool_compare(property_id: int, radius_km: float = 1.0) -> dict:
    """Compare property valuations."""
    radius_result = compare_radius(property_id, radius_km)
    suburb_result = compare_suburb(property_id)
    return {
        "radius": radius_result if radius_result.get("error") != "Property not found" else None,
        "suburb": suburb_result if suburb_result.get("error") != "Property not found" else None,
    }


def _tool_development_potential(property_id: int) -> dict:
    """Calculate development potential with site plan GeoJSON."""
    result = calculate_development_potential(property_id)
    if "error" in result:
        return result
    # Also generate site plan GeoJSON for context panel map
    try:
        site_plan = generate_site_plan_geojson(property_id)
        if site_plan and "error" not in site_plan:
            result["site_plan_geojson"] = site_plan
    except Exception:
        pass
    return result


def _tool_site_massing(property_id: int) -> dict:
    """Generate building massing + unit layout."""
    massing = generate_massing_geojson(property_id)
    layout = generate_unit_layout(property_id)
    result = {}
    if massing and "error" not in massing:
        result["massing_geojson"] = massing
        result["building"] = massing.get("properties", {})
    if layout and "error" not in layout:
        result["unit_layout"] = {
            "building": layout.get("building"),
            "summary": layout.get("summary"),
            "parking": layout.get("parking"),
            "floors": [
                {
                    "floor": f["floor"],
                    "label": f["floor_label"],
                    "use": f["use"],
                    "unit_count": f["unit_count"],
                    "units": [{"type": u["type"], "label": u["label"], "bedrooms": u["bedrooms"], "size_sqm": u["size_sqm"]} for u in f["units"]],
                }
                for f in layout.get("floors", [])
            ],
        }
    return result if result else {"error": "Could not generate massing or layout"}


def _tool_constraint_map(property_id: int) -> dict:
    """Generate constraint map GeoJSON."""
    prop = _lookup_erf(property_id)
    if not prop:
        return {"error": "Property not found"}
    result = generate_constraint_map(prop["erf_number"], suburb=prop["suburb"])
    # Return summary for chat text + full GeoJSON for context panel map
    if "error" not in result and result.get("features"):
        summary = {
            "total_features": len(result["features"]),
            "feature_types": [f["properties"].get("layer_type") for f in result["features"] if f.get("properties")],
            "geojson": result,  # Full GeoJSON for context panel
        }
        for f in result["features"]:
            props = f.get("properties", {})
            if props.get("layer_type") == "developable_area":
                summary["developable_area_sqm"] = props.get("area_sqm")
                summary["developable_pct"] = props.get("developable_pct")
            elif props.get("layer_type") == "property_boundary":
                summary["property_area_sqm"] = props.get("area_sqm")
        return summary
    return result
