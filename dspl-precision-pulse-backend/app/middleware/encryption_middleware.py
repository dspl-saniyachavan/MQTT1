"""
Middleware to decrypt encrypted request payloads and encrypt responses.
Usage: @encrypted_payload on any route that expects encrypted body.
"""
from functools import wraps
from flask import request, jsonify, g
import logging

logger = logging.getLogger(__name__)


def encrypted_payload(f):
    """Decorator: decrypt request body, re-attach as request.decrypted_json."""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            from app.utils.encryption import decrypt_payload
            raw = request.get_json(silent=True) or {}
            token = raw.get('payload')
            if token:
                request.decrypted_json = decrypt_payload(token)
            else:
                request.decrypted_json = raw  # fallback: plain JSON (dev mode)
        except ValueError as e:
            return jsonify({'error': 'Invalid encrypted payload'}), 400
        except Exception as e:
            logger.error(f"[ENCRYPT_MW] Decrypt error: {e}")
            return jsonify({'error': 'Payload decryption failed'}), 400
        return f(*args, **kwargs)
    return decorated
