# Siteline — Property Development Intelligence

## Project Overview

AI-powered property development intelligence platform for South African developers. Aggregates fragmented development data — zoning, biodiversity, load shedding, crime, municipal finance, valuations — into one workspace. Features a full-screen AI chat workspace where developers can query property data conversationally.

## Tech Stack

- **Database**: PostgreSQL 17 + PostGIS 3.6.1
- **Python**: 3.x with geopandas, shapely, sqlalchemy, geoalchemy2, ijson, psycopg2
- **API**: FastAPI + Uvicorn (localhost:8000), modular route architecture
- **AI**: DeepSeek Chat API with function calling (tool-augmented agent loop)
- **Frontend**: React 19 + Vite + Tailwind CSS v4 + React-Leaflet + Lucide icons
- **Map tiles**: Free providers only (OpenStreetMap, Esri World Imagery, OpenTopoMap)
- **Data format**: GeoJSON (always EPSG:4326 — do NOT assume EPSG:3857)
- **DB schema**: `siteline` (configurable via `SITELINE_SCHEMA` env var, falls back to `capeeco` for legacy DBs)
- **Auth**: JWT tokens stored as `siteline_token` in localStorage

## Database

- **Schema**: `siteline` (set via `SITELINE_SCHEMA` env var)
- **Key tables**:
  - `properties` — 834,959 land parcels. `erf_number` is TEXT and NOT unique across suburbs. Use `erf_number + suburb`.
  - `biodiversity_areas` — 23,473 BioNet polygons with `cba_category` enum
  - `ecosystem_types` — 4,553 vegetation type polygons with `threat_status` enum
  - `urban_edges` — 53 polygons (development + coastal edges)
  - `heritage_sites` — 98,648 sites (inventory + NHRA)
  - `address_points` — 853,521 geocoding points
  - `users` — JWT authenticated users
  - `property_valuations` — GV2022 municipal valuations
- **Derived tables**: `property_biodiversity`, `property_ecosystems`, `property_urban_edge`
- **Optional tables** (data loaders not yet run): `police_stations`, `crime_stats`, `loadshedding_blocks`, `municipalities`, `municipal_finance`

## Project Structure

```
api/
  main.py              — App factory, middleware, lifespan, auth endpoints, static SPA serving (~190 lines)
  db.py                — Shared engine, connection pooling, schema constant
  auth.py              — JWT auth (hash_password, verify_password, create_access_token, get_current_user)
  tools.py             — AI tool definitions + execution (9 tools for DeepSeek function calling)
  routes/
    search.py          — GET /api/search
    properties.py      — GET /api/property/{id}, /biodiversity, /netzero, /solar, /water, /constraint-map, /development-potential, /site-plan, /massing, /unit-layout
    comparison.py      — GET /api/property/{id}/compare/radius, /compare/suburb, /construction-cost
    layers.py          — GET /api/layers/biodiversity, /properties, /ecosystem-types, /heritage
    reports.py         — GET /api/property/{id}/report
    ai.py              — POST /api/ai/analyze (section-based DeepSeek insights)
    chat.py            — POST /api/ai/chat (SSE streaming chat with tool loop)
    v1.py              — /api/v1/* public API endpoints
    newdata.py         — GET /api/property/{id}/loadshedding, /crime, /municipal
scripts/
  biodiversity_engine.py — Biodiversity offset calculator (3 functions + CLI)
  netzero_engine.py      — Net zero feasibility calculator (solar, water, scorecard)
  site_plan_engine.py    — Development potential, massing, unit layout (CTZS zoning rules, yield calc, financials)
  comparison_engine.py   — Property valuation comparison engine
  loadshedding_engine.py — Load shedding impact assessment
  crime_engine.py        — Crime risk scoring (SAPS data, 29 categories)
  municipal_engine.py    — Municipal finance health scoring (National Treasury data)
  valuation_scraper.py   — GV2022 municipal valuation scraper
  data_loader.py         — ETL pipeline (--step setup|load|index|intersect|all)
  schema.sql             — Full PostGIS schema definition
frontend/
  src/
    App.jsx              — AppShell with TopBar + TabBar + React Router
    pages/
      LoginPage.jsx      — Auth page (Siteline branding)
      MapView.jsx        — Map + sidebar + layer control
      AIWorkspace.jsx    — Full-screen AI chat + context panel
      ReportsView.jsx    — Report history (placeholder)
      DashboardView.jsx  — Overview metrics (placeholder)
    components/
      AddressSearchBar.jsx — Autocomplete search
      InteractiveMap.jsx   — Leaflet map with overlays
      PropertySidebar.jsx  — Property details + analysis
      LayerControl.jsx     — Toggle overlay layers + legend
      ReportView.jsx       — Development Potential Report with PDF export
      ai/
        ChatMessage.jsx    — User/assistant message rendering + tool indicators
        ContextPanel.jsx   — Right panel (property, analysis, map tabs)
        SuggestedPrompts.jsx — Quick-start prompt cards
    contexts/
      AuthContext.jsx      — JWT auth state management
    hooks/
      useDarkMode.js       — Dark mode with localStorage persistence (key: siteline-dark)
    utils/
      api.js               — Axios client + SSE streaming chat + all endpoints
      constants.js         — Colors, thresholds, enums
```

