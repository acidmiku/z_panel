"""Add jumphosts, jumphost traffic snapshots, routing rules, and user routing configs.

Revision ID: 008
Revises: 007
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    # Jumphosts
    op.create_table(
        "jumphosts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("ip", sa.String(45), nullable=False),
        sa.Column("ssh_port", sa.Integer(), server_default="22"),
        sa.Column("ssh_user", sa.String(255), server_default="root"),
        sa.Column("ssh_key_id", UUID(as_uuid=True), sa.ForeignKey("ssh_keys.id"), nullable=False),
        sa.Column("host_key", sa.Text(), nullable=True),
        sa.Column("shadowsocks_port", sa.Integer(), nullable=True),
        sa.Column("shadowsocks_method", sa.String(100), server_default="2022-blake3-aes-128-gcm"),
        sa.Column("shadowsocks_server_key", sa.Text(), nullable=True),
        sa.Column("tunnel_private_key", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), server_default="provisioning"),
        sa.Column("status_message", sa.Text(), nullable=True),
        sa.Column("hardened", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("last_health_check", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sing_box_version", sa.String(50), nullable=True),
        sa.Column("system_stats", sa.JSON(), nullable=True),
        sa.Column("traffic_cache", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Jumphost traffic snapshots
    op.create_table(
        "jumphost_traffic_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("jumphost_id", UUID(as_uuid=True), sa.ForeignKey("jumphosts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bytes_rx", sa.BigInteger(), server_default="0"),
        sa.Column("bytes_tx", sa.BigInteger(), server_default="0"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_jh_traffic_snapshots_jh_time", "jumphost_traffic_snapshots", ["jumphost_id", "recorded_at"])

    # Routing rules
    op.create_table(
        "routing_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("domain_pattern", sa.String(500), nullable=False),
        sa.Column("match_type", sa.String(30), nullable=False, server_default="domain-suffix"),
        sa.Column("action", sa.String(10), nullable=False, server_default="proxy"),
        sa.Column("order", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # User routing configs
    op.create_table(
        "user_routing_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("geo_rules", sa.JSON(), nullable=True),
        sa.Column("jumphost_id", UUID(as_uuid=True), sa.ForeignKey("jumphosts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("jumphost_protocol", sa.String(10), server_default="ss"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("user_routing_configs")
    op.drop_table("routing_rules")
    op.drop_index("ix_jh_traffic_snapshots_jh_time", table_name="jumphost_traffic_snapshots")
    op.drop_table("jumphost_traffic_snapshots")
    op.drop_table("jumphosts")
