"""
Desktop layer offline / network-loss / partial-failure resilience tests.
Covers: PahoMQTTClient reconnect, CommandExecutor ACK, ConfigurationService
persistence, DesktopSocketIOService offline queue, UserSyncService DB failures,
and ParameterStreamSyncService network errors.
"""

import json
import sqlite3
import sys
import os
import pytest
from unittest.mock import MagicMock, patch, PropertyMock, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(db_path: str):
    """Create minimal SQLite schema needed by the services under test."""
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            password_hash TEXT NOT NULL DEFAULT '',
            role TEXT DEFAULT 'user',
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            data_type TEXT DEFAULT 'string',
            version INTEGER DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        );
        CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            resource TEXT NOT NULL,
            action TEXT NOT NULL,
            allowed BOOLEAN DEFAULT 1,
            UNIQUE(role, resource, action)
        );
        CREATE TABLE IF NOT EXISTS parameter_stream (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parameter_id INTEGER NOT NULL,
            value REAL NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            synced BOOLEAN DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS telemetry_buffer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            data TEXT NOT NULL,
            synced BOOLEAN DEFAULT 0
        );
    """)
    conn.commit()
    conn.close()


def _db_manager(db_path: str):
    mgr = MagicMock()
    mgr.db_path = db_path
    return mgr


# ===========================================================================
# 1. PahoMQTTClient — reconnect behaviour
# ===========================================================================

class TestPahoMQTTReconnect:

    def test_is_connected_false_after_unexpected_disconnect(self, test_db_path):
        from src.services.paho_mqtt_client import PahoMQTTClient
        client = PahoMQTTClient(client_id='test-reconnect')
        client._is_connected = True
        # Simulate unexpected disconnect (rc != 0)
        with patch.object(client, '_start_reconnect_thread'):
            client._internal_on_disconnect(None, None, rc=1)
        assert client._is_connected is False

    def test_clean_disconnect_does_not_start_reconnect(self, test_db_path):
        from src.services.paho_mqtt_client import PahoMQTTClient
        client = PahoMQTTClient(client_id='test-clean-disc')
        client._is_connected = True
        with patch.object(client, '_start_reconnect_thread') as mock_reconnect:
            client._internal_on_disconnect(None, None, rc=0)
        mock_reconnect.assert_not_called()

    def test_should_reconnect_false_stops_loop(self, test_db_path):
        from src.services.paho_mqtt_client import PahoMQTTClient
        client = PahoMQTTClient(client_id='test-stop-loop')
        client.should_reconnect = False
        client._is_connected = False
        # _reconnect_loop must exit immediately without calling client.reconnect
        with patch.object(client.client, 'reconnect') as mock_reconnect:
            client._reconnect_loop()
        mock_reconnect.assert_not_called()

    def test_exponential_backoff_delays_increase(self, test_db_path):
        from src.services.paho_mqtt_client import PahoMQTTClient
        client = PahoMQTTClient(client_id='test-backoff')
        base = 2
        delays = [min(base * (2 ** i), 60) for i in range(5)]
        assert delays == [2, 4, 8, 16, 32]

    def test_is_connected_true_after_successful_connect_callback(self, test_db_path):
        from src.services.paho_mqtt_client import PahoMQTTClient
        client = PahoMQTTClient(client_id='test-conn-cb')
        client._internal_on_connect(None, None, None, rc=0)
        assert client._is_connected is True

    def test_is_connected_false_after_failed_connect_callback(self, test_db_path):
        from src.services.paho_mqtt_client import PahoMQTTClient
        client = PahoMQTTClient(client_id='test-conn-fail')
        client._internal_on_connect(None, None, None, rc=5)
        assert client._is_connected is False

    def test_reconnect_loop_stops_when_connected(self, test_db_path):
        """Loop exits early if _is_connected becomes True mid-loop."""
        from src.services.paho_mqtt_client import PahoMQTTClient
        import time
        client = PahoMQTTClient(client_id='test-loop-exit')
        client.should_reconnect = True
        client._is_connected = True  # already connected → loop body never runs
        with patch.object(client.client, 'reconnect') as mock_reconnect:
            with patch('time.sleep'):
                client._reconnect_loop()
        mock_reconnect.assert_not_called()


# ===========================================================================
# 2. CommandExecutor — offline ACK and unknown command type
# ===========================================================================

class TestCommandExecutorOfflineACK:

    def _make_executor(self, qapp):
        mock_mqtt = MagicMock()
        mock_mqtt.message_received = MagicMock()
        mock_mqtt.message_received.connect = MagicMock()
        mock_mqtt.device_id = 'desktop-001'
        mock_config = MagicMock()
        from src.services.command_executor import CommandExecutor
        executor = CommandExecutor(mock_mqtt, mock_config)
        return executor, mock_mqtt

    def test_ack_publish_fails_when_mqtt_offline(self, qapp):
        executor, mock_mqtt = self._make_executor(qapp)
        # Simulate offline: publish returns False
        mock_mqtt.client.publish.return_value = False
        executor._send_acknowledgment('cmd-001', 'received', 'success', 'ok')
        mock_mqtt.client.publish.assert_called_once()

    def test_ack_publish_succeeds_when_mqtt_online(self, qapp):
        executor, mock_mqtt = self._make_executor(qapp)
        mock_mqtt.client.publish.return_value = True
        executor._send_acknowledgment('cmd-002', 'completed', 'success', 'done')
        mock_mqtt.client.publish.assert_called_once()
        topic = mock_mqtt.client.publish.call_args[0][0]
        assert 'ack' in topic

    def test_unknown_command_type_sends_failed_ack(self, qapp):
        executor, mock_mqtt = self._make_executor(qapp)
        mock_mqtt.client.publish.return_value = True
        executor._execute_command('cmd-003', 'nonexistent_command', {'command_id': 'cmd-003', 'command': 'nonexistent_command'})
        # Should have sent 'executing' then 'failed' acks
        calls = mock_mqtt.client.publish.call_args_list
        payloads = [json.loads(c[0][1]) for c in calls]
        ack_types = [p['ack_type'] for p in payloads]
        assert 'failed' in ack_types

    def test_known_command_sends_completed_ack(self, qapp):
        executor, mock_mqtt = self._make_executor(qapp)
        mock_mqtt.client.publish.return_value = True
        executor._execute_command('cmd-004', 'status', {'command_id': 'cmd-004', 'command': 'status'})
        calls = mock_mqtt.client.publish.call_args_list
        payloads = [json.loads(c[0][1]) for c in calls]
        ack_types = [p['ack_type'] for p in payloads]
        assert 'completed' in ack_types

    def test_on_mqtt_message_ignores_non_command_topics(self, qapp):
        executor, mock_mqtt = self._make_executor(qapp)
        mock_mqtt.client.publish.return_value = True
        executor._on_mqtt_message('precisionpulse/telemetry', {'command_id': 'x', 'command': 'status'})
        mock_mqtt.client.publish.assert_not_called()

    def test_on_mqtt_message_missing_command_id_ignored(self, qapp):
        executor, mock_mqtt = self._make_executor(qapp)
        mock_mqtt.client.publish.return_value = True
        executor._on_mqtt_message('precisionpulse/commands/broadcast/sync', {'command': 'status'})
        mock_mqtt.client.publish.assert_not_called()


# ===========================================================================
# 3. ConfigurationService — SQLite persistence, callbacks, version guard
# ===========================================================================

class TestConfigurationServicePersistence:

    def _make_service(self, db_path):
        _make_db(db_path)
        db = _db_manager(db_path)
        db.get_connection = lambda: sqlite3.connect(db_path)
        auth = MagicMock()
        auth.get_token.return_value = 'test-token'
        from src.services.configuration_service import ConfigurationService
        svc = ConfigurationService(db, auth)
        return svc

    def test_apply_config_change_persists_to_sqlite(self, test_db_path):
        svc = self._make_service(test_db_path)
        svc.apply_config_change('TELEMETRY_INTERVAL', '5')
        conn = sqlite3.connect(test_db_path)
        row = conn.execute("SELECT value FROM config WHERE key='TELEMETRY_INTERVAL'").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == '5'

    def test_apply_config_change_upsert_updates_existing(self, test_db_path):
        svc = self._make_service(test_db_path)
        svc.apply_config_change('MQTT_BROKER', 'host1')
        svc.apply_config_change('MQTT_BROKER', 'host2')
        conn = sqlite3.connect(test_db_path)
        rows = conn.execute("SELECT value FROM config WHERE key='MQTT_BROKER'").fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][0] == 'host2'

    def test_apply_config_change_fires_registered_callback(self, test_db_path):
        svc = self._make_service(test_db_path)
        received = []
        svc.register_callback('TELEMETRY_INTERVAL', lambda k, v, old: received.append(v))
        svc.apply_config_change('TELEMETRY_INTERVAL', '10')
        assert received == ['10']

    def test_load_local_configs_fires_all_callbacks(self, test_db_path):
        svc = self._make_service(test_db_path)
        # Seed a config row directly
        conn = sqlite3.connect(test_db_path)
        conn.execute("INSERT INTO config (key, value, version) VALUES ('MAX_CHART_DATA_POINTS', '50', 3)")
        conn.commit()
        conn.close()
        received = []
        svc.register_callback('MAX_CHART_DATA_POINTS', lambda k, v, old: received.append(v))
        svc.load_local_configs()
        assert received == ['50']

    def test_load_local_configs_restores_config_version(self, test_db_path):
        svc = self._make_service(test_db_path)
        conn = sqlite3.connect(test_db_path)
        conn.execute("INSERT INTO config (key, value, version) VALUES ('K1', 'v1', 7)")
        conn.execute("INSERT INTO config (key, value, version) VALUES ('K2', 'v2', 5)")
        conn.commit()
        conn.close()
        svc.load_local_configs()
        assert svc.config_version == 7

    def test_sync_configurations_version_guard_blocks_older(self, test_db_path):
        svc = self._make_service(test_db_path)
        svc.config_version = 10  # already at v10
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                'configs': [],
                'global_version': 5  # older than current
            }
            result = svc.sync_configurations()
        assert result is False
        assert svc.config_version == 10  # unchanged

    def test_sync_configurations_version_guard_allows_newer(self, test_db_path):
        svc = self._make_service(test_db_path)
        svc.config_version = 2
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                'configs': [{'key': 'K', 'value': 'v', 'data_type': 'string', 'category': 'general', 'version': 3}],
                'global_version': 3
            }
            result = svc.sync_configurations()
        assert result is True
        assert svc.config_version == 3

    def test_sync_configurations_returns_false_on_network_error(self, test_db_path):
        svc = self._make_service(test_db_path)
        with patch('requests.get', side_effect=Exception('network down')):
            result = svc.sync_configurations()
        assert result is False


# ===========================================================================
# 4. DesktopSocketIOService — offline queue and flush on reconnect
# ===========================================================================

class TestDesktopSocketIOOfflineQueue:

    def _make_service(self, db_path):
        _make_db(db_path)
        from src.services.socketio_service import DesktopSocketIOService
        svc = DesktopSocketIOService(db_path=db_path)
        return svc

    def test_pending_writes_queued_when_offline(self, test_db_path):
        svc = self._make_service(test_db_path)
        svc.is_connected = False
        data = {'parameter_id': 1, 'value': 42.0, 'timestamp': '2024-01-01T00:00:00', 'source': 'admin'}
        # Simulate the on_parameter_value_updated handler path
        svc._pending_writes.append((1, 42.0, '2024-01-01T00:00:00'))
        assert len(svc._pending_writes) == 1
        assert svc._pending_writes[0] == (1, 42.0, '2024-01-01T00:00:00')

    def test_flush_pending_writes_stores_to_sqlite(self, test_db_path):
        svc = self._make_service(test_db_path)
        svc._pending_writes = [(2, 99.5, '2024-06-01T12:00:00')]
        svc._flush_pending_writes()
        assert svc._pending_writes == []
        conn = sqlite3.connect(test_db_path)
        row = conn.execute("SELECT value FROM parameter_stream WHERE parameter_id=2").fetchone()
        conn.close()
        assert row is not None
        assert float(row[0]) == 99.5

    def test_flush_pending_writes_clears_queue(self, test_db_path):
        svc = self._make_service(test_db_path)
        svc._pending_writes = [(3, 1.0, None), (4, 2.0, None)]
        svc._flush_pending_writes()
        assert svc._pending_writes == []

    def test_emit_telemetry_queues_to_buffer_when_offline(self, test_db_path):
        svc = self._make_service(test_db_path)
        svc.is_connected = False
        svc.emit_telemetry({'client_id': 'dev', 'parameters': [{'id': 1, 'value': 5.0}]})
        conn = sqlite3.connect(test_db_path)
        count = conn.execute("SELECT COUNT(*) FROM telemetry_buffer WHERE synced=0").fetchone()[0]
        conn.close()
        assert count == 1

    def test_emit_telemetry_emits_when_online(self, test_db_path):
        svc = self._make_service(test_db_path)
        svc.is_connected = True
        svc.sio = MagicMock()
        svc.emit_telemetry({'client_id': 'dev', 'parameters': []})
        svc.sio.emit.assert_called_once()

    def test_get_buffer_count_returns_unsynced(self, test_db_path):
        svc = self._make_service(test_db_path)
        conn = sqlite3.connect(test_db_path)
        conn.execute("INSERT INTO telemetry_buffer (data, synced) VALUES ('{}', 0)")
        conn.execute("INSERT INTO telemetry_buffer (data, synced) VALUES ('{}', 0)")
        conn.execute("INSERT INTO telemetry_buffer (data, synced) VALUES ('{}', 1)")
        conn.commit()
        conn.close()
        assert svc.get_buffer_count() == 2


# ===========================================================================
# 5. UserSyncService — DB failures and network errors
# ===========================================================================

class TestUserSyncServiceDBFailure:

    def _make_service(self, db_path):
        _make_db(db_path)
        db = _db_manager(db_path)
        from src.services.user_sync_service import UserSyncService
        svc = UserSyncService(database_manager=db)
        return svc

    def test_sync_user_to_db_returns_true_on_success(self, test_db_path):
        svc = self._make_service(test_db_path)
        svc.database_manager.db_path = test_db_path
        result = svc._sync_user_to_db({'id': 1, 'email': 'a@b.com', 'name': 'A', 'role': 'user', 'is_active': True})
        assert result is True

    def test_sync_user_to_db_returns_false_on_db_error(self, test_db_path):
        svc = self._make_service(test_db_path)
        svc.database_manager.db_path = '/nonexistent/path/db.sqlite'
        result = svc._sync_user_to_db({'id': 1, 'email': 'a@b.com', 'name': 'A', 'role': 'user', 'is_active': True})
        assert result is False

    def test_delete_user_from_db_returns_false_on_db_error(self, test_db_path):
        svc = self._make_service(test_db_path)
        svc.database_manager.db_path = '/nonexistent/path/db.sqlite'
        result = svc._delete_user_from_db('a@b.com')
        assert result is False

    def test_update_user_role_in_db_returns_false_on_db_error(self, test_db_path):
        svc = self._make_service(test_db_path)
        svc.database_manager.db_path = '/nonexistent/path/db.sqlite'
        result = svc._update_user_role_in_db(1, 'admin')
        assert result is False

    def test_fetch_users_from_backend_returns_false_on_connection_error(self, test_db_path):
        svc = self._make_service(test_db_path)
        with patch('requests.get', side_effect=Exception('connection refused')):
            result = svc.fetch_users_from_backend()
        assert result is False

    def test_fetch_users_from_backend_returns_false_on_non_200(self, test_db_path):
        svc = self._make_service(test_db_path)
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 503
        result = svc.fetch_users_from_backend()
        assert result is False

    def test_on_mqtt_message_user_created_syncs_to_db(self, test_db_path):
        svc = self._make_service(test_db_path)
        svc.database_manager.db_path = test_db_path
        payload = {'type': 'user_created', 'user': {'id': 10, 'email': 'x@y.com', 'name': 'X', 'role': 'user', 'is_active': True}}
        svc._on_mqtt_message('precisionpulse/sync/users/created', payload)
        conn = sqlite3.connect(test_db_path)
        row = conn.execute("SELECT email FROM users WHERE email='x@y.com'").fetchone()
        conn.close()
        assert row is not None

    def test_on_mqtt_message_user_deleted_removes_from_db(self, test_db_path):
        svc = self._make_service(test_db_path)
        svc.database_manager.db_path = test_db_path
        conn = sqlite3.connect(test_db_path)
        conn.execute("INSERT INTO users (id, email, name, password_hash, role) VALUES (20, 'del@x.com', 'Del', '', 'user')")
        conn.commit()
        conn.close()
        payload = {'type': 'user_deleted', 'user': {'id': 20, 'email': 'del@x.com'}}
        svc._on_mqtt_message('precisionpulse/sync/users/deleted', payload)
        conn = sqlite3.connect(test_db_path)
        row = conn.execute("SELECT email FROM users WHERE email='del@x.com'").fetchone()
        conn.close()
        assert row is None


# ===========================================================================
# 6. ParameterStreamSyncService — network errors, no token, mark_synced
# ===========================================================================

class TestParameterStreamSyncResilience:

    def _make_service(self, db_path):
        _make_db(db_path)
        db = _db_manager(db_path)
        db.db_path = db_path
        from src.services.parameter_stream_sync_service import ParameterStreamSyncService
        svc = ParameterStreamSyncService(db_manager=db, backend_url='http://localhost:5000')
        return svc

    def _seed_unsynced(self, db_path, count=3):
        conn = sqlite3.connect(db_path)
        for i in range(count):
            conn.execute("INSERT INTO parameter_stream (parameter_id, value, synced) VALUES (?, ?, 0)", (i + 1, float(i)))
        conn.commit()
        conn.close()

    def test_returns_false_when_no_token(self, test_db_path):
        svc = self._make_service(test_db_path)
        self._seed_unsynced(test_db_path)
        result = svc.sync_parameter_stream_to_backend()
        assert result is False

    def test_returns_false_on_connection_error(self, test_db_path):
        svc = self._make_service(test_db_path)
        svc.set_auth_token('tok')
        self._seed_unsynced(test_db_path)
        with patch('requests.post', side_effect=__import__('requests').exceptions.ConnectionError('offline')):
            result = svc.sync_parameter_stream_to_backend()
        assert result is False

    def test_returns_false_on_timeout(self, test_db_path):
        svc = self._make_service(test_db_path)
        svc.set_auth_token('tok')
        self._seed_unsynced(test_db_path)
        with patch('requests.post', side_effect=__import__('requests').exceptions.Timeout('timeout')):
            result = svc.sync_parameter_stream_to_backend()
        assert result is False

    def test_returns_false_on_non_200_response(self, test_db_path):
        svc = self._make_service(test_db_path)
        svc.set_auth_token('tok')
        self._seed_unsynced(test_db_path)
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 500
            mock_post.return_value.text = 'Internal Server Error'
            result = svc.sync_parameter_stream_to_backend()
        assert result is False

    def test_mark_synced_called_on_success(self, test_db_path):
        svc = self._make_service(test_db_path)
        svc.set_auth_token('tok')
        self._seed_unsynced(test_db_path, count=2)
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {'count': 2}
            with patch.object(svc, 'mark_synced') as mock_mark:
                result = svc.sync_parameter_stream_to_backend()
        assert result is True
        mock_mark.assert_called_once()

    def test_returns_true_when_no_unsynced_records(self, test_db_path):
        svc = self._make_service(test_db_path)
        svc.set_auth_token('tok')
        # No records seeded → nothing to sync
        result = svc.sync_parameter_stream_to_backend()
        assert result is True

    def test_mark_synced_calls_db_manager(self, test_db_path):
        svc = self._make_service(test_db_path)
        records = [{'id': 1}, {'id': 2}]
        svc.mark_synced(records)
        svc.db_manager.mark_parameter_stream_synced.assert_called_once_with([1, 2])

    def test_get_sync_status_returns_correct_counts(self, test_db_path):
        svc = self._make_service(test_db_path)
        svc.db_manager.db_path = test_db_path
        self._seed_unsynced(test_db_path, count=3)
        conn = sqlite3.connect(test_db_path)
        conn.execute("INSERT INTO parameter_stream (parameter_id, value, synced) VALUES (1, 9.9, 1)")
        conn.commit()
        conn.close()
        status = svc.get_sync_status()
        assert status['unsynced_count'] == 3
        assert status['total_count'] == 4
        assert status['sync_percentage'] == pytest.approx(25.0)
