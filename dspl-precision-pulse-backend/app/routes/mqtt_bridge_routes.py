"""
MQTT Bridge — authenticated endpoint that publishes any payload to MQTT.
All create/update/delete operations from the frontend go through here
instead of hitting REST routes directly. The MQTT subscriber handles
the DB write and emits the result back to the frontend via Socket.IO.

Allowed topics (whitelist prevents abuse):
  precisionpulse/sync/parameters
  precisionpulse/sync/users/created
  precisionpulse/sync/users/updated
  precisionpulse/sync/users/deleted
  precisionpulse/sync/roles/changed
  precisionpulse/config/update
  precisionpulse/config/bulk-update
  precisionpulse/+/parameter/edit
"""

import uuid
import json
import logging
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from app.middleware.auth_middleware import token_required

logger = logging.getLogger(__name__)

mqtt_bridge_bp = Blueprint('mqtt_bridge', __name__, url_prefix='/api/mqtt-bridge')

# Whitelist of topic prefixes the frontend is allowed to publish to
_ALLOWED_PREFIXES = (
    'precisionpulse/sync/parameters',
    'precisionpulse/sync/users/',
    'precisionpulse/sync/roles/',
    'precisionpulse/config/',
    'precisionpulse/commands/',
    'precisionpulse/presence/',
    'precisionpulse/desktop/parameter/',
)


def _topic_allowed(topic: str) -> bool:
    return any(topic.startswith(p) for p in _ALLOWED_PREFIXES)


@mqtt_bridge_bp.route('/publish', methods=['POST'])
@token_required
def publish():
    """
    Publish a payload to an MQTT topic.
    Body: { "topic": "precisionpulse/...", "payload": {...} }
    Returns immediately — the subscriber handles the DB write asynchronously
    and emits the result back via Socket.IO.
    """
    data = request.get_json(force=True, silent=True) or {}
    topic   = data.get('topic', '')
    payload = data.get('payload', {})

    if not topic:
        return jsonify({'error': 'topic required'}), 400
    if not _topic_allowed(topic):
        return jsonify({'error': f'Topic not allowed: {topic}'}), 403

    # Inject metadata
    payload.setdefault('msg_id',    str(uuid.uuid4()))
    payload.setdefault('timestamp', datetime.now(timezone.utc).isoformat())
    payload.setdefault('source',    'frontend')
    payload['actor'] = request.user.get('email', '')

    try:
        from app.services.mqtt_publisher import get_mqtt_publisher
        pub = get_mqtt_publisher()
        ok  = pub._publish(topic, payload)
        if ok:
            logger.info('[BRIDGE] Published to %s by %s', topic, payload['actor'])
            return jsonify({'ok': True, 'msg_id': payload['msg_id']}), 200
        else:
            # MQTT not connected — handle inline so the operation still succeeds
            logger.warning('[BRIDGE] MQTT not connected, handling inline for %s', topic)
            _handle_inline(topic, payload, request.user)
            return jsonify({'ok': True, 'msg_id': payload['msg_id'], 'inline': True}), 200
    except Exception as e:
        logger.error('[BRIDGE] Error publishing to %s: %s', topic, e)
        return jsonify({'error': str(e)}), 500


def _handle_inline(topic: str, payload: dict, user: dict):
    """
    Fallback: when MQTT broker is unreachable, apply the operation directly
    to PostgreSQL and emit via Socket.IO — same result, no MQTT hop.
    """
    try:
        from app import get_socketio
        sio = get_socketio()

        if 'sync/parameters' in topic:
            _inline_parameter(payload, sio)
        elif 'sync/users/created' in topic or payload.get('type') == 'user_created':
            _inline_user(payload, 'create', sio)
        elif 'sync/users/updated' in topic or payload.get('type') == 'user_updated':
            _inline_user(payload, 'update', sio)
        elif 'sync/users/deleted' in topic or payload.get('type') == 'user_deleted':
            _inline_user(payload, 'delete', sio)
        elif 'sync/roles/changed' in topic or payload.get('type') == 'role_changed':
            _inline_role(payload, sio)
        elif 'config/' in topic:
            _inline_config(payload, sio)
        elif 'parameter/edit' in topic or payload.get('type') == 'parameter_value_updated':
            _inline_param_value(payload, sio)
    except Exception as e:
        logger.error('[BRIDGE] Inline fallback error: %s', e)


