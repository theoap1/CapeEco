#!/usr/bin/env python3
"""
GV2022 Valuation Roll Scraper — fetches municipal property valuations from
the City of Cape Town's GV2022 Provision Roll website and caches them in the
capeeco.property_valuations table.

Public data source: https://web1.capetown.gov.za/web1/gv2022/
"""

import logging
import os
import re
import time
from contextlib import contextmanager
from html.parser import HTMLParser

import requests
from sqlalchemy import create_engine, text

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GV2022_URL = "https://web1.capetown.gov.za/web1/gv2022/Results"
SCHEMA = "capeeco"
REQUEST_DELAY = 1.0  # seconds between requests (be respectful)

_last_request_time = 0.0


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


# ---------------------------------------------------------------------------
# HTML table parser for GV2022 results
# ---------------------------------------------------------------------------
class GV2022Parser(HTMLParser):
    """Extracts rows from the GV2022 results HTML table."""

    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.in_header = False
        self.current_row = []
        self.current_cell = ""
        self.rows = []
        self.headers = []
        self._table_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._table_depth += 1
            if self._table_depth == 1:
                self.in_table = True
        elif self.in_table:
            if tag == "tr":
                self.in_row = True
                self.current_row = []
            elif tag in ("td", "th"):
                self.in_cell = True
                self.in_header = tag == "th"
                self.current_cell = ""

    def handle_endtag(self, tag):
        if tag == "table":
            self._table_depth -= 1
            if self._table_depth == 0:
                self.in_table = False
        elif self.in_table:
            if tag == "tr" and self.in_row:
                self.in_row = False
                if self.current_row:
                    self.rows.append(self.current_row)
            elif tag in ("td", "th") and self.in_cell:
                self.in_cell = False
                text = self.current_cell.strip()
                self.current_row.append(text)

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell += data


def _parse_market_value(val_str: str) -> float | None:
    """Parse 'R 1450000.00' or 'R1,450,000' into float."""
    if not val_str:
        return None
    cleaned = re.sub(r"[R\s,]", "", val_str)
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _parse_extent(val_str: str) -> float | None:
    """Parse '497.0000' into float."""
    if not val_str:
        return None
    try:
        return float(val_str)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Scraping functions
# ---------------------------------------------------------------------------
def scrape_erf_valuations(erf_number: str) -> list[dict]:
    """
    Scrape GV2022 for all properties matching an ERF number.
    Returns list of dicts with keys: property_reference, suburb, rating_category,
    address, extent_sqm, market_value_zar.
    """
    global _last_request_time

    # Rate limit
    elapsed = time.time() - _last_request_time
    if elapsed < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - elapsed)

    # Strip any non-numeric suffixes for the search (GV2022 searches on numeric ERF)
    erf_clean = erf_number.split("-")[0].strip()

    try:
        resp = requests.get(
            GV2022_URL,
            params={"Search": f"ERF,{erf_clean}"},
            timeout=15,
            headers={"User-Agent": "CapeEco/1.0 (property research tool)"},
        )
        _last_request_time = time.time()
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning("GV2022 request failed for ERF %s: %s", erf_number, e)
        return []

    parser = GV2022Parser()
    parser.feed(resp.text)

    results = []
    # Find the data rows — skip header rows (those with "Property Reference" etc.)
    for row in parser.rows:
        if len(row) < 6:
            continue
        # Header row detection
        if "Property Reference" in row[0] or "Registered" in row[1]:
            continue
        # Row number only (page separator)
        if len(row) == 1:
            continue

        # Columns: PropertyRef, RegisteredDescription, RatingCategory, Address, Extent, MarketValue, ...
        prop_ref = row[0].strip() if len(row) > 0 else ""
        description = row[1].strip() if len(row) > 1 else ""
        rating_cat = row[2].strip() if len(row) > 2 else ""
        address = row[3].strip() if len(row) > 3 else ""
        extent_str = row[4].strip() if len(row) > 4 else ""
        market_str = row[5].strip() if len(row) > 5 else ""

        market_value = _parse_market_value(market_str)
        extent_sqm = _parse_extent(extent_str)

        # Extract suburb from description (format: "901 GORDONS BAY")
        # The description is "{erf_number} {SUBURB}"
        suburb = ""
        if description:
            parts = description.split(None, 1)
            if len(parts) > 1:
                suburb = parts[1].strip()

        if prop_ref and market_value is not None:
            results.append({
                "property_reference": prop_ref,
                "suburb": suburb,
                "rating_category": rating_cat,
                "address": address,
                "extent_sqm": extent_sqm,
                "market_value_zar": market_value,
            })

    return results


