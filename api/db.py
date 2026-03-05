"""
Siteline — Shared database configuration.

Provides connection string resolution, engine creation, and schema constant.
Used by both the API layer and CLI engines.
"""

import logging
import os

from sqlalchemy import create_engine, text

logger = logging.getLogger("siteline")

SCHEMA = os.environ.get("SITELINE_SCHEMA", "capeeco")


def _conn_string():
    """Resolve database connection string from environment."""
    raw = os.environ.get("DATABASE_URL")
    if raw is None:
        for k, v in os.environ.items():
            if k.strip() == "DATABASE_URL":
                raw = v
                break
    if raw is None:
        raw = os.environ.get("DATABASE_PRIVATE_URL")
    db_url = raw or ""
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return db_url
    pw = os.environ.get("PGPASSWORD", "")
    host = os.environ.get("PGHOST", "localhost")
    port = os.environ.get("PGPORT", "5432")
    user = os.environ.get("PGUSER", os.environ.get("USER", "postgres"))
    name = os.environ.get("PGDATABASE", "capeeco")
    url = f"postgresql://{user}:{pw}@{host}:{port}/{name}" if pw else f"postgresql://{user}@{host}:{port}/{name}"
    return url


# Global engine — initialized in lifespan
engine = None


def init_engine():
    """Create and return the SQLAlchemy engine."""
    global engine
    conn_str = _conn_string()
    engine = create_engine(
        conn_str,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    return engine


def get_engine():
    """Return the current engine, initializing if needed."""
    if engine is None:
        return init_engine()
    return engine


def ensure_tables():
    """Ensure required tables exist (users, property_valuations).

    Uses a short lock_timeout so startup doesn't hang if another process
    (e.g. data loader) holds a lock on a table.
    """
    e = get_engine()
    try:
        with e.connect() as conn:
            # Prevent hanging on locked tables — skip indexes if we can't get the lock
            conn.execute(text("SET lock_timeout = '5s'"))
            conn.execute(text(f"""
                CREATE SCHEMA IF NOT EXISTS {SCHEMA}
            """))
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.users (
                    id          BIGSERIAL PRIMARY KEY,
                    email       VARCHAR(255) UNIQUE NOT NULL,
                    hashed_password VARCHAR(255) NOT NULL,
                    full_name   VARCHAR(255),
                    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """))
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_users_email ON {SCHEMA}.users(email)"))
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.property_valuations (
                    id                  BIGSERIAL PRIMARY KEY,
                    property_id         BIGINT NOT NULL UNIQUE,
                    property_reference  VARCHAR(50),
                    market_value_zar    NUMERIC(15,2),
                    valuation_date      DATE DEFAULT '2022-07-01',
                    rating_category     VARCHAR(100),
                    fetched_at          TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_pv_property ON {SCHEMA}.property_valuations(property_id)"))
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_pv_market_value ON {SCHEMA}.property_valuations(market_value_zar)"))
            # Chat conversations
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.conversations (
                    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id     BIGINT NOT NULL REFERENCES {SCHEMA}.users(id) ON DELETE CASCADE,
                    title       VARCHAR(200) NOT NULL DEFAULT 'New chat',
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """))
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_conv_user ON {SCHEMA}.conversations(user_id, updated_at DESC)"))
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.conversation_messages (
                    id              BIGSERIAL PRIMARY KEY,
                    conversation_id UUID NOT NULL REFERENCES {SCHEMA}.conversations(id) ON DELETE CASCADE,
                    role            VARCHAR(20) NOT NULL,
                    content         TEXT NOT NULL DEFAULT '',
                    tool_calls      JSONB,
                    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """))
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_cm_conv ON {SCHEMA}.conversation_messages(conversation_id, created_at)"))
            # Police stations & crime stats
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.police_stations (
                    id          BIGSERIAL PRIMARY KEY,
                    station_name VARCHAR(200) NOT NULL,
                    province    VARCHAR(100),
                    geom        geometry(Geometry, 4326) NOT NULL,
                    created_at  TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.crime_stats (
                    id          BIGSERIAL PRIMARY KEY,
                    station_id  BIGINT REFERENCES {SCHEMA}.police_stations(id),
                    station_name VARCHAR(200) NOT NULL,
                    category    VARCHAR(200) NOT NULL,
                    year        VARCHAR(20) NOT NULL,
                    count       INTEGER NOT NULL DEFAULT 0,
                    created_at  TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            # Load shedding blocks
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.loadshedding_blocks (
                    id              BIGSERIAL PRIMARY KEY,
                    block_number    INTEGER NOT NULL,
                    block_name      VARCHAR(50),
                    area_sqm        DOUBLE PRECISION,
                    geom            geometry(Geometry, 4326) NOT NULL,
                    created_at      TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            # Zoning rules (CTZS Table A)
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.zoning_rules (
                    id            SERIAL PRIMARY KEY,
                    zone_code     VARCHAR(10) NOT NULL UNIQUE,
                    zone_name     VARCHAR(100) NOT NULL,
                    setback_front NUMERIC(5,2) DEFAULT 4.5,
                    setback_side  NUMERIC(5,2) DEFAULT 1.5,
                    setback_rear  NUMERIC(5,2) DEFAULT 3.0,
                    coverage_pct  NUMERIC(5,2) DEFAULT 50,
                    far           NUMERIC(5,3) DEFAULT 0.500,
                    height_limit  NUMERIC(5,1) DEFAULT 9.0,
                    max_floors    INTEGER DEFAULT 2,
                    parking_ratio NUMERIC(5,2) DEFAULT 1.50,
                    min_erf_sqm   NUMERIC(10,2) DEFAULT 0,
                    notes         TEXT
                )
            """))
            conn.commit()
            logger.info("Tables ready")
    except Exception as e:
        logger.warning("Table check skipped (lock timeout or error): %s", e)
