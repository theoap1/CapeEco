# CapeEco — Cape Town Eco-Property Intelligence

## Project Overview

Web-based geospatial platform that takes any Cape Town address and returns biodiversity risk assessments, zoning analysis, net zero feasibility scores, and offset marketplace data. Built entirely on free open government data from the City of Cape Town Open Data Portal.

## Tech Stack

- **Database**: PostgreSQL 17 + PostGIS 3.6.1 (running on localhost:5432)
- **Python**: 3.x with geopandas, shapely, sqlalchemy, geoalchemy2, ijson, psycopg2
- **API**: FastAPI + Uvicorn (localhost:8000)
- **Frontend**: React + Vite + Tailwind CSS v4 + React-Leaflet + Lucide icons
- **Map tiles**: Free providers only (OpenStreetMap, Esri World Imagery, OpenTopoMap — no API keys)
- **Data format**: GeoJSON (always EPSG:4326 per spec — do NOT assume EPSG:3857)
- **DB schema**: All tables in `capeeco` schema, geometries stored as EPSG:4326

## Database

- **Connection**: `postgresql://capeeco_user:capeeco_pass@localhost:5432/capeeco`
- **Schema**: `capeeco` (set via `SET search_path TO capeeco, public`)
- **Key tables**:
  - `properties` — 834,959 land parcels. `erf_number` is TEXT (formats: "10-RE", "102-0-1") and NOT unique across suburbs. Use `erf_number + suburb` for lookups.
  - `biodiversity_areas` — 23,473 BioNet polygons with `cba_category` enum (PA, CA, CBA 1a/1b/1c, CBA 2, ESA 1/2, ONA)
  - `ecosystem_types` — 4,553 vegetation type polygons with `threat_status` enum (CR, EN, VU, LT)
  - `urban_edges` — 53 polygons (development + coastal edges)
  - `heritage_sites` — 98,648 sites (inventory + NHRA)
  - `address_points` — 853,521 geocoding points
- **Derived tables** (computed via spatial joins):
  - `property_biodiversity` — 63,232 property × biodiversity intersections
  - `property_ecosystems` — 29,732 property × ecosystem intersections
  - `property_urban_edge` — 834,959 inside/outside classifications
- **Staging tables**: `staging_*` variants exist for safe data loading

## Project Structure

```
scripts/
  data_loader.py      — ETL pipeline (--step setup|load|index|intersect|all)
  biodiversity_engine.py — Biodiversity calculation engine (3 functions + CLI)
  netzero_engine.py     — Net Zero feasibility calculator (3 functions + CLI)
  schema.sql          — Full PostGIS schema definition
  download_datasets.py — Downloads 14 GeoJSON datasets from CCT portal
  discover_datasets.py — Dataset discovery utility
data/
  raw/                — 14 GeoJSON files + metadata (~2.1GB)
  processed/
    offset_rules.json — Biodiversity offset ratios, multipliers, cost rules
api/
  main.py             — FastAPI backend serving PostGIS data + analysis endpoints
frontend/
  src/
    components/
      AddressSearchBar.jsx — Autocomplete search (address + ERF number)
      InteractiveMap.jsx   — Leaflet map with CBA overlays, property click, constraint map
      PropertySidebar.jsx  — Property details + analysis results + Green Star scorecard
      LayerControl.jsx     — Toggle overlay layers + legend
    hooks/
      useDarkMode.js       — Dark mode with localStorage persistence
    utils/
      api.js               — Axios API client
      constants.js         — CBA colors, threat status, Green Star thresholds
      ReportView.jsx       — Full Development Potential Report with PDF export
tests/
  test_biodiversity_engine.py — 38 tests using real ERF numbers (requires running DB)
  test_netzero_engine.py      — 44 tests for net zero calculator (requires running DB)
docs/
  data_dictionary.md
```

## Key Scripts

### biodiversity_engine.py

Three core functions:

1. **`calculate_offset_requirement(erf_number, footprint_sqm, suburb=None)`** — Returns offset ratio, required hectares, cost estimate, no-go flags
2. **`generate_constraint_map(erf_number, suburb=None)`** — Returns GeoJSON FeatureCollection with property boundary, CBA overlays, buffer zones, developable area
3. **`find_matching_conservation_land_bank(required_ha, ecosystem_type)`** — Finds candidate offset parcels in Open Space-zoned PA/CA/CBA 1 areas

Offset formula: `offset_ha = footprint_ha × base_ratio × condition_multiplier × urban_edge_adjustment`