def fetch_and_cache_valuations(property_ids: list[int]) -> dict[int, float]:
    """
    For a list of property IDs, check cache first, then scrape GV2022 for
    uncached properties. Returns {property_id: market_value_zar}.
    """
    if not property_ids:
        return {}

    with _connection() as conn:
        # Check existing cache
        cached = conn.execute(text(f"""
            SELECT property_id, market_value_zar
            FROM {SCHEMA}.property_valuations
            WHERE property_id = ANY(:ids)
        """), {"ids": property_ids}).mappings().fetchall()

        result = {r["property_id"]: float(r["market_value_zar"]) for r in cached if r["market_value_zar"]}
        uncached_ids = [pid for pid in property_ids if pid not in result]

        if not uncached_ids:
            return result

        # Get ERF numbers and suburbs for uncached properties
        props = conn.execute(text(f"""
            SELECT id, erf_number, suburb, area_sqm
            FROM {SCHEMA}.properties
            WHERE id = ANY(:ids)
        """), {"ids": uncached_ids}).mappings().fetchall()

        # Group by ERF number to minimise scrape requests
        erf_groups: dict[str, list[dict]] = {}
        for p in props:
            erf = p["erf_number"]
            if erf not in erf_groups:
                erf_groups[erf] = []
            erf_groups[erf].append(dict(p))

        # Scrape each unique ERF number
        for erf_number, db_props in erf_groups.items():
            scraped = scrape_erf_valuations(erf_number)
            if not scraped:
                continue

            # Match scraped results to DB properties by suburb
            for db_prop in db_props:
                db_suburb = (db_prop["suburb"] or "").upper().strip()
                best_match = None
                for s in scraped:
                    s_suburb = (s["suburb"] or "").upper().strip()
                    if s_suburb == db_suburb:
                        best_match = s
                        break
                    # Partial match fallback
                    if db_suburb and s_suburb and (db_suburb in s_suburb or s_suburb in db_suburb):
                        best_match = s

                if best_match:
                    val = best_match["market_value_zar"]
                    result[db_prop["id"]] = val
                    # Cache it
                    try:
                        conn.execute(text(f"""
                            INSERT INTO {SCHEMA}.property_valuations
                                (property_id, property_reference, market_value_zar, rating_category)
                            VALUES (:pid, :pref, :val, :cat)
                            ON CONFLICT (property_id) DO UPDATE
                                SET market_value_zar = EXCLUDED.market_value_zar,
                                    property_reference = EXCLUDED.property_reference,
                                    rating_category = EXCLUDED.rating_category,
                                    fetched_at = NOW()
                        """), {
                            "pid": db_prop["id"],
                            "pref": best_match["property_reference"],
                            "val": val,
                            "cat": best_match["rating_category"],
                        })
                    except Exception as e:
                        log.warning("Failed to cache valuation for property %s: %s", db_prop["id"], e)

        conn.commit()

    return result


def get_cached_valuation(property_id: int) -> float | None:
    """Return cached market value for a property, or None."""
    with _connection() as conn:
        row = conn.execute(text(f"""
            SELECT market_value_zar FROM {SCHEMA}.property_valuations WHERE property_id = :pid
        """), {"pid": property_id}).mappings().fetchone()
    return float(row["market_value_zar"]) if row and row["market_value_zar"] else None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 2:
        print("Usage: python valuation_scraper.py <erf_number>")
        sys.exit(1)
    erf = sys.argv[1]
    results = scrape_erf_valuations(erf)
    for r in results:
        print(f"  {r['suburb']:30s}  R {r['market_value_zar']:>15,.2f}  {r['extent_sqm'] or 0:>10.1f} m²  {r['address']}")
    print(f"\n{len(results)} results")
