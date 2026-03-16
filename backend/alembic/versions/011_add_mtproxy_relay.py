"""Add mtproxy relay server FK to jumphosts.

Revision ID: 011
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jumphosts",
        sa.Column("mtproxy_relay_server_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_jh_mtproxy_relay_server",
        "jumphosts",
        "servers",
        ["mtproxy_relay_server_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_jh_mtproxy_relay_server", "jumphosts", type_="foreignkey")
    op.drop_column("jumphosts", "mtproxy_relay_server_id")