CBA severity ordering: PA > CA > CBA 1a > CBA 1b > CBA 1c > CBA 2 > ESA 1 > ESA 2 > ONA

### netzero_engine.py

Three core functions:

1. **`calculate_solar_potential(erf_number, suburb=None)`** — Estimates rooftop PV system size, annual generation, net zero energy ratio, carbon offset, payback period
2. **`calculate_water_harvesting(erf_number, suburb=None)`** — Calculates rainwater harvest potential using suburb-based rainfall zones, monthly distribution, tank sizing
3. **`netzero_scorecard(erf_number, suburb=None, proposed_gfa_sqm=None)`** — Aggregates solar, water, biodiversity into GBCSA Green Star SA equivalent rating (3-star to 6-star)

Key data sources:
- Solar irradiance: Cape Town avg 5.5 PSH/day, validated against CCT Smart Facility real-world generation data
- Rainfall: 4 zones (550-1100 mm/yr) mapped from ~60 suburbs, with latitude fallback
- Energy benchmarks: SANS 10400-XA (40-200 kWh/m²/yr by building type)
- Water demand: SANS 10252-1 (200 L/person/day residential)
- Roof area: estimated from property area × zoning coverage ratio (10-75%)

### data_loader.py

Streams large GeoJSON files via `ijson` in chunks. Uses staging tables then promotes to production. Key patterns:
- `write_to_postgis()` wrapper renames geometry column from `geometry` → `geom` to match DB schema
- Integer columns need `pd.to_numeric().astype("Int64")` cast (ijson returns Decimals)
- Schema applied via `psql -f` subprocess (not Python semicolon splitting)
- Urban edge anti-join uses LEFT JOIN (not NOT IN) for performance

## Important Gotchas

- **ERF numbers are not unique** — always pair with suburb for property lookups
- **GeoJSON is always EPSG:4326** — never reproject from 3857, the CCT portal exports as 4326
- **CBA key format mismatch** — DB stores `"CBA 1a"`, offset_rules.json keys use `"CBA_1a"` (underscore)
- **base_ratio=0 vs None** — explicit 0 (ONA) means no offset; None means fall back to ecosystem ratio
- **geometry column naming** — PostGIS tables use `geom`, GeoDataFrame defaults to `geometry`

## API Endpoints (FastAPI — port 8000)

- `GET /api/search?q=...` — Address/ERF autocomplete
- `GET /api/property/{id}` — Property detail + GeoJSON geometry
- `GET /api/property/{id}/biodiversity` — Biodiversity offset calculation
- `GET /api/property/{id}/netzero` — Net zero scorecard
- `GET /api/property/{id}/solar` — Solar potential
- `GET /api/property/{id}/water` — Water harvesting
- `GET /api/property/{id}/constraint-map` — GeoJSON constraint map
- `GET /api/layers/biodiversity?bbox=...` — CBA overlay for map viewport
- `GET /api/layers/properties?bbox=...` — Property boundaries (high zoom only)
- `GET /api/layers/ecosystem-types?bbox=...` — Ecosystem type polygons
- `GET /api/layers/heritage?bbox=...` — Heritage sites
- `GET /api/property/{id}/report` — Full Development Potential Report (aggregates all data)

## Running

```bash
# Backend API (from project root)
uvicorn api.main:app --host 127.0.0.1 --port 8000

# Frontend dev server (from frontend/)
cd frontend && npm run dev    # → http://localhost:5173

# Tests
pytest tests/ -v              # all 82 tests
```

Requires PostgreSQL 17 running with loaded CapeEco data.

## Public API (v1) — Authenticated Endpoints

All v1 endpoints require `Authorization: Bearer <api_key>` header.

Default dev key: `demo-key-capeeco-2026` (free tier, 100 req/day).

Set custom keys via `CAPEECO_API_KEYS` env var: `"key1:free,key2:paid"`.

### Endpoints

- `POST /api/v1/analyze` — Unified property analysis (accepts `erf_number` or `address`)
  - Request: `{"erf_number": "901", "suburb": "BANTRY BAY", "proposed_footprint_sqm": 200, "proposed_building_type": "residential"}`
  - Returns: biodiversity, zoning, netzero, offset requirements, constraint map, report URL
  - Errors: 404 (property not found), 422 (outside CCT boundary or missing identifier), 401/403 (auth), 429 (rate limit)

- `GET /api/v1/conservation-land-bank?ecosystem_type=...&min_hectares=...&max_distance_km=...&origin_property_id=...`
  - Returns candidate offset parcels with area, cost estimates, distance

