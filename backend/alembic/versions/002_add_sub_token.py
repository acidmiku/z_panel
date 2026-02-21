"""Add subscription token to users.

Revision ID: 002
Revises: 001
"""
import secrets
from alembic import op
import sqlalchemy as sa


revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("sub_token", sa.String(64), nullable=True))

    # Backfill existing users with tokens
    conn = op.get_bind()
    users = conn.execute(sa.text("SELECT id FROM users WHERE sub_token IS NULL")).fetchall()
    for row in users:
        token = secrets.token_urlsafe(32)
        conn.execute(
            sa.text("UPDATE users SET sub_token = :token WHERE id = :uid"),
            {"token": token, "uid": row[0]},
        )

    op.create_index("ix_users_sub_token", "users", ["sub_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_sub_token", table_name="users")
    op.drop_column("users", "sub_token")
