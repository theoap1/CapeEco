#!/usr/bin/env python3
"""
Download all required datasets from the Cape Town Open Data Portal.
Downloads GeoJSON files for spatial data and CSV for tabular data.
Also fetches feature service metadata for CRS and field info.
"""

import requests
import json
import os
import time

OUTPUT_DIR = "/Users/theoapteker/Documents/CapeEco/data/raw"

# Dataset definitions: name -> {geojson_url, shapefile_url, feature_service_url, type}
DATASETS = {
    # === CRITICAL BIODIVERSITY ===
    "cct_terrestrial_biodiversity_network_2025": {
        "geojson": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/4f2d7835518a4e6b8205ce12d77ff463/geojson?layers=9",
        "shapefile": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/4f2d7835518a4e6b8205ce12d77ff463/shapefile?layers=9",
        "feature_service": "https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_3/FeatureServer/9",
        "description": "Terrestrial Biodiversity Network (BioNet) - CBA classifications for Cape Town"
    },
    "cct_wetlands_2025": {
        "geojson": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/f72e3c3f6179490f9e87575b9833eee5/geojson?layers=15",
        "shapefile": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/f72e3c3f6179490f9e87575b9833eee5/shapefile?layers=15",
        "feature_service": "https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_3/FeatureServer/15",
        "description": "Wetlands - aquatic biodiversity network features"
    },
    "cct_indigenous_vegetation_current_2025": {
        "geojson": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/766a627d9597420d92be65365b333ff7/geojson?layers=11",
        "shapefile": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/766a627d9597420d92be65365b333ff7/shapefile?layers=11",
        "feature_service": "https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_3/FeatureServer/11",
        "description": "Indigenous Vegetation - Current Extent"
    },
    "cct_sanbi_ecosystem_status_2011": {
        "geojson": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/0eff7ab5c5484e7aaa1eea5d797762f0/geojson?layers=13",
        "shapefile": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/0eff7ab5c5484e7aaa1eea5d797762f0/shapefile?layers=13",
        "feature_service": "https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_3/FeatureServer/13",
        "description": "SANBI Vegetation Ecosystem Threat Status 2011"
    },

    # === ZONING ===
    "cct_zoning_2025": {
        "geojson": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/8dddb4894a2f4f1a8c394f8295361e9e/geojson?layers=0",
        "shapefile": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/8dddb4894a2f4f1a8c394f8295361e9e/shapefile?layers=0",
        "feature_service": "https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_5/FeatureServer/0",
        "description": "City Zoning - current zoning scheme boundaries"
    },
    "cct_split_zoning_2025": {
        "geojson": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/dce26baeb9f245f6b0690b214b61f149/geojson?layers=1",
        "shapefile": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/dce26baeb9f245f6b0690b214b61f149/shapefile?layers=1",
        "feature_service": "https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_4/FeatureServer/1",
        "description": "Split Zoning - properties with multiple zoning classifications"
    },

    # === URBAN EDGE ===
    "cct_urban_development_edge_2025": {
        "geojson": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/8a60b001a2cc4691a9de8e10c9d29467/geojson?layers=12",
        "shapefile": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/8a60b001a2cc4691a9de8e10c9d29467/shapefile?layers=12",
        "feature_service": "https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_11/FeatureServer/12",
        "description": "Urban Development Edge boundary"
    },
    "cct_coastal_urban_edge_2025": {
        "geojson": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/7fcaefb2d2ab401882e13d51b32b1365/geojson?layers=10",
        "shapefile": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/7fcaefb2d2ab401882e13d51b32b1365/shapefile?layers=10",
        "feature_service": "https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_3/FeatureServer/10",
        "description": "Coastal Urban Edge boundary"
    },

    # === CADASTRAL / LAND PARCELS ===
    "cct_land_parcels_2025": {
        "geojson": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/2194bbc8f65b4dc6938ee7a5871c82b3/geojson?layers=0",
        "shapefile": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/2194bbc8f65b4dc6938ee7a5871c82b3/shapefile?layers=0",
        "feature_service": "https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_4/FeatureServer/0",
        "description": "Land Parcels - cadastral/erf boundaries"
    },

    # === SOLAR ===
    "cct_smartfacility_solar_2025": {
        "geojson": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/a5e7b9702a974f23aa6d3698b32c0ea0/geojson?layers=13",
        "shapefile": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/a5e7b9702a974f23aa6d3698b32c0ea0/shapefile?layers=13",
        "feature_service": "https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_10/FeatureServer/13",
        "description": "SmartFacility Solar installations"
    },

    # === ADDRESS POINTS ===
    "cct_street_address_numbers_2025": {
        "geojson": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/c2101858187f424298f85e60f9706533/geojson?layers=1",
        "shapefile": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/c2101858187f424298f85e60f9706533/shapefile?layers=1",
        "feature_service": "https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_6/FeatureServer/1",
        "description": "Street Address Numbers - geocoding reference points"
    },

    # === HERITAGE ===
    "cct_heritage_inventory_2025": {
        "geojson": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/3865065100214518b7466495da7e9a28/geojson?layers=2",
        "shapefile": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/3865065100214518b7466495da7e9a28/shapefile?layers=2",
        "feature_service": "https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_3/FeatureServer/2",
        "description": "Heritage Inventory - protected structures"
    },
    "cct_nhra_protection_2025": {
        "geojson": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/762b9d72e2db4c5a826f9483b6eca9e1/geojson?layers=0",
        "shapefile": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/762b9d72e2db4c5a826f9483b6eca9e1/shapefile?layers=0",
        "feature_service": "https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_3/FeatureServer/0",
        "description": "National Heritage Resources Act formal protections"
    },

    # === ENVIRONMENTAL ===
    "cct_environmental_focus_areas_2025": {
        "geojson": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/eccc5785df894de3868dfba82fbf7013/geojson?layers=18",
        "shapefile": "https://odp-cctegis.opendata.arcgis.com/api/download/v1/items/eccc5785df894de3868dfba82fbf7013/shapefile?layers=18",
        "feature_service": "https://esapqa.capetown.gov.za/agsext/rest/services/Theme_Based/ODP_SPLIT_11/FeatureServer/18",
        "description": "Environmental Focus Areas"
    },
}