- `GET /api/v1/bionet/layers?west=...&south=...&east=...&north=...`
  - Returns CBA overlay GeoJSON (authenticated version of `/api/layers/biodiversity`)

- `POST /api/v1/reports/generate` — Same body as `/analyze`, returns full report data + download URL

- `GET /api/v1/health` — Health check (no auth)

### Rate Limiting

- Free tier: 100 requests/day
- Paid tier: 10,000 requests/day
- In-memory sliding window (resets on server restart)

### AI Integration

- `POST /api/ai/analyze` — DeepSeek-powered contextual analysis for report sections
- Sections: executive_summary, biodiversity, heritage, netzero, solar, water, actions
- Key: `DEEPSEEK_API_KEY` env var (fallback hardcoded for dev)
- Max 300 tokens, temperature 0.3, 15s timeout, graceful fallback

## Development Phases

- **Phase 1** (complete): Data acquisition + offset rules
- **Phase 2** (complete): Database setup, data loading, biodiversity engine, net zero calculator
- **Phase 3** (complete): FastAPI backend + React/Leaflet frontend + Development Potential Report (PDF export via html2canvas/jsPDF)
- **Phase 4** (complete): Public API v1 (Bearer auth, rate limiting, unified `/analyze`, conservation land bank, AI insights)
- **Phase 5** (complete): Docker containerization (PostGIS, FastAPI, React/nginx multi-stage builds, docker-compose)

## Docker Deployment

```bash
# Copy and configure environment
cp .env.example .env
# Edit .env with your DEEPSEEK_API_KEY and any custom API keys

# Build and start all services
docker compose up --build -d

# Services:
#   db  — PostGIS 17 on :5432 (schema auto-applied from scripts/schema.sql)
#   api — FastAPI on :8000
#   web — nginx serving React SPA on :80, proxying /api/ to backend
```

Key files: `Dockerfile` (backend), `frontend/Dockerfile` (multi-stage build), `docker-compose.yml`, `frontend/nginx.conf`, `.env.example`

## Database Migration & Seeding

### Alembic Migrations
```bash
# Apply all migrations
python3 -m alembic upgrade head

# Rollback last migration
python3 -m alembic downgrade -1

# Create new migration
python3 -m alembic revision -m "description"
```

Config: `alembic.ini` (local dev URL) or set `DATABASE_URL` env var for production.

### Seed Data
```bash
python3 scripts/seed_data.py
```
Idempotent script that ensures PostGIS extensions, schema, and sample properties exist. Safe to run repeatedly.

### DB Export/Import
```bash
# Export local DB to compressed backup
./scripts/db_migrate.sh export

# Import to cloud DB
DATABASE_URL=postgresql://user:pass@host/db ./scripts/db_migrate.sh import backups/capeeco_20260130.sql.gz
```

### Connection Pooling
SQLAlchemy engine configured with: `pool_size=5`, `max_overflow=10`, `pool_pre_ping=True`, `pool_recycle=3600`. Supports `DATABASE_URL` env var for Docker/cloud deployments.

### Health Check
`GET /api/v1/health` verifies: DB connectivity, PostGIS extension active, minimum 1 property record loaded. Returns `"status": "ok"` or `"degraded"`.

## Production Deployment (Railway)

**Architecture:** Single service — FastAPI serves both API (`/api/*`) and the built React SPA (catch-all route). PostGIS database as a separate Railway service.

### Railway Setup
1. Create project on [railway.app](https://railway.app)
2. Add PostgreSQL plugin (supports PostGIS)
3. Connect GitHub repo — auto-deploys on push to `main`
4. Set environment variables: `DATABASE_URL`, `DEEPSEEK_API_KEY`, `CAPEECO_API_KEYS`, `ENVIRONMENT=production`, `CORS_ORIGINS`
5. Health check configured via `railway.toml`

### CI/CD
GitHub Actions (`.github/workflows/deploy.yml`):
- **test**: Spins up PostGIS container, applies schema, runs pytest
- **build-frontend**: Verifies React build succeeds
- **deploy**: Pushes to Railway on merge to `main` (requires `RAILWAY_TOKEN` secret)

### Security
- HSTS headers in production (`ENVIRONMENT=production`)
- `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`
- CORS restricted via `CORS_ORIGINS` env var
- SSL termination handled by Railway

### Key Files
| File | Purpose |
|------|---------|
| `railway.toml` | Railway deploy config with health check |
| `Procfile` | Process command for Railway |
| `.github/workflows/deploy.yml` | CI/CD pipeline |
| `.gitignore` | Excludes data/raw, .env, node_modules |
