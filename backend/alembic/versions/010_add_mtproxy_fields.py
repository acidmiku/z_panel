"""Add MTProxy (telemt) fields to servers and jumphosts.

Revision ID: 010
Revises: 009
"""
from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("servers", sa.Column("mtproxy_enabled", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("servers", sa.Column("mtproxy_port", sa.Integer(), nullable=True))
    op.add_column("servers", sa.Column("mtproxy_secret", sa.Text(), nullable=True))
    op.add_column("servers", sa.Column("mtproxy_tls_domain", sa.String(255), nullable=True))
    op.add_column("servers", sa.Column("mtproxy_link", sa.Text(), nullable=True))

    op.add_column("jumphosts", sa.Column("mtproxy_enabled", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("jumphosts", sa.Column("mtproxy_port", sa.Integer(), nullable=True))
    op.add_column("jumphosts", sa.Column("mtproxy_secret", sa.Text(), nullable=True))
    op.add_column("jumphosts", sa.Column("mtproxy_tls_domain", sa.String(255), nullable=True))
    op.add_column("jumphosts", sa.Column("mtproxy_link", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("jumphosts", "mtproxy_link")
    op.drop_column("jumphosts", "mtproxy_tls_domain")
    op.drop_column("jumphosts", "mtproxy_secret")
    op.drop_column("jumphosts", "mtproxy_port")
    op.drop_column("jumphosts", "mtproxy_enabled")

    op.drop_column("servers", "mtproxy_link")
    op.drop_column("servers", "mtproxy_tls_domain")
    op.drop_column("servers", "mtproxy_secret")
    op.drop_column("servers", "mtproxy_port")
    op.drop_column("servers", "mtproxy_enabled")
