"""
Backend unit tests — cover config, models, routes, and utility functions.
These run against an in-memory SQLite database (no Postgres required).
"""
import pytest
import json
import os
from datetime import datetime, timezone


# ── Config ────────────────────────────────────────────────────────────────────

def test_config_jwt_secret_set():
    assert os.environ.get('JWT_SECRET') is not None


def test_config_database_url_set():
    assert os.environ.get('DATABASE_URL') is not None


# ── App factory ───────────────────────────────────────────────────────────────

def test_app_creates(app):
    assert app is not None


def test_app_is_testing(app):
    assert app.config['TESTING'] is True


def test_app_has_socketio(app):
    assert hasattr(app, 'socketio')


# ── Health endpoint ───────────────────────────────────────────────────────────

def test_health_endpoint(client):
    resp = client.get('/api/internal/health')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None


# ── Auth routes ───────────────────────────────────────────────────────────────

def test_login_missing_body(client):
    resp = client.post('/api/auth/login',
                       data=json.dumps({}),
                       content_type='application/json')
    assert resp.status_code in (400, 401, 422)


def test_login_invalid_credentials(client):
    resp = client.post('/api/auth/login',
                       data=json.dumps({'email': 'nobody@test.com', 'password': 'wrong'}),
                       content_type='application/json')
    assert resp.status_code in (401, 404)


def test_login_returns_json(client):
    resp = client.post('/api/auth/login',
                       data=json.dumps({'email': 'admin@precisionpulse.com', 'password': 'admin123'}),
                       content_type='application/json')
    assert resp.content_type.startswith('application/json')


# ── Parameter routes ──────────────────────────────────────────────────────────

def test_parameters_requires_auth(client):
    resp = client.get('/api/parameters')
    assert resp.status_code == 401


def test_parameters_with_bad_token(client):
    resp = client.get('/api/parameters',
                      headers={'Authorization': 'Bearer invalid.token.here'})
    assert resp.status_code == 401


# ── Telemetry routes ──────────────────────────────────────────────────────────

def test_telemetry_config_public(client):
    resp = client.get('/api/telemetry/config')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'max_chart_data_points' in data
    assert 'fetch_interval_ms' in data


def test_telemetry_stream_missing_fields(client):
    resp = client.post('/api/telemetry/stream',
                       data=json.dumps({}),
                       content_type='application/json')
    assert resp.status_code == 400


def test_telemetry_stream_valid(client):
    payload = {
        'client_id': 'test-device',
        'parameters': [{'parameter_id': 1, 'name': 'temp', 'value': 25.0, 'unit': 'C'}]
    }
    resp = client.post('/api/telemetry/stream',
                       data=json.dumps(payload),
                       content_type='application/json')
    assert resp.status_code == 200


# ── Config routes ─────────────────────────────────────────────────────────────

def test_config_public_endpoint(client):
    resp = client.get('/api/config/public')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'configs' in data


def test_config_requires_auth(client):
    resp = client.get('/api/config/')
    assert resp.status_code == 401


# ── Parameter stream routes ───────────────────────────────────────────────────

def test_parameter_stream_push_missing_fields(client):
    resp = client.post('/api/parameter-stream/push',
                       data=json.dumps({}),
                       content_type='application/json')
    assert resp.status_code == 400


def test_parameter_stream_push_valid(client):
    payload = {
        'client_id': 'test-device',
        'parameters': [{'parameter_id': 1, 'value': 42.0}]
    }
    resp = client.post('/api/parameter-stream/push',
                       data=json.dumps(payload),
                       content_type='application/json')
    assert resp.status_code == 200


def test_parameter_stream_latest(client):
    resp = client.get('/api/parameter-stream/latest')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'parameters' in data


# ── Audit log routes ──────────────────────────────────────────────────────────

def test_audit_logs_requires_auth(client):
    resp = client.get('/api/audit-logs')
    assert resp.status_code == 401


# ── MQTT status ───────────────────────────────────────────────────────────────

def test_mqtt_status_endpoint(client):
    resp = client.get('/api/mqtt/status')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'status' in data or 'connected' in data


# ── Sync routes ───────────────────────────────────────────────────────────────

def test_sync_user_missing_email(client):
    resp = client.post('/api/internal/sync-user',
                       data=json.dumps({}),
                       content_type='application/json')
    assert resp.status_code == 400


