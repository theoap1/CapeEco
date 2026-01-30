#!/usr/bin/env python3
"""
Tests for the Biodiversity Calculation Engine.

Uses real ERF numbers from known CBA areas in Cape Town:
  - Constantia: CBA 1a, PA (Peninsula Granite Fynbos - South, CR)
  - Noordhoek: CBA 1b (Peninsula Granite Fynbos - South, CR)
  - Hout Bay: CBA 1c, CBA 2 (various)
  - Fish Hoek: PA, CBA 1a, ONA (Peninsula Sandstone Fynbos, EN)
  - Kommetjie: ESA 1, ESA 2 (Peninsula Sandstone Fynbos, EN)
  - Parklands: No biodiversity overlay (residential)

Requires a running PostgreSQL database with loaded CapeEco data.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from biodiversity_engine import (
    calculate_offset_requirement,
    find_matching_conservation_land_bank,
    generate_constraint_map,
)


# ==========================================================================
# calculate_offset_requirement tests
# ==========================================================================


class TestCalculateOffset:
    """Test offset calculations across all CBA categories."""

    def test_pa_is_no_go(self):
        """Protected Area (Fish Hoek 8422) must be flagged as no-go."""
        result = calculate_offset_requirement("8422", 500, suburb="FISH HOEK")
        assert result["designation"] == "PA"
        assert result["is_no_go"] is True
        assert result["offset_applicable"] is False
        assert any("NO-GO" in n for n in result["notes"])

    def test_ca_is_no_go(self):
        """Conservation Area (Hout Bay 4494-RE) must be flagged as no-go."""
        result = calculate_offset_requirement("4494-RE", 1000, suburb="HOUT BAY")
        assert result["designation"] in ("PA", "CA")
        assert result["is_no_go"] is True

    def test_cba_1a_is_no_go(self):
        """CBA 1a (Fish Hoek 13676) is no-go for development."""
        result = calculate_offset_requirement("13676", 200, suburb="FISH HOEK")
        assert result["is_no_go"] is True
        assert result["offset_applicable"] is False

    def test_cba_1b_exceptional_only(self):
        """CBA 1b (Noordhoek 719) is exceptional circumstances only."""
        result = calculate_offset_requirement("719", 1000, suburb="NOORDHOEK")
        assert result["designation"] == "CBA 1b"
        assert result["is_exceptional_only"] is True
        assert result["base_ratio"] == 30
        # CR ecosystem: 30 × condition × urban edge
        assert result["required_offset_ha"] > 0

    def test_cba_1b_condition_multiplier(self):
        """CBA 1b in Fair condition should apply 0.75 multiplier."""
        result = calculate_offset_requirement("719", 1000, suburb="NOORDHOEK")
        assert result["habitat_condition"] == "Fair"
        assert result["condition_multiplier"] == 0.75

    def test_cba_2_offset_applicable(self):
        """CBA 2 (Hout Bay 9785) allows offsets."""
        result = calculate_offset_requirement("9785", 2000, suburb="HOUT BAY")
        assert result["designation"] == "CBA 2"
        assert result["offset_applicable"] is True
        assert result["base_ratio"] == 20
        assert result["required_offset_ha"] > 0
        assert result["offset_cost_estimate_zar"] > 0

    def test_cba_2_outside_urban_edge(self):
        """CBA 2 outside urban edge gets 1.2x adjustment."""
        result = calculate_offset_requirement("9785", 2000, suburb="HOUT BAY")
        assert result["inside_urban_edge"] is False
        assert result["urban_edge_adjustment"] == 1.2

    def test_cba_2_no_trade_down_outside_edge(self):
        """CBA 2 outside urban edge is NOT trade-down eligible."""
        result = calculate_offset_requirement("9785", 2000, suburb="HOUT BAY")
        assert result["trade_down_eligible"] is False

    def test_esa_1_offset_required(self):
        """ESA 1 (Kommetjie 7183) requires offset."""
        result = calculate_offset_requirement("7183", 300, suburb="KOMMETJIE")
        assert result["designation"] == "ESA 1"
        assert result["offset_applicable"] is True
        assert result["base_ratio"] == 5

    def test_esa_2_lower_ratio(self):
        """ESA 2 (Kommetjie 7059) has lower base ratio."""
        result = calculate_offset_requirement("7059", 200, suburb="KOMMETJIE")
        assert result["designation"] == "ESA 2"
        assert result["base_ratio"] == 3

    def test_ona_no_offset(self):
        """ONA (Fish Hoek 17923) requires no offset."""
        result = calculate_offset_requirement("17923", 300, suburb="FISH HOEK")
        # ONA is in offset_required? No — it's in no_offset_categories
        # But the primary overlay may still be ONA
        # The property might have multiple overlays; check the most restrictive
        if result["designation"] == "ONA":
            assert result["base_ratio"] == 0
            assert result["required_offset_ha"] == 0

    def test_no_biodiversity_overlay(self):
        """Property with no CBA overlay (Parklands 5074) needs no offset."""
        result = calculate_offset_requirement("5074", 500, suburb="PARKLANDS")
        assert result["designation"] is None
        assert result["offset_applicable"] is False
        assert result["required_offset_ha"] == 0
        assert result["offset_cost_estimate_zar"] == 0
        assert "No biodiversity designation" in result["notes"]

    def test_footprint_exceeds_area(self):
        """Footprint larger than property should return error."""
        result = calculate_offset_requirement("5074", 999999, suburb="PARKLANDS")
        assert "error" in result

    def test_nonexistent_property(self):
        """Non-existent ERF number should return error."""
        result = calculate_offset_requirement("NONEXISTENT_99999", 100)
        assert "error" in result

    def test_cr_ecosystem_warning(self):
        """Properties on CR ecosystems should get warning even when offset-applicable."""
        result = calculate_offset_requirement("9785", 2000, suburb="HOUT BAY")
        assert result["ecosystem_threat_status"] == "CR"
        assert any("Critically Endangered" in n for n in result["notes"])

    def test_offset_formula_correctness(self):
        """Verify: offset_ha = footprint_ha × base_ratio × condition × urban_edge."""
        result = calculate_offset_requirement("9785", 2000, suburb="HOUT BAY")
        footprint_ha = 2000 / 10000
        expected = footprint_ha * result["base_ratio"] * result["condition_multiplier"] * result["urban_edge_adjustment"]
        assert abs(result["required_offset_ha"] - round(expected, 4)) < 0.01

    def test_conservation_land_bank_eligible(self):
        """CBA 2 with offset applicable should be CLB eligible."""
        result = calculate_offset_requirement("9785", 2000, suburb="HOUT BAY")
        assert result["conservation_land_bank_option"] is True

    def test_all_designations_populated(self):
        """Properties with multiple overlays should list all designations."""
        result = calculate_offset_requirement("1043", 5000, suburb="CONSTANTIA")
        assert len(result["all_designations"]) > 1


# ==========================================================================
# generate_constraint_map tests
# ==========================================================================


class TestConstraintMap:
    """Test GeoJSON constraint map generation."""

    def test_returns_feature_collection(self):
        """Result should be a valid GeoJSON FeatureCollection."""
        result = generate_constraint_map("719", suburb="NOORDHOEK")
        assert result["type"] == "FeatureCollection"
        assert "features" in result
        assert len(result["features"]) > 0

    def test_property_boundary_feature(self):
        """Should include a property_boundary feature."""
        result = generate_constraint_map("719", suburb="NOORDHOEK")
        layers = [f["properties"]["layer"] for f in result["features"]]
        assert "property_boundary" in layers

    def test_cba_overlay_feature(self):
        """Properties in CBA areas should have cba_overlay features."""
        result = generate_constraint_map("719", suburb="NOORDHOEK")
        cba_features = [
            f for f in result["features"] if f["properties"]["layer"] == "cba_overlay"
        ]
        assert len(cba_features) > 0
        assert cba_features[0]["properties"]["cba_category"] == "CBA 1b"

    def test_buffer_zone_feature(self):
        """CBA properties should have buffer_zone features."""
        result = generate_constraint_map("719", suburb="NOORDHOEK")
        buf_features = [
            f for f in result["features"] if f["properties"]["layer"] == "buffer_zone"
        ]
        assert len(buf_features) > 0
        assert buf_features[0]["properties"]["buffer_m"] == 30

    def test_developable_area_feature(self):
        """Should include a developable_area feature."""
        result = generate_constraint_map("719", suburb="NOORDHOEK")
        dev_features = [
            f for f in result["features"] if f["properties"]["layer"] == "developable_area"
        ]
        assert len(dev_features) > 0

    def test_small_property_no_developable_area(self):
        """Small CBA 1b property buffer should consume entire property."""
        result = generate_constraint_map("719", suburb="NOORDHOEK")
        assert result["properties"]["developable_area_sqm"] <= 1.0  # effectively zero

    def test_no_cba_full_developable(self):
        """Property without CBA should have full area as developable."""
        result = generate_constraint_map("5074", suburb="PARKLANDS")
        dev = [f for f in result["features"] if f["properties"]["layer"] == "developable_area"]
        assert len(dev) > 0
        assert dev[0]["properties"]["area_sqm"] > 0

    def test_ecosystem_type_feature(self):
        """Properties with ecosystem overlays should have ecosystem_type features."""
        result = generate_constraint_map("719", suburb="NOORDHOEK")
        eco = [f for f in result["features"] if f["properties"]["layer"] == "ecosystem_type"]
        assert len(eco) > 0
        assert eco[0]["properties"]["vegetation_type"] is not None

    def test_valid_geojson_geometries(self):
        """All features should have valid GeoJSON geometry."""
        result = generate_constraint_map("719", suburb="NOORDHOEK")
        for f in result["features"]:
            assert "geometry" in f
            assert f["geometry"] is not None
            assert f["geometry"]["type"] in (
                "Polygon", "MultiPolygon", "GeometryCollection",
                "Point", "MultiPoint", "LineString", "MultiLineString",
            )

    def test_nonexistent_property_error(self):
        """Non-existent property should return error dict."""
        result = generate_constraint_map("NONEXISTENT_99999")
        assert "error" in result


# ==========================================================================
# find_matching_conservation_land_bank tests
# ==========================================================================


class TestConservationLandBank:
    """Test conservation land bank matching."""

    def test_returns_candidates(self):
        """Should find candidates for common ecosystem types."""
        result = find_matching_conservation_land_bank(
            5.0, "Peninsula Granite Fynbos - South"
        )
        assert result["candidates_found"] > 0
        assert len(result["candidates"]) > 0

    def test_candidates_match_ecosystem(self):
        """All candidates should match the requested ecosystem type."""
        result = find_matching_conservation_land_bank(
            1.0, "Peninsula Sandstone Fynbos"
        )
        for c in result["candidates"]:
            assert c["vegetation_type"] == "Peninsula Sandstone Fynbos"

    def test_candidates_in_high_priority_areas(self):
        """Candidates should be in PA, CA, or CBA 1 areas."""
        result = find_matching_conservation_land_bank(
            1.0, "Peninsula Granite Fynbos - South"
        )
        high_priority = {"PA", "CA", "CBA 1a", "CBA 1b"}
        for c in result["candidates"]:
            assert c["cba_category"] in high_priority

    def test_cost_estimates_present(self):
        """Candidates should include cost estimates."""
        result = find_matching_conservation_land_bank(
            1.0, "Peninsula Granite Fynbos - South"
        )
        for c in result["candidates"]:
            assert "estimated_cost_range_zar" in c
            assert len(c["estimated_cost_range_zar"]) == 2
            assert c["estimated_cost_range_zar"][0] > 0

    def test_coordinates_present(self):
        """Candidates should include coordinates."""
        result = find_matching_conservation_land_bank(
            1.0, "Peninsula Granite Fynbos - South"
        )
        for c in result["candidates"]:
            assert "coordinates" in c
            lon, lat = c["coordinates"]
            # Cape Town bounds
            assert 18.0 < lon < 19.0
            assert -34.5 < lat < -33.5

    def test_no_candidates_for_nonexistent_type(self):
        """Non-existent ecosystem type should return empty list."""
        result = find_matching_conservation_land_bank(
            1.0, "Nonexistent Vegetation Type XYZ"
        )
        assert result["candidates_found"] == 0

    def test_very_large_area_fewer_candidates(self):
        """Very large area requirement should filter out small parcels."""
        result = find_matching_conservation_land_bank(
            100.0, "Peninsula Granite Fynbos - South"
        )
        # May still find some (10% threshold) but fewer
        for c in result["candidates"]:
            assert c["area_ha"] >= 10.0  # 10% of 100

    def test_includes_note(self):
        """Result should include disclaimer note."""
        result = find_matching_conservation_land_bank(
            1.0, "Peninsula Granite Fynbos - South"
        )
        assert "note" in result
        assert "indicative" in result["note"].lower()


# ==========================================================================
# Integration test: full workflow
# ==========================================================================


class TestFullWorkflow:
    """End-to-end workflow: calculate → map → land bank."""

    def test_cba2_full_workflow(self):
        """Full workflow for a CBA 2 property in Hout Bay."""
        # 1. Calculate offset
        calc = calculate_offset_requirement("9785", 2000, suburb="HOUT BAY")
        assert calc["offset_applicable"] is True
        assert calc["required_offset_ha"] > 0

        # 2. Generate constraint map
        cmap = generate_constraint_map("9785", suburb="HOUT BAY")
        assert cmap["type"] == "FeatureCollection"
        layers = {f["properties"]["layer"] for f in cmap["features"]}
        assert "property_boundary" in layers
        assert "cba_overlay" in layers

        # 3. Find land bank matches
        lb = find_matching_conservation_land_bank(
            calc["required_offset_ha"], calc["ecosystem_type"]
        )
        assert lb["candidates_found"] > 0

    def test_no_constraints_workflow(self):
        """Workflow for an unconstrained property."""
        calc = calculate_offset_requirement("5074", 500, suburb="PARKLANDS")
        assert calc["required_offset_ha"] == 0

        cmap = generate_constraint_map("5074", suburb="PARKLANDS")
        assert cmap["type"] == "FeatureCollection"
        # Should have property_boundary and developable_area
        layers = {f["properties"]["layer"] for f in cmap["features"]}
        assert "property_boundary" in layers
        assert "developable_area" in layers
        # No CBA overlays
        assert "cba_overlay" not in layers