# Tabular datasets (CSV only)
TABULAR_DATASETS = {
    "cct_rainfall_from_2000": {
        "url": "https://odp-cctegis.opendata.arcgis.com/datasets/cctegis::rainfall-data-from-2000",
        "description": "Daily rainfall time series from 2000 onwards (CSV)"
    },
    "cct_solar_exports_2014_2023": {
        "url": "https://odp-cctegis.opendata.arcgis.com/datasets/cctegis::customer-solar-energy-exports-2014-to-2023",
        "description": "Customer solar energy exports 2014-2023 (CSV)"
    },
}


def get_feature_service_metadata(url):
    """Fetch metadata from ArcGIS Feature Service endpoint."""
    try:
        resp = requests.get(f"{url}?f=json", timeout=30)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"    Warning: Could not fetch metadata: {e}")
    return None


def download_geojson(name, config):
    """Download GeoJSON file for a dataset."""
    filepath = os.path.join(OUTPUT_DIR, f"{name}.geojson")

    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        if size > 100:  # Skip if already downloaded and not empty
            print(f"  [SKIP] {name}.geojson already exists ({size:,} bytes)")
            return filepath, size

    print(f"  [DOWNLOADING] {name}.geojson ...")
    try:
        resp = requests.get(config["geojson"], timeout=300, stream=True)
        if resp.status_code == 200:
            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            size = os.path.getsize(filepath)
            print(f"  [OK] {size:,} bytes")
            return filepath, size
        else:
            print(f"  [ERROR] HTTP {resp.status_code}")
            return None, 0
    except Exception as e:
        print(f"  [ERROR] {e}")
        return None, 0


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    catalog = {}

    print("=" * 80)
    print("CAPE TOWN ECO-PROPERTY: DATA DOWNLOAD")
    print("=" * 80)

    for name, config in DATASETS.items():
        print(f"\n--- {config['description']} ---")

        # Get feature service metadata (CRS, fields)
        meta = get_feature_service_metadata(config["feature_service"])

        crs = "Unknown"
        fields = []
        if meta:
            # Extract spatial reference
            sr = meta.get("extent", {}).get("spatialReference", {})
            wkid = sr.get("latestWkid", sr.get("wkid", "Unknown"))
            crs = f"EPSG:{wkid}"

            # Extract fields
            for field in meta.get("fields", []):
                fields.append({
                    "name": field.get("name"),
                    "alias": field.get("alias"),
                    "type": field.get("type"),
                })

            # Save metadata
            meta_path = os.path.join(OUTPUT_DIR, f"{name}_metadata.json")
            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=2)

        # Download GeoJSON
        filepath, size = download_geojson(name, config)

        catalog[name] = {
            "description": config["description"],
            "crs": crs,
            "geojson_file": f"{name}.geojson" if filepath else None,
            "geojson_size_bytes": size,
            "feature_service_url": config["feature_service"],
            "shapefile_url": config["shapefile"],
            "field_count": len(fields),
            "fields": fields,
        }

        time.sleep(1)  # Be polite to the server

    # Note tabular datasets
    print("\n\n--- TABULAR DATASETS (require manual download or API access) ---")
    for name, config in TABULAR_DATASETS.items():
        print(f"  {name}: {config['description']}")
        print(f"    URL: {config['url']}")
        catalog[name] = {
            "description": config["description"],
            "type": "tabular",
            "portal_url": config["url"],
            "note": "CSV - download from portal or access via API"
        }

    # Save catalog
    catalog_path = os.path.join(OUTPUT_DIR, "dataset_catalog.json")
    with open(catalog_path, "w") as f:
        json.dump(catalog, f, indent=2)

    print(f"\n\nCatalog saved to {catalog_path}")
    print(f"\nSUMMARY:")
    print(f"  Spatial datasets: {len(DATASETS)}")
    print(f"  Tabular datasets: {len(TABULAR_DATASETS)}")

    total_size = sum(v.get("geojson_size_bytes", 0) for v in catalog.values())
    print(f"  Total download size: {total_size:,} bytes ({total_size/1024/1024:.1f} MB)")


if __name__ == "__main__":
    main()