def test_sync_user_creates_user(client, app_context):
    from app.models import db
    from app.models.user import User
    with app_context.app_context():
        payload = {
            'email': 'testuser@example.com',
            'name': 'Test User',
            'role': 'user',
            'is_active': True
        }
        resp = client.post('/api/internal/sync-user',
                           data=json.dumps(payload),
                           content_type='application/json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['user']['email'] == 'testuser@example.com'


# ── Models ────────────────────────────────────────────────────────────────────

def test_user_model_to_dict(app_context):
    from app.models.user import User
    with app_context.app_context():
        u = User(email='x@test.com', name='X', role='user',
                 created_at=datetime.now(timezone.utc),
                 updated_at=datetime.now(timezone.utc))
        u.set_password('password123')
        d = u.to_dict()
        assert d['email'] == 'x@test.com'
        assert d['role'] == 'user'
        assert 'password_hash' not in d


def test_user_password_check(app_context):
    from app.models.user import User
    with app_context.app_context():
        u = User(email='y@test.com', name='Y', role='user')
        u.set_password('mypassword')
        assert u.check_password('mypassword') is True
        assert u.check_password('wrongpassword') is False


def test_parameter_model_to_dict(app_context):
    from app.models.parameter import Parameter
    with app_context.app_context():
        p = Parameter(name='Temperature', unit='C', enabled=True)
        d = p.to_dict()
        assert d['name'] == 'Temperature'
        assert d['unit'] == 'C'
        assert d['enabled'] is True


def test_parameter_stream_model_to_dict(app_context):
    from app.models.parameter_stream import ParameterStream
    with app_context.app_context():
        ts = datetime.now(timezone.utc)
        ps = ParameterStream(parameter_id=1, value=99.5, timestamp=ts, synced=False)
        d = ps.to_dict()
        assert d['value'] == 99.5
        assert d['parameter_id'] == 1
        assert d['synced'] is False


def test_system_config_model_to_dict(app_context):
    from app.models.system_config import SystemConfig
    with app_context.app_context():
        sc = SystemConfig(key='TEST_KEY', value='test_value', category='general', data_type='string')
        d = sc.to_dict()
        assert d['key'] == 'TEST_KEY'
        assert d['value'] == 'test_value'


def test_system_config_get_typed_value_int(app_context):
    from app.models.system_config import SystemConfig
    with app_context.app_context():
        sc = SystemConfig(key='INT_KEY', value='42', data_type='integer')
        assert sc.get_typed_value() == 42


def test_system_config_get_typed_value_bool(app_context):
    from app.models.system_config import SystemConfig
    with app_context.app_context():
        sc = SystemConfig(key='BOOL_KEY', value='true', data_type='boolean')
        assert sc.get_typed_value() is True


def test_audit_log_model_to_dict(app_context):
    from app.models.audit_log import AuditLog
    with app_context.app_context():
        log = AuditLog(
            event_type='login_success', severity='info',
            actor_email='admin@test.com', action='login', status='success'
        )
        d = log.to_dict()
        assert d['event_type'] == 'login_success'
        assert d['status'] == 'success'


# ── Cache service ─────────────────────────────────────────────────────────────

def test_cache_set_and_get():
    from app.services.cache_service import cache_set, cache_get, cache_delete
    cache_set('test_key', {'value': 123}, ttl=60)
    result = cache_get('test_key')
    assert result == {'value': 123}
    cache_delete('test_key')
    assert cache_get('test_key') is None


def test_cache_miss_returns_none():
    from app.services.cache_service import cache_get
    assert cache_get('nonexistent_key_xyz') is None


# ── JWT utils ─────────────────────────────────────────────────────────────────

def test_jwt_generate_and_verify(app_context):
    from app.utils.jwt_utils import create_token, verify_token
    with app_context.app_context():
        token = create_token(1, 'test@test.com', 'admin')
        assert token is not None
        payload = verify_token(token)
        assert payload is not None
        assert payload.get('email') == 'test@test.com'


def test_jwt_invalid_token_returns_none(app_context):
    from app.utils.jwt_utils import verify_token
    with app_context.app_context():
        result = verify_token('invalid.token.string')
        assert result is None
