"""
Security & cache status endpoint — admin-only monitoring.
GET /api/security/status  → cache stats, encryption health, lockout summary, JWT config
"""
from flask import Blueprint, jsonify, request
from app.middleware.auth_middleware import token_required, _login_attempts
import time

security_bp = Blueprint('security', __name__, url_prefix='/api/security')


@security_bp.route('/status', methods=['GET'])
@token_required
def security_status():
    if request.user.get('role') != 'admin':
        return jsonify({'error': 'Admin only'}), 403

    # Cache stats
    from app.services.cache_service import cache_stats
    cache_info = cache_stats()

    # Encryption health check
    enc_ok = False
    try:
        from app.utils.encryption import encrypt_field, decrypt_field
        test_val = 'health_check'
        enc_ok = decrypt_field(encrypt_field(test_val)) == test_val
    except Exception:
        enc_ok = False

    # Brute-force lockout summary
    now = time.time()
    locked_ips = [
        ip for ip, entry in _login_attempts.items()
        if entry.get('locked_until', 0) > now
    ]
    total_tracked = len(_login_attempts)

    # JWT config (non-secret info only)
    from config.config import Config
    jwt_info = {
        'algorithm':      Config.JWT_ALGORITHM,
        'expiration_sec': Config.JWT_EXPIRATION,
        'expiration_hrs': round(Config.JWT_EXPIRATION / 3600, 1),
    }

    # Security headers active
    headers_active = True  # always on — wired in create_app

    return jsonify({
        'cache': cache_info,
        'encryption': {
            'field_level_ok':  enc_ok,
            'algorithm':       'Fernet (AES-128-CBC + HMAC-SHA256)',
            'sensitive_fields': 'SystemConfig.is_sensitive=True values encrypted at rest',
        },
        'brute_force_protection': {
            'max_attempts':    5,
            'lockout_seconds': 300,
            'tracked_ips':     total_tracked,
            'currently_locked': len(locked_ips),
        },
        'jwt':             jwt_info,
        'security_headers': headers_active,
        'tls_mqtt':        Config.MQTT_USE_TLS,
    }), 200


@security_bp.route('/cache/clear', methods=['POST'])
@token_required
def clear_cache():
    if request.user.get('role') != 'admin':
        return jsonify({'error': 'Admin only'}), 403

    from app.services.cache_service import cache_delete_pattern
    cache_delete_pattern('*')
    return jsonify({'message': 'Cache cleared'}), 200
