"""Add subdomain_prefix to servers and server_traffic_snapshots table.

Revision ID: 003
Revises: 002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add subdomain_prefix column to servers
    op.add_column("servers", sa.Column("subdomain_prefix", sa.String(50), nullable=True))

    # Backfill existing servers with 'vpn' (matching the old hardcoded prefix)
    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE servers SET subdomain_prefix = 'vpn' WHERE subdomain_prefix IS NULL")
    )

    # Create server_traffic_snapshots table
    op.create_table(
        "server_traffic_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("server_id", UUID(as_uuid=True), sa.ForeignKey("servers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bytes_rx", sa.BigInteger(), default=0),
        sa.Column("bytes_tx", sa.BigInteger(), default=0),
        sa.Column("recorded_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_traffic_snapshots_server_time",
        "server_traffic_snapshots",
        ["server_id", "recorded_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_traffic_snapshots_server_time", table_name="server_traffic_snapshots")
    op.drop_table("server_traffic_snapshots")
    op.drop_column("servers", "subdomain_prefix")