def _inline_parameter(payload: dict, sio):
    action     = payload.get('action', '')
    param_data = payload.get('parameter', {})
    if not param_data:
        return
    from app.models.parameter import Parameter
    from app.models import db
    if action == 'create':
        p = Parameter(
            name=param_data['name'], unit=param_data.get('unit', ''),
            description=param_data.get('description', ''),
            enabled=param_data.get('enabled', True),
            alert_min=param_data.get('alert_min'), alert_max=param_data.get('alert_max'),
            warn_min=param_data.get('warn_min'),   warn_max=param_data.get('warn_max'),
        )
        db.session.add(p)
        db.session.commit()
        if sio: sio.emit('parameter_created', {'parameter': p.to_dict()}, namespace='/')
    elif action == 'update':
        p = Parameter.query.get(param_data.get('id'))
        if p:
            for k, v in param_data.items():
                if k != 'id' and hasattr(p, k):
                    setattr(p, k, v)
            db.session.commit()
            if sio: sio.emit('parameter_updated', {'parameter': p.to_dict()}, namespace='/')
    elif action == 'delete':
        p = Parameter.query.get(param_data.get('id'))
        if p:
            db.session.delete(p)
            db.session.commit()
            if sio: sio.emit('parameter_deleted', {'parameter_id': param_data.get('id')}, namespace='/')


def _inline_user(payload: dict, action: str, sio):
    user_data = payload.get('user', {})
    email = user_data.get('email')
    if not email:
        return
    from app.models.user import User
    from app.models import db
    if action == 'delete':
        u = User.query.filter_by(email=email).first()
        if u:
            uid = u.id
            db.session.delete(u)
            db.session.commit()
            if sio: sio.emit('user_deleted', {'user_id': uid, 'email': email}, namespace='/')
    else:
        u = User.query.filter_by(email=email).first()
        if u:
            u.name      = user_data.get('name', u.name)
            u.role      = user_data.get('role', u.role)
            u.is_active = user_data.get('is_active', u.is_active)
            db.session.commit()
            if sio: sio.emit('user_updated', {'user': u.to_dict()}, namespace='/')
        else:
            import bcrypt, secrets
            u = User(email=email, name=user_data.get('name', email.split('@')[0]),
                     role=user_data.get('role', 'user'), is_active=user_data.get('is_active', True))
            ph = user_data.get('password_hash')
            u.password_hash = ph if ph else bcrypt.hashpw(secrets.token_bytes(32), bcrypt.gensalt()).decode()
            db.session.add(u)
            db.session.commit()
            if sio: sio.emit('user_created', {'user': u.to_dict()}, namespace='/')


def _inline_role(payload: dict, sio):
    email    = payload.get('email')
    new_role = payload.get('new_role')
    if not email or not new_role:
        return
    from app.models.user import User
    from app.models import db
    u = User.query.filter_by(email=email).first()
    if u:
        u.role = new_role
        db.session.commit()
        if sio: sio.emit('user_updated', {'user': u.to_dict()}, namespace='/')


def _inline_config(payload: dict, sio):
    key   = payload.get('key')
    value = payload.get('value')
    if not key:
        return
    from app.models.system_config import SystemConfig
    from app.models import db
    cfg = SystemConfig.query.filter_by(key=key).first()
    if cfg:
        cfg.value = str(value)
        db.session.commit()
        if sio: sio.emit('config_update', {'key': key, 'value': value}, namespace='/')


def _inline_param_value(payload: dict, sio):
    param_id = payload.get('parameter_id')
    value    = payload.get('value')
    if param_id is None or value is None:
        return
    from app.models.parameter_stream import ParameterStream
    from app.models import db
    from datetime import datetime, timezone
    record = ParameterStream(
        parameter_id=int(param_id), value=float(value),
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None), synced=True
    )
    db.session.add(record)
    db.session.commit()
    if sio:
        sio.emit('parameter_value_updated',
                 {'parameter_id': param_id, 'value': float(value),
                  'timestamp': record.timestamp.isoformat(), 'source': 'admin'},
                 namespace='/')
