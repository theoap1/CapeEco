"""initial_schema

Revision ID: ca1bb4842c9d
Create Date: 2026-01-30

Applies the full CapeEco PostGIS schema from scripts/schema.sql.
This is the baseline migration — all tables, enums, staging tables, and comments.
"""
from pathlib import Path

from alembic import op

revision = "ca1bb4842c9d"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA_SQL = Path(__file__).resolve().parents[2] / "scripts" / "schema.sql"


def upgrade():
    sql = SCHEMA_SQL.read_text()
    # Execute each statement separately (Alembic/psycopg2 can't handle multi-statement)
    for stmt in sql.split(";"):
        stmt = stmt.strip()
        if stmt and not stmt.startswith("--"):
            op.execute(stmt)


def downgrade():
    op.execute("DROP SCHEMA IF EXISTS capeeco CASCADE")
