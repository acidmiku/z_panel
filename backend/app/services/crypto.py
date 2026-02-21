"""Fernet encryption/decryption for sensitive data at rest."""
import hashlib
import base64
import logging
from cryptography.fernet import Fernet, InvalidToken
from app.config import settings

logger = logging.getLogger(__name__)

_fernet_instance = None


def _get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance

    key = settings.ENCRYPTION_KEY
    if not key:
        raise ValueError("ENCRYPTION_KEY must be set in environment")

    try:
        _fernet_instance = Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        raise ValueError(
            "ENCRYPTION_KEY is not a valid Fernet key. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return _fernet_instance


def _derive_legacy_fernet(raw_key: str) -> Fernet:
    """Derive a Fernet instance from a legacy non-Fernet key string via SHA-256."""
    digest = hashlib.sha256(raw_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(plaintext: str) -> str:
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()


def decrypt_with_legacy_fallback(ciphertext: str, legacy_key: str | None = None) -> str:
    """Decrypt, falling back to legacy SHA-256-derived key if the current key fails."""
    f = _get_fernet()
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        if legacy_key:
            legacy_f = _derive_legacy_fernet(legacy_key)
            return legacy_f.decrypt(ciphertext.encode()).decode()
        raise