## AI Chat Architecture

The AI workspace uses a tool-augmented agent loop:

1. User sends message → `POST /api/ai/chat` (SSE stream)
2. Backend sends conversation to DeepSeek with 11 tool definitions
3. If DeepSeek calls a tool → execute against DB/engines → stream `tool_call` + `tool_result` events → feed result back to DeepSeek
4. Loop up to 5 iterations until DeepSeek returns final text
5. Frontend renders streaming text + tool call indicators + context panel updates

**Available AI tools**: `search_property`, `get_property_details`, `analyze_biodiversity`, `analyze_netzero`, `compare_properties`, `get_constraint_map`, `get_loadshedding`, `get_crime_stats`, `get_municipal_health`, `get_development_potential`, `get_site_massing`

**SSE event types**: `text`, `tool_call`, `tool_result`, `context`, `done`

## Key Engines

### biodiversity_engine.py
- `calculate_offset_requirement(erf_number, footprint_sqm, suburb=None)` — offset ratio, cost, no-go flags
- `generate_constraint_map(erf_number, suburb=None)` — GeoJSON FeatureCollection
- `find_matching_conservation_land_bank(required_ha, ecosystem_type)` — candidate offset parcels
- CBA severity: PA > CA > CBA 1a > CBA 1b > CBA 1c > CBA 2 > ESA 1 > ESA 2 > ONA

### netzero_engine.py
- `calculate_solar_potential(erf_number, suburb=None)` — PV sizing, generation, payback
- `calculate_water_harvesting(erf_number, suburb=None)` — rainwater potential, tank sizing
- `netzero_scorecard(erf_number, suburb=None)` — Green Star SA rating (3-6 star)

### loadshedding_engine.py
- `calculate_loadshedding_impact(property_id)` — block assignment, stage 1-8 impacts, risk level, backup recommendations
- Falls back to estimates when `loadshedding_blocks` table doesn't exist

### crime_engine.py
- `calculate_crime_risk(property_id)` — risk score, 29-category breakdown, security recommendations
- 10-point severity weighting (Murder=10, Crimen injuria=2)
- Falls back to suburb-based estimates when `police_stations` table doesn't exist

### site_plan_engine.py
- `calculate_development_potential(property_id)` — full yield analysis: zoning rules, buildable envelope, GFA, unit mix breakdown, parking (resident + visitor, surface vs basement), financial feasibility (construction cost, revenue, profit, margin/ROI), density metrics (units/ha, beds/ha)
- `generate_site_plan_geojson(property_id)` — GeoJSON: property boundary, buildable envelope, setback zone, biodiversity constraints
- `generate_massing_geojson(property_id)` — GeoJSON: building footprint, per-floor plates with use type, parking zone
- `generate_unit_layout(property_id)` — floor-by-floor unit packing: unit positions, corridor/core placement, parking grid
- 34 CTZS zone codes with Table A parameters (setbacks, coverage, FAR, height, floors, parking ratio)
- Unit mix templates for 7 development types (single res → high-density → commercial → mixed use)
- Financial model: construction costs, professional fees, contingency, market value per unit type

### municipal_engine.py
- `calculate_municipal_health(property_id)` — 6-metric financial health score, trends
- Pre-computed Cape Town data from National Treasury (2020/21–2022/23)

## Important Gotchas

- **ERF numbers are not unique** — always pair with suburb for property lookups
- **GeoJSON is always EPSG:4326** — never reproject from 3857
- **CBA key format mismatch** — DB stores `"CBA 1a"`, offset_rules.json uses `"CBA_1a"` (underscore)
- **base_ratio=0 vs None** — explicit 0 (ONA) means no offset; None means fall back to ecosystem ratio
- **geometry column naming** — PostGIS tables use `geom`, GeoDataFrame defaults to `geometry`
- **Schema fallback** — New engines try `siteline` schema first, fall back to `capeeco` for legacy DBs
- **Token key** — Frontend stores JWT as `siteline_token` in localStorage

