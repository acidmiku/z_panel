"""Add hardened column to servers.

Revision ID: 007
Revises: 006
"""
from alembic import op
import sqlalchemy as sa


revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("servers", sa.Column("hardened", sa.Boolean(), server_default="false", nullable=False))


def downgrade():
    op.drop_column("servers", "hardened")
