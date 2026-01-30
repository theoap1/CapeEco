#!/usr/bin/env python3
"""
Discover and catalog all required datasets from the Cape Town Open Data Portal.
Uses the ArcGIS Hub Search API to find datasets and their feature service endpoints.
"""

import requests
import json
import os

BASE_URL = "https://odp-cctegis.opendata.arcgis.com"
OUTPUT_DIR = "/Users/theoapteker/Documents/CapeEco/data/raw"

# Search terms to find our required datasets
SEARCHES = [
    "Terrestrial Biodiversity Network",
    "biodiversity",
    "zoning",
    "urban edge",
    "cadastral",
    "conservation land",
    "rainfall",
    "solar",
    "address point",
    "heritage",
    "valuation",
    "wetlands",
    "vegetation",
    "property",
    "erf",
]

def search_hub(query, num=20):
    """Search the ArcGIS Hub for datasets."""
    url = f"{BASE_URL}/api/feed/dcat-us/1.1.json"
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"DCAT feed error: {e}")

    # Try alternative: ArcGIS Hub v3 search
    url2 = f"https://hub.arcgis.com/api/v3/datasets?filter[source]=City%20of%20Cape%20Town&page[size]={num}&q={query}"
    try:
        resp = requests.get(url2, timeout=30)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Hub v3 error: {e}")

    return None

def get_dcat_catalog():
    """Get the full DCAT catalog from the portal."""
    url = f"{BASE_URL}/api/feed/dcat-us/1.1.json"
    print(f"Fetching DCAT catalog from {url}...")
    try:
        resp = requests.get(url, timeout=60)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            return data
    except Exception as e:
        print(f"Error: {e}")
    return None

def main():
    # Try DCAT catalog first - this lists ALL datasets
    catalog = get_dcat_catalog()

    if catalog and "dataset" in catalog:
        datasets = catalog["dataset"]
        print(f"\nFound {len(datasets)} datasets in DCAT catalog\n")

        # Save full catalog
        with open(os.path.join(OUTPUT_DIR, "cct_dcat_catalog.json"), "w") as f:
            json.dump(catalog, f, indent=2)

        # Search for our required datasets
        keywords = {
            "bionet": [],
            "biodiversity": [],
            "terrestrial": [],
            "zoning": [],
            "urban edge": [],
            "cadastral": [],
            "erf": [],
            "conservation": [],
            "rainfall": [],
            "solar": [],
            "address": [],
            "heritage": [],
            "valuation": [],
            "wetland": [],
            "vegetation": [],
            "property": [],
        }

        for ds in datasets:
            title = ds.get("title", "").lower()
            desc = ds.get("description", "").lower()
            combined = title + " " + desc

            for kw in keywords:
                if kw in combined:
                    keywords[kw].append({
                        "title": ds.get("title"),
                        "description": ds.get("description", "")[:200],
                        "distribution": [
                            {"url": d.get("downloadURL", d.get("accessURL", "")),
                             "format": d.get("mediaType", "")}
                            for d in ds.get("distribution", [])
                        ],
                        "modified": ds.get("modified", ""),
                        "keyword": ds.get("keyword", []),
                    })

        print("=" * 80)
        print("DATASET DISCOVERY RESULTS")
        print("=" * 80)

        for kw, matches in keywords.items():
            if matches:
                print(f"\n--- '{kw}' ({len(matches)} matches) ---")
                for m in matches:
                    print(f"  Title: {m['title']}")
                    print(f"  Modified: {m['modified']}")
                    for d in m['distribution']:
                        if d['url']:
                            print(f"    -> {d['format']}: {d['url'][:120]}")
                    print()

        # Save discovery results
        with open(os.path.join(OUTPUT_DIR, "dataset_discovery.json"), "w") as f:
            json.dump(keywords, f, indent=2)

        print(f"\nResults saved to {OUTPUT_DIR}/dataset_discovery.json")
    else:
        print("DCAT catalog not available or empty, trying alternative approaches...")

        # Try searching individually
        for query in SEARCHES[:5]:
            print(f"\nSearching for: {query}")
            result = search_hub(query)
            if result:
                print(json.dumps(result, indent=2)[:500])

if __name__ == "__main__":
    main()
