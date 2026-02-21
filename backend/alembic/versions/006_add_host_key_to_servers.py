"""Add host_key column to servers for SSH host key pinning.

Revision ID: 006
Revises: 005
"""
from alembic import op
import sqlalchemy as sa


revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("servers", sa.Column("host_key", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("servers", "host_key")