## API Endpoints

### Core
- `GET /api/search?q=...` — Address/ERF autocomplete
- `GET /api/property/{id}` — Property detail + GeoJSON geometry
- `GET /api/property/{id}/biodiversity` — Biodiversity offset calculation
- `GET /api/property/{id}/netzero` — Net zero scorecard
- `GET /api/property/{id}/solar` — Solar potential
- `GET /api/property/{id}/water` — Water harvesting
- `GET /api/property/{id}/constraint-map` — GeoJSON constraint map
- `GET /api/property/{id}/development-potential` — Full yield analysis (unit mix, financials, parking, density)
- `GET /api/property/{id}/site-plan` — GeoJSON site plan (boundary, envelope, setbacks, bio)
- `GET /api/property/{id}/massing` — GeoJSON building massing (floor plates, parking zone)
- `GET /api/property/{id}/unit-layout` — Floor-by-floor unit packing layout
- `GET /api/property/{id}/report` — Full Development Potential Report

### New Data Sources
- `GET /api/property/{id}/loadshedding` — Load shedding impact assessment
- `GET /api/property/{id}/crime` — Crime risk score + breakdown
- `GET /api/property/{id}/municipal` — Municipal financial health

### Map Layers
- `GET /api/layers/biodiversity?bbox=...` — CBA overlay
- `GET /api/layers/properties?bbox=...` — Property boundaries (high zoom)
- `GET /api/layers/ecosystem-types?bbox=...` — Ecosystem polygons
- `GET /api/layers/heritage?bbox=...` — Heritage sites

### AI
- `POST /api/ai/analyze` — Section-based DeepSeek insights for reports
- `POST /api/ai/chat` — SSE streaming chat with tool-augmented agent loop

### Public API (v1)
- `POST /api/v1/analyze` — Unified property analysis
- `GET /api/v1/conservation-land-bank` — Offset parcel search
- `GET /api/v1/bionet/layers` — Authenticated CBA overlay
- `POST /api/v1/reports/generate` — Report generation
- `GET /api/v1/health` — Health check (no auth)

Default dev key: `demo-key-siteline-2026` (free tier, 100 req/day).
Set custom keys via `SITELINE_API_KEYS` env var.

## Running

```bash
# Backend API (from project root)
uvicorn api.main:app --host 127.0.0.1 --port 8000

# Frontend dev server (from frontend/)
cd frontend && npm run dev    # → http://localhost:5173

# Tests
pytest tests/ -v
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Built from PG* vars |
| `SITELINE_SCHEMA` | Database schema name | `siteline` |
| `DEEPSEEK_API_KEY` | DeepSeek API key for AI | — |
| `SITELINE_API_KEYS` | API keys (key:tier pairs) | `demo-key-siteline-2026:free` |
| `JWT_SECRET` | JWT signing secret | `siteline-dev-secret-change-in-prod` |
| `ENVIRONMENT` | `production` enables HSTS | — |
| `CORS_ORIGINS` | Comma-separated allowed origins | `*` |

## Deployment (Railway)

**Architecture:** Single service — FastAPI serves both API (`/api/*`) and built React SPA (catch-all route). PostGIS database as separate Railway service.

- GitHub repo auto-deploys on push to `main`
- Dockerfile: multi-stage (Node frontend build → Python backend + built assets)
- Health check: `GET /api/v1/health` via `railway.toml`
- CI/CD: `.github/workflows/deploy.yml` — test + build-frontend + deploy to Railway

### Key Deployment Files
| File | Purpose |
|------|---------|
| `railway.toml` | Railway deploy config with health check |
| `Dockerfile` | Multi-stage build (frontend + backend) |
| `docker-compose.yml` | Local dev (PostGIS + API + nginx) |
| `.github/workflows/deploy.yml` | CI/CD pipeline |
| `.env.example` | Environment variable template |

## Database Migration

```bash
# Alembic migrations
python3 -m alembic upgrade head
python3 -m alembic revision -m "description"

# Seed data
python3 scripts/seed_data.py
```

Connection pooling: `pool_size=5`, `max_overflow=10`, `pool_pre_ping=True`, `pool_recycle=3600`.
