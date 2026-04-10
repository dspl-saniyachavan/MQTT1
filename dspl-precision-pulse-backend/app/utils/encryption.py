"""
Payload encryption/decryption using Fernet (AES-128-CBC + HMAC-SHA256).
Shared between backend and desktop via the same PAYLOAD_ENCRYPTION_KEY env var.
Also provides field-level encryption for sensitive DB values.
"""
import os
import base64
import json
import logging
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_KEY_ENV = 'PAYLOAD_ENCRYPTION_KEY'
_fernet_instance: Fernet = None  # cached singleton


def _get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance
    key = os.getenv(_KEY_ENV)
    if not key:
        # Derive a stable 32-byte key from JWT_SECRET so no extra env var is needed
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.backends import default_backend
        import sys, os as _os
        sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
        from config.config import Config
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(Config.JWT_SECRET.encode())
        raw = digest.finalize()
        key = base64.urlsafe_b64encode(raw).decode()
    _fernet_instance = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet_instance


# ── Payload encryption (dict <-> token string) ────────────────────────────────

def encrypt_payload(data: dict) -> str:
    """Encrypt a dict payload → base64 token string."""
    try:
        return _get_fernet().encrypt(json.dumps(data).encode()).decode()
    except Exception as e:
        logger.error(f"[ENCRYPT] Failed: {e}")
        raise


def decrypt_payload(token: str) -> dict:
    """Decrypt a base64 token string → dict."""
    try:
        return json.loads(_get_fernet().decrypt(token.encode()).decode())
    except InvalidToken:
        raise ValueError("Invalid or tampered payload")
    except Exception as e:
        logger.error(f"[DECRYPT] Failed: {e}")
        raise


# ── Field-level encryption (str <-> encrypted str) ────────────────────────────
# Used to encrypt sensitive SystemConfig values at rest in the database.
# Encrypted values are prefixed with 'enc:' so they can be identified.

_ENC_PREFIX = 'enc:'


def encrypt_field(plaintext: str) -> str:
    """Encrypt a string field for storage. Returns 'enc:<fernet_token>'."""
    try:
        token = _get_fernet().encrypt(plaintext.encode()).decode()
        return f"{_ENC_PREFIX}{token}"
    except Exception as e:
        logger.error(f"[ENCRYPT_FIELD] Failed: {e}")
        raise


def decrypt_field(ciphertext: str) -> str:
    """Decrypt a field value. Handles both encrypted ('enc:...') and plaintext."""
    if not ciphertext or not ciphertext.startswith(_ENC_PREFIX):
        return ciphertext  # not encrypted — return as-is (backward compat)
    try:
        token = ciphertext[len(_ENC_PREFIX):]
        return _get_fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        logger.error("[DECRYPT_FIELD] Invalid or tampered ciphertext")
        raise ValueError("Encrypted field is invalid or tampered")
    except Exception as e:
        logger.error(f"[DECRYPT_FIELD] Failed: {e}")
        raise


def is_encrypted_field(value: str) -> bool:
    """Return True if the value is an encrypted field."""
    return isinstance(value, str) and value.startswith(_ENC_PREFIX)
