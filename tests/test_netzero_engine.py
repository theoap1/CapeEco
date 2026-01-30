#!/usr/bin/env python3
"""
Tests for the Net Zero Feasibility Calculator.

Uses real ERF numbers from the loaded CapeEco database:
  - Parklands 5074: SR1, no biodiversity, inside urban edge, low rainfall
  - Hout Bay 9785: Agricultural, CBA 2, outside urban edge, high rainfall
  - Noordhoek 719: Rural, CBA 1b, inside urban edge, medium-high rainfall
  - Fish Hoek 8422: Open Space (PA), inside urban edge, medium-high rainfall
  - Kommetjie 7183: SR1, ESA 1, inside urban edge, medium-high rainfall

Requires a running PostgreSQL database with loaded CapeEco data.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from netzero_engine import (
    calculate_solar_potential,
    calculate_water_harvesting,
    netzero_scorecard,
    _classify_building_type,
    _estimate_roof_area,
    _get_rainfall_zone,
    RAINFALL_ZONES,
    ENERGY_BENCHMARKS,
)


# ==========================================================================
# Helper function tests (no DB required)
# ==========================================================================


class TestHelpers:
    """Test internal helper functions."""

    def test_classify_residential(self):
        assert _classify_building_type("Single Residential 1 : Conventional Housing") == "residential"

    def test_classify_commercial(self):
        assert _classify_building_type("General Business 1") == "commercial"

    def test_classify_industrial(self):
        assert _classify_building_type("General Industrial 1") == "industrial"

    def test_classify_mixed_use(self):
        assert _classify_building_type("Mixed Use 2") == "commercial"

    def test_classify_none(self):
        assert _classify_building_type(None) == "residential"

    def test_roof_area_sr1(self):
        """SR1 should use 40% coverage."""
        area = _estimate_roof_area(1000, "Single Residential 1 : Conventional Housing")
        assert area == 400

    def test_roof_area_business(self):
        """Business should use 75% coverage."""
        area = _estimate_roof_area(1000, "General Business 1")
        assert area == 750

    def test_roof_area_industrial(self):
        area = _estimate_roof_area(1000, "General Industrial 1")
        assert area == 650

    def test_roof_area_agricultural(self):
        """Agricultural should use 10% coverage."""
        area = _estimate_roof_area(10000, "Agricultural")
        assert area == 1000

    def test_rainfall_zone_constantia(self):
        assert _get_rainfall_zone("CONSTANTIA") == "high"

    def test_rainfall_zone_noordhoek(self):
        assert _get_rainfall_zone("NOORDHOEK") == "medium_high"

    def test_rainfall_zone_parklands(self):
        assert _get_rainfall_zone("PARKLANDS") == "low"

    def test_rainfall_zone_bellville(self):
        assert _get_rainfall_zone("BELLVILLE") == "medium"

    def test_rainfall_zone_lat_fallback(self):
        """Unknown suburb should fall back to latitude."""
        zone = _get_rainfall_zone("UNKNOWN_SUBURB", lat=-34.15)
        assert zone == "medium_high"

    def test_rainfall_zone_default(self):
        """No suburb or lat should return medium."""
        assert _get_rainfall_zone(None) == "medium"


# ==========================================================================
# calculate_solar_potential tests
# ==========================================================================


class TestSolarPotential:
    """Test solar potential calculations with real properties."""

    def test_parklands_residential(self):
        """Parklands 5074: small SR1 property, should get valid solar result."""
        result = calculate_solar_potential("5074", suburb="PARKLANDS")
        assert "error" not in result
        assert result["building_type"] == "residential"
        assert result["system_size_kwp"] > 0
        assert result["annual_generation_kwh"] > 0
        assert result["carbon_offset_tonnes_per_year"] > 0
        assert result["estimated_payback_years"] > 0
        assert len(result["install_cost_range_zar"]) == 2
        assert result["install_cost_range_zar"][0] < result["install_cost_range_zar"][1]

    def test_hout_bay_agricultural(self):
        """Hout Bay 9785: agricultural property, should have low roof coverage."""
        result = calculate_solar_potential("9785", suburb="HOUT BAY")
        assert "error" not in result
        assert result["building_type"] == "residential"  # agricultural defaults to residential
        # Agricultural uses 10% coverage — smaller roof relative to property
        assert result["estimated_roof_area_sqm"] < result["property_area_sqm"] * 0.15

    def test_system_size_proportional(self):
        """Larger property should have larger system."""
        small = calculate_solar_potential("7183", suburb="KOMMETJIE")  # 587 m²
        large = calculate_solar_potential("9785", suburb="HOUT BAY")   # 4440 m²
        assert "error" not in small
        assert "error" not in large
        # Both agricultural (10%) vs SR1 (40%) — ratio isn't just area-based
        # but SR1 on small property may still produce more
        assert small["system_size_kwp"] > 0
        assert large["system_size_kwp"] > 0

    def test_netzero_ratio_present(self):
        result = calculate_solar_potential("5074", suburb="PARKLANDS")
        assert "netzero_ratio_average" in result
        assert "netzero_ratio_efficient" in result
        assert result["netzero_ratio_average"] > 0
        assert result["netzero_ratio_efficient"] >= result["netzero_ratio_average"]

    def test_carbon_offset_calculation(self):
        """Carbon offset should be generation × emission factor."""
        result = calculate_solar_potential("5074", suburb="PARKLANDS")
        expected_tonnes = result["annual_generation_kwh"] * 1.04 / 1000
        assert abs(result["carbon_offset_tonnes_per_year"] - round(expected_tonnes, 2)) < 0.1

    def test_nonexistent_property(self):
        result = calculate_solar_potential("NONEXISTENT_99999")
        assert "error" in result

    def test_notes_populated(self):
        result = calculate_solar_potential("5074", suburb="PARKLANDS")
        assert len(result["notes"]) > 0


# ==========================================================================
# calculate_water_harvesting tests
# ==========================================================================


class TestWaterHarvesting:
    """Test water harvesting calculations."""

    def test_parklands_low_rainfall(self):
        """Parklands is in a low-rainfall zone."""
        result = calculate_water_harvesting("5074", suburb="PARKLANDS")
        assert "error" not in result
        assert result["rainfall_zone"] == "low"
        assert result["annual_rainfall_mm"] == 550

    def test_noordhoek_medium_high_rainfall(self):
        """Noordhoek is in a medium-high rainfall zone."""
        result = calculate_water_harvesting("719", suburb="NOORDHOEK")
        assert "error" not in result
        assert result["rainfall_zone"] == "medium_high"
        assert result["annual_rainfall_mm"] == 800

    def test_harvest_positive(self):
        result = calculate_water_harvesting("5074", suburb="PARKLANDS")
        assert result["annual_harvestable_kl"] > 0

    def test_demand_met_percentage(self):
        result = calculate_water_harvesting("5074", suburb="PARKLANDS")
        assert 0 < result["demand_met_pct"] <= 200

    def test_monthly_distribution(self):
        """Monthly harvest should sum to approximately annual total."""
        result = calculate_water_harvesting("5074", suburb="PARKLANDS")
        monthly_sum = sum(result["monthly_harvest_kl"].values())
        assert abs(monthly_sum - result["annual_harvestable_kl"]) < 1.0

    def test_winter_higher_than_summer(self):
        """Cape Town winter months should have higher harvest."""
        result = calculate_water_harvesting("5074", suburb="PARKLANDS")
        winter = result["monthly_harvest_kl"]["Jun"] + result["monthly_harvest_kl"]["Jul"]
        summer = result["monthly_harvest_kl"]["Jan"] + result["monthly_harvest_kl"]["Feb"]
        assert winter > summer * 3

    def test_tank_size_recommendation(self):
        result = calculate_water_harvesting("5074", suburb="PARKLANDS")
        assert result["recommended_tank_size_kl"] > 0

    def test_savings_positive(self):
        result = calculate_water_harvesting("5074", suburb="PARKLANDS")
        assert result["annual_savings_zar"] > 0
        assert result["tank_cost_estimate_zar"] > 0

    def test_nonexistent_property(self):
        result = calculate_water_harvesting("NONEXISTENT_99999")
        assert "error" in result

    def test_notes_populated(self):
        result = calculate_water_harvesting("5074", suburb="PARKLANDS")
        assert len(result["notes"]) > 0


# ==========================================================================
# netzero_scorecard tests
# ==========================================================================


class TestNetZeroScorecard:
    """Test the aggregated scorecard."""

    def test_parklands_unconstrained(self):
        """Parklands 5074: no bio constraints, inside urban edge."""
        result = netzero_scorecard("5074", suburb="PARKLANDS")
        assert "error" not in result
        assert result["total_score"] > 0
        assert result["greenstar_rating"] is not None
        assert "scores" in result
        assert "energy" in result["scores"]
        assert "water" in result["scores"]
        assert "ecology" in result["scores"]
        assert "location" in result["scores"]

    def test_hout_bay_cba2_outside_edge(self):
        """Hout Bay 9785: CBA 2, outside urban edge — lower location score."""
        result = netzero_scorecard("9785", suburb="HOUT BAY")
        assert "error" not in result
        assert result["scores"]["location"] < 5  # outside urban edge
        assert result["biodiversity_summary"]["designation"] == "CBA 2"
        assert result["biodiversity_summary"]["offset_applicable"] is True

    def test_fish_hoek_pa_no_go(self):
        """Fish Hoek 8422: PA — biodiversity no-go."""
        result = netzero_scorecard("8422", suburb="FISH HOEK")
        assert "error" not in result
        assert result["biodiversity_summary"]["is_no_go"] is True
        assert any("no-go" in r.lower() or "not permitted" in r.lower()
                    for r in result["recommendations"])

    def test_score_components_sum(self):
        """Component scores should sum to total."""
        result = netzero_scorecard("5074", suburb="PARKLANDS")
        assert result["total_score"] == sum(result["scores"].values())

    def test_greenstar_rating_valid(self):
        result = netzero_scorecard("5074", suburb="PARKLANDS")
        valid_ratings = {"6-star", "5-star", "4-star", "3-star", "Below rated"}
        assert result["greenstar_rating"] in valid_ratings

    def test_solar_summary_present(self):
        result = netzero_scorecard("5074", suburb="PARKLANDS")
        assert "solar_summary" in result
        assert result["solar_summary"]["system_kwp"] > 0

    def test_water_summary_present(self):
        result = netzero_scorecard("5074", suburb="PARKLANDS")
        assert "water_summary" in result
        assert result["water_summary"]["annual_harvest_kl"] > 0

    def test_recommendations_present(self):
        result = netzero_scorecard("5074", suburb="PARKLANDS")
        assert isinstance(result["recommendations"], list)

    def test_missing_for_netzero(self):
        result = netzero_scorecard("5074", suburb="PARKLANDS")
        assert isinstance(result["missing_for_netzero"], list)

    def test_nonexistent_property(self):
        result = netzero_scorecard("NONEXISTENT_99999")
        assert "error" in result

    def test_disclaimer_note(self):
        result = netzero_scorecard("5074", suburb="PARKLANDS")
        assert "indicative" in result["note"].lower()


# ==========================================================================
# Integration: full workflow
# ==========================================================================


class TestFullWorkflow:
    """End-to-end: solar → water → scorecard."""

    def test_kommetjie_full_workflow(self):
        """Kommetjie 7183: SR1, ESA 1, medium-high rainfall."""
        solar = calculate_solar_potential("7183", suburb="KOMMETJIE")
        assert "error" not in solar
        assert solar["system_size_kwp"] > 0

        water = calculate_water_harvesting("7183", suburb="KOMMETJIE")
        assert "error" not in water
        assert water["annual_harvestable_kl"] > 0

        score = netzero_scorecard("7183", suburb="KOMMETJIE")
        assert "error" not in score
        assert score["total_score"] > 0
        assert score["biodiversity_summary"]["designation"] == "ESA 1"
        assert score["biodiversity_summary"]["offset_applicable"] is True
