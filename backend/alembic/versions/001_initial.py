"""initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )

    op.create_table(
        "cloudflare_configs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("api_token", sa.Text(), nullable=False),
        sa.Column("zone_id", sa.String(255), nullable=False),
        sa.Column("base_domain", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "ssh_keys",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("private_key_path", sa.String(512), nullable=False),
        sa.Column("fingerprint", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "servers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("ip", sa.String(45), nullable=False),
        sa.Column("ssh_port", sa.Integer(), nullable=True, server_default="22"),
        sa.Column("ssh_key_id", sa.UUID(), nullable=False),
        sa.Column("ssh_user", sa.String(255), nullable=True, server_default="root"),
        sa.Column("cf_config_id", sa.UUID(), nullable=False),
        sa.Column("subdomain", sa.String(255), nullable=True),
        sa.Column("fqdn", sa.String(255), nullable=True),
        sa.Column("cf_dns_record_id", sa.String(255), nullable=True),
        sa.Column("hysteria2_port", sa.Integer(), nullable=True, server_default="443"),
        sa.Column("reality_port", sa.Integer(), nullable=True, server_default="443"),
        sa.Column("reality_private_key", sa.Text(), nullable=True),
        sa.Column("reality_public_key", sa.Text(), nullable=True),
        sa.Column("reality_short_id", sa.String(16), nullable=True),
        sa.Column("reality_dest", sa.String(255), nullable=True, server_default="dl.google.com:443"),
        sa.Column("reality_server_name", sa.String(255), nullable=True, server_default="dl.google.com"),
        sa.Column("status", sa.String(20), nullable=True, server_default="provisioning"),
        sa.Column("status_message", sa.Text(), nullable=True),
        sa.Column("last_health_check", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sing_box_version", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["ssh_key_id"], ["ssh_keys.id"]),
        sa.ForeignKeyConstraint(["cf_config_id"], ["cloudflare_configs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("uuid", sa.UUID(), nullable=True),
        sa.Column("hysteria2_password", sa.String(255), nullable=False),
        sa.Column("traffic_limit_bytes", sa.BigInteger(), nullable=True),
        sa.Column("traffic_used_bytes", sa.BigInteger(), nullable=True, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=True, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )

    op.create_table(
        "server_user_traffic",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("server_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("bytes_up", sa.BigInteger(), nullable=True, server_default="0"),
        sa.Column("bytes_down", sa.BigInteger(), nullable=True, server_default="0"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("server_id", "user_id", "recorded_at", name="uq_server_user_traffic"),
    )


def downgrade() -> None:
    op.drop_table("server_user_traffic")
    op.drop_table("users")
    op.drop_table("servers")
    op.drop_table("ssh_keys")
    op.drop_table("cloudflare_configs")
    op.drop_table("admin_users")
