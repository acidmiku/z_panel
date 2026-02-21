"""Add system_stats and traffic_cache JSON columns to servers.

Revision ID: 004
Revises: 003
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("servers", sa.Column("system_stats", JSON, nullable=True))
    op.add_column("servers", sa.Column("traffic_cache", JSON, nullable=True))


def downgrade() -> None:
    op.drop_column("servers", "traffic_cache")
    op.drop_column("servers", "system_stats")
