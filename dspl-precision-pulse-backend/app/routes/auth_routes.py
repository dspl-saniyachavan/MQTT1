import re
from flask import Blueprint, request, jsonify
from app.controllers.auth_controller import AuthController
from app.middleware.auth_middleware import (
    token_required, is_locked_out, record_failed_login, clear_failed_login
)

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')


def _sanitize(s: str) -> str:
    """Strip leading/trailing whitespace and remove null bytes."""
    return s.strip().replace('\x00', '') if isinstance(s, str) else s


@auth_bp.route('/login', methods=['POST'])
def login():
    ip = request.remote_addr or '0.0.0.0'

    # Brute-force lockout check
    if is_locked_out(ip):
        return jsonify({
            'error': 'Too many failed login attempts. Try again in 5 minutes.'
        }), 429

    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    email    = _sanitize(data.get('email', ''))
    password = _sanitize(data.get('password', ''))

    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    if not _EMAIL_RE.match(email):
        return jsonify({'error': 'Invalid email format'}), 400

    result, status = AuthController.login(email, password)

    if status == 200:
        clear_failed_login(ip)   # reset counter on success
        # Track online status
        from app.services.online_users_service import mark_online
        mark_online(email)
        # Publish presence via MQTT so desktop manage-users page updates
        try:
            from app.routes.mqtt_status_routes import get_subscriber
            sub = get_subscriber()
            if sub and sub.connected:
                import json as _json
                sub.client.publish(
                    f'precisionpulse/presence/web',
                    _json.dumps({'email': email, 'status': 'online'}),
                    qos=1
                )
        except Exception:
            pass
    elif status in (401, 403):
        record_failed_login(ip)  # increment counter on failure

    return jsonify(result), status


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    email    = _sanitize(data.get('email', ''))
    name     = _sanitize(data.get('name', ''))
    password = _sanitize(data.get('password', ''))

    if not email or not password or not name:
        return jsonify({'error': 'Email, name, and password required'}), 400

    if not _EMAIL_RE.match(email):
        return jsonify({'error': 'Invalid email format'}), 400

    if len(name) > 120:
        return jsonify({'error': 'Name too long (max 120 chars)'}), 400

    result, status = AuthController.register(
        email, name, password, data.get('role', 'user')
    )
    return jsonify(result), status


@auth_bp.route('/refresh', methods=['POST'])
@token_required
def refresh_token():
    from app.utils.jwt_utils import create_token
    user = request.user
    new_token = create_token(user['user_id'], user['email'], user['role'])
    return jsonify({'token': new_token}), 200


@auth_bp.route('/logout', methods=['POST'])
@token_required
def logout():
    user = request.user
    try:
        from app.services.online_users_service import mark_offline
        mark_offline(user.get('email', ''))
        # Publish offline presence via MQTT so desktop manage-users page updates
        try:
            from app.routes.mqtt_status_routes import get_subscriber
            sub = get_subscriber()
            if sub and sub.connected:
                import json as _json
                sub.client.publish(
                    f'precisionpulse/presence/web',
                    _json.dumps({'email': user.get('email', ''), 'status': 'offline'}),
                    qos=1
                )
        except Exception:
            pass
        from app import get_socketio
        sio = get_socketio()
        if sio:
            sio.emit('user_logged_out', {'email': user.get('email'), 'user_id': user.get('user_id')}, namespace='/')
    except Exception:
        pass
    return jsonify({'message': 'Logged out'}), 200
