"""Re-encrypt CF tokens and encrypt Reality private keys with proper Fernet key.

Revision ID: 005
Revises: 004
"""
import os
import hashlib
import base64
from alembic import op
import sqlalchemy as sa
from cryptography.fernet import Fernet, InvalidToken


revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None

# The old dummy key that was in .env
LEGACY_RAW_KEY = "dummykeyfordevelopment123456789"


def _legacy_fernet() -> Fernet:
    digest = hashlib.sha256(LEGACY_RAW_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _current_fernet() -> Fernet:
    key = os.environ.get("ENCRYPTION_KEY", "")
    return Fernet(key.encode())


def _reencrypt_value(current_f, legacy_f, ciphertext, label):
    """Try current key, then legacy key. Returns new ciphertext or None."""
    try:
        current_f.decrypt(ciphertext.encode())
        return None  # already correct
    except (InvalidToken, Exception):
        pass

    try:
        plaintext = legacy_f.decrypt(ciphertext.encode()).decode()
        return current_f.encrypt(plaintext.encode()).decode()
    except (InvalidToken, Exception):
        print(f"WARNING: Cannot decrypt {label} — skipping")
        return None


def upgrade():
    conn = op.get_bind()
    current_f = _current_fernet()
    legacy_f = _legacy_fernet()

    # Re-encrypt CF tokens
    cf_rows = conn.execute(sa.text("SELECT id, api_token FROM cloudflare_configs")).fetchall()
    for row in cf_rows:
        new_ct = _reencrypt_value(current_f, legacy_f, row[1], f"CF token {row[0]}")
        if new_ct:
            conn.execute(
                sa.text("UPDATE cloudflare_configs SET api_token = :token WHERE id = :id"),
                {"token": new_ct, "id": row[0]},
            )
            print(f"Re-encrypted CF token for config {row[0]}")

    # Encrypt Reality private keys (previously stored as plaintext)
    srv_rows = conn.execute(
        sa.text("SELECT id, reality_private_key FROM servers WHERE reality_private_key IS NOT NULL")
    ).fetchall()
    for row in srv_rows:
        raw_key = row[1]
        # Check if already encrypted (try to decrypt)
        try:
            current_f.decrypt(raw_key.encode())
            continue  # already encrypted
        except (InvalidToken, Exception):
            pass

        # It's plaintext — encrypt it
        encrypted = current_f.encrypt(raw_key.encode()).decode()
        conn.execute(
            sa.text("UPDATE servers SET reality_private_key = :key WHERE id = :id"),
            {"key": encrypted, "id": row[0]},
        )
        print(f"Encrypted Reality private key for server {row[0]}")


def downgrade():
    pass
