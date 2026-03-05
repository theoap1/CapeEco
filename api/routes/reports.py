"""Report generation endpoint."""

import json
import sys
from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text

from api.db import get_engine, SCHEMA
from api.auth import get_current_user

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from biodiversity_engine import calculate_offset_requirement
from netzero_engine import calculate_solar_potential, calculate_water_harvesting, netzero_scorecard

router = APIRouter(prefix="/api", tags=["reports"])

RULES_PATH = Path(__file__).parent.parent.parent / "data" / "processed" / "offset_rules.json"


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


@router.get("/property/{property_id}/report")
def get_property_report(property_id: int, _user: dict = Depends(get_current_user)):
    """Generate comprehensive Development Potential Report data."""
    rules = _load_rules()
    report_date = date.today()
    engine = get_engine()

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
        "report_id": f"SL-{property_id}-{report_date.strftime('%Y%m%d')}",
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
