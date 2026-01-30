"""Add users table for authentication.

Revision ID: b2f3a8d91e01
Revises: ca1bb4842c9d
Create Date: 2026-01-30
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "b2f3a8d91e01"
down_revision = "ca1bb4842c9d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="capeeco",
    )
    op.create_index("idx_users_email", "users", ["email"], schema="capeeco")


def downgrade():
    op.drop_index("idx_users_email", table_name="users", schema="capeeco")
    op.drop_table("users", schema="capeeco")
