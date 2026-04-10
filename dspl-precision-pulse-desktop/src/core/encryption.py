"""
Payload encryption/decryption for desktop app — mirrors backend app/utils/encryption.py
"""
import os
import base64
import json
import logging
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_KEY_ENV = 'PAYLOAD_ENCRYPTION_KEY'


def _get_fernet() -> Fernet:
    key = os.getenv(_KEY_ENV)
    if not key:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.backends import default_backend
        from src.core.config import Config
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(Config.JWT_SECRET.encode())
        raw = digest.finalize()
        key = base64.urlsafe_b64encode(raw).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


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
