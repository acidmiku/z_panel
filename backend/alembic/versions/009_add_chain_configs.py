"""Add chain_configs table for visual proxy chain editor.

Revision ID: 009
Revises: 008
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "chain_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("graph_data", sa.JSON(), nullable=False),
        sa.Column("generated_config", sa.JSON(), nullable=True),
        sa.Column("is_valid", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("validation_errors", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_chain_configs_user_id", "chain_configs", ["user_id"])


def downgrade():
    op.drop_index("ix_chain_configs_user_id", table_name="chain_configs")
    op.drop_table("chain_configs")
