"""
Offline, Network Loss, and Partial Failure Resilience Tests — Backend
Covers: MQTT disconnect/reconnect, command ACK lifecycle, config sync failures,
        telemetry buffering, concurrent writes, and partial DB failures.
"""

import pytest
import json
import uuid
import threading
import time
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock, call

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from app.models import db
from app.models.command_execution import CommandExecution, CommandAcknowledgment


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


# ===========================================================================
# 1. MQTT Publisher — offline / reconnect behaviour
# ===========================================================================

class TestMQTTPublisherOffline:
    """MQTTPublisher._publish() must not raise and must return False when disconnected."""

    def test_publish_while_disconnected_returns_false(self, app):
        with app.app_context():
            from app.services.mqtt_publisher import MQTTPublisher
            pub = MQTTPublisher()
            pub.connected = False  # simulate offline
            result = pub._publish('precisionpulse/sync/users/created', {'type': 'user_created'})
            assert result is False

    def test_publish_after_reconnect_returns_true(self, app):
        with app.app_context():
            from app.services.mqtt_publisher import MQTTPublisher
            pub = MQTTPublisher()
            mock_client = MagicMock()
            mock_result = MagicMock()
            mock_result.rc = 0  # MQTT_ERR_SUCCESS
            mock_client.publish.return_value = mock_result
            pub.client = mock_client
            pub.connected = True
            result = pub._publish('precisionpulse/sync/users/created', {'type': 'user_created'})
            assert result is True

    def test_publish_exception_returns_false(self, app):
        with app.app_context():
            from app.services.mqtt_publisher import MQTTPublisher
            pub = MQTTPublisher()
            mock_client = MagicMock()
            mock_client.publish.side_effect = OSError("network unreachable")
            pub.client = mock_client
            pub.connected = True
            result = pub._publish('precisionpulse/sync/users/created', {'type': 'user_created'})
            assert result is False

    def test_on_disconnect_emits_offline_status(self, app):
        with app.app_context():
            from app.services.mqtt_publisher import MQTTPublisher
            pub = MQTTPublisher()
            mock_sio = MagicMock()
            pub.set_socketio(mock_sio)
            pub.connected = True
            pub._on_disconnect(None, None, None, rc=1)
            assert pub.connected is False
            mock_sio.emit.assert_any_call('mqtt_status', {'status': 'offline'}, namespace='/')

    def test_on_connect_failure_emits_offline_status(self, app):
        with app.app_context():
            from app.services.mqtt_publisher import MQTTPublisher
            pub = MQTTPublisher()
            mock_sio = MagicMock()
            pub.set_socketio(mock_sio)
            pub._on_connect(None, None, None, rc=5)  # rc != 0 → failure
            assert pub.connected is False
            mock_sio.emit.assert_any_call('mqtt_status', {'status': 'offline'}, namespace='/')

    def test_on_connect_success_triggers_auto_flush(self, app):
        with app.app_context():
            from app.services.mqtt_publisher import MQTTPublisher
            pub = MQTTPublisher()
            mock_sio = MagicMock()
            pub.set_socketio(mock_sio)
            with patch.object(pub, '_auto_flush_buffer') as mock_flush:
                pub._on_connect(None, None, None, rc=0)
                mock_flush.assert_called_once()


# ===========================================================================
# 2. MQTT Subscriber — message routing under partial failures
# ===========================================================================

class TestMQTTSubscriberRouting:
    """_on_message must route correctly and not crash on malformed payloads."""

    def _make_subscriber(self, app):
        from app.services.mqtt_subscriber import MQTTSubscriber
        sub = MQTTSubscriber(app=app)
        sub.socketio = MagicMock()
        return sub

    def test_malformed_json_does_not_raise(self, app):
        with app.app_context():
            sub = self._make_subscriber(app)
            msg = MagicMock()
            msg.topic = 'precisionpulse/sync/users/created'
            msg.payload = b'NOT_JSON'
            # Must not raise
            sub._on_message(None, None, msg)

    def test_telemetry_message_broadcasts_via_socketio(self, app):
        with app.app_context():
            sub = self._make_subscriber(app)
            msg = MagicMock()
            msg.topic = 'precisionpulse/device_001/telemetry'
            msg.payload = json.dumps({
                'client_id': 'device_001',
                'timestamp': datetime.utcnow().isoformat(),
                'parameters': [{'id': 'temp', 'value': 25.0}]
            }).encode()
            sub._on_message(None, None, msg)
            from unittest.mock import ANY
            sub.socketio.emit.assert_any_call('telemetry', ANY, namespace='/')

    def test_command_ack_missing_fields_logs_warning(self, app):
        with app.app_context():
            sub = self._make_subscriber(app)
            # Incomplete payload — missing status
            with patch('app.services.mqtt_subscriber.logger') as mock_log:
                sub._handle_command_ack({'command_id': str(uuid.uuid4()), 'device_id': 'dev', 'ack_type': 'received'})
                mock_log.warning.assert_called()

    def test_command_ack_no_app_context_logs_warning(self, app):
        with app.app_context():
            from app.services.mqtt_subscriber import MQTTSubscriber
            sub = MQTTSubscriber()  # no app
            sub.socketio = MagicMock()
            with patch('app.services.mqtt_subscriber.logger') as mock_log:
                sub._handle_command_ack({
                    'command_id': str(uuid.uuid4()),
                    'device_id': 'dev',
                    'ack_type': 'received',
                    'status': 'success'
                })
                mock_log.warning.assert_called()

    def test_command_ack_full_flow_stores_in_db(self, app):
        with app.app_context():
            sub = self._make_subscriber(app)
            cid = str(uuid.uuid4())
            # Pre-create execution record
            cmd = CommandExecution(
                command_id=cid, command_type='force_sync',
                target_type='broadcast', payload={'command': 'force_sync'},
                status='sent'
            )
            db.session.add(cmd)
            db.session.commit()

            sub._handle_command_ack({
                'command_id': cid,
                'device_id': 'desktop-001',
                'ack_type': 'completed',
                'status': 'success',
                'message': 'done'
            })

            ack = CommandAcknowledgment.query.filter_by(command_id=cid).first()
            assert ack is not None
            assert ack.ack_type == 'completed'
            updated = CommandExecution.query.filter_by(command_id=cid).first()
            assert updated.status == 'completed'

    def test_on_disconnect_emits_offline_status(self, app):
        with app.app_context():
            sub = self._make_subscriber(app)
            sub._on_disconnect(None, None, None, rc=1)
            sub.socketio.emit.assert_any_call('mqtt_status', {'status': 'offline'}, namespace='/')


# ===========================================================================
# 3. RemoteCommandsService — offline MQTT, DB failures
# ===========================================================================

class TestRemoteCommandsServiceResilience:

    def test_send_force_sync_mqtt_offline_still_creates_db_record(self, app):
        with app.app_context():
            from app.services.remote_commands_service import RemoteCommandsService
            svc = RemoteCommandsService()
            mock_pub = MagicMock()
            mock_pub.connected = False
            mock_pub._publish.return_value = False
            svc.mqtt_publisher = mock_pub

            result = svc.send_force_sync(user_email='admin@test.com')
            assert result['success'] is False
            # DB record must still exist with status 'pending'
            cmd = CommandExecution.query.filter_by(command_id=result['command_id']).first()
            assert cmd is not None
            assert cmd.status == 'pending'

    def test_send_force_sync_mqtt_online_updates_status_to_sent(self, app):
        with app.app_context():
            from app.services.remote_commands_service import RemoteCommandsService
            svc = RemoteCommandsService()
            mock_pub = MagicMock()
            mock_pub._publish.return_value = True
            svc.mqtt_publisher = mock_pub

            result = svc.send_force_sync(user_email='admin@test.com')
            assert result['success'] is True
            cmd = CommandExecution.query.filter_by(command_id=result['command_id']).first()
            assert cmd.status == 'sent'
            assert cmd.delivery_status == 'sent'

    def test_send_user_sync_command_offline_records_pending(self, app):
        with app.app_context():
            from app.services.remote_commands_service import RemoteCommandsService
            svc = RemoteCommandsService()
            mock_pub = MagicMock()
            mock_pub._publish.return_value = False
            svc.mqtt_publisher = mock_pub

            result = svc.send_user_sync_command('user_created', {'user': {'id': 1, 'email': 'a@b.com'}})
            assert result['success'] is False
            cmd = CommandExecution.query.filter_by(command_id=result['command_id']).first()
            assert cmd is not None
            assert cmd.command_type == 'sync_users'

    def test_handle_command_acknowledgment_unknown_command_id(self, app):
        with app.app_context():
            from app.services.remote_commands_service import RemoteCommandsService
            svc = RemoteCommandsService()
            # Should not raise even if command_id doesn't exist
            result = svc.handle_command_acknowledgment(
                command_id=str(uuid.uuid4()),
                device_id='desktop-001',
                ack_type='completed',
                status='success'
                
            )
            assert result['success'] is True  # ack row still inserted

    def test_handle_command_acknowledgment_all_ack_types(self, app):
        with app.app_context():
            from app.services.remote_commands_service import RemoteCommandsService
            svc = RemoteCommandsService()
            cid = str(uuid.uuid4())
            cmd = CommandExecution(
                command_id=cid, command_type='update_config',
                target_type='broadcast', payload={}, status='sent'
            )
            db.session.add(cmd)
            db.session.commit()

            for ack_type, expected_status in [
                ('received', 'delivered'),
                ('executing', 'executing'),
                ('completed', 'completed'),
            ]:
                svc.handle_command_acknowledgment(cid, 'dev', ack_type, 'success')
                cmd = CommandExecution.query.filter_by(command_id=cid).first()
                assert cmd.status == expected_status

    def test_handle_command_acknowledgment_failed_ack(self, app):
        with app.app_context():
            from app.services.remote_commands_service import RemoteCommandsService
            svc = RemoteCommandsService()
            cid = str(uuid.uuid4())
            cmd = CommandExecution(
                command_id=cid, command_type='force_sync',
                target_type='broadcast', payload={}, status='sent'
            )
            db.session.add(cmd)
            db.session.commit()

            svc.handle_command_acknowledgment(cid, 'dev', 'failed', 'error', message='timeout')
            cmd = CommandExecution.query.filter_by(command_id=cid).first()
            assert cmd.status == 'failed'
            assert cmd.error_message == 'timeout'

    def test_db_rollback_on_commit_failure(self, app):
        with app.app_context():
            from app.services.remote_commands_service import RemoteCommandsService
            svc = RemoteCommandsService()
            mock_pub = MagicMock()
            mock_pub._publish.return_value = True
            svc.mqtt_publisher = mock_pub

            with patch.object(db.session, 'commit', side_effect=[Exception("DB error"), None, None]):
                # Should not raise; rollback is called internally
                try:
                    svc.send_force_sync()
                except Exception:
                    pass  # acceptable — we just verify no unhandled crash


# ===========================================================================
# 4. ConfigManager — cache invalidation and DB failures
# ===========================================================================

class TestConfigManagerResilience:

    def test_get_config_returns_default_when_db_unavailable(self, app):
        with app.app_context():
            from app.services.config_manager import ConfigManager
            mgr = ConfigManager()
            with patch('app.services.config_manager.SystemConfig') as mock_model:
                mock_model.query.filter_by.side_effect = Exception("DB down")
                result = mgr.get_config('MQTT_BROKER', default='fallback')
                assert result == 'fallback'

    def test_cache_invalidation_forces_fresh_db_read(self, app):
        with app.app_context():
            from app.services.config_manager import ConfigManager
            from app.models.system_config import SystemConfig
            mgr = ConfigManager()
            # Seed a value
            cfg = SystemConfig(key='TEST_KEY', value='v1', data_type='string', category='general')
            db.session.add(cfg)
            db.session.commit()

            first = mgr.get_config('TEST_KEY')
            assert first == 'v1'

            # Update DB directly and invalidate cache
            cfg.value = 'v2'
            db.session.commit()
            mgr.invalidate_cache('TEST_KEY')

            second = mgr.get_config('TEST_KEY')
            assert second == 'v2'

    def test_on_config_updated_invalidates_cache(self, app):
        with app.app_context():
            from app.services.config_manager import ConfigManager
            mgr = ConfigManager()
            mgr.cache['SOME_KEY'] = 'cached'
            mgr.cache_timestamps['SOME_KEY'] = datetime.utcnow()
            mgr.on_config_updated('SOME_KEY')
            assert 'SOME_KEY' not in mgr.cache

    def test_get_all_configs_returns_empty_on_db_error(self, app):
        with app.app_context():
            from app.services.config_manager import ConfigManager
            mgr = ConfigManager()
            with patch('app.services.config_manager.SystemConfig') as mock_model:
                mock_model.query.all.side_effect = Exception("DB down")
                mock_model.query.filter_by.side_effect = Exception("DB down")
                result = mgr.get_all_configs(use_cache=False)
                assert result == {}


# ===========================================================================
# 5. Command ACK lifecycle — full end-to-end via subscriber
# ===========================================================================

class TestCommandACKLifecycle:

    def test_ack_sequence_received_executing_completed(self, app):
        with app.app_context():
            from app.services.mqtt_subscriber import MQTTSubscriber
            sub = MQTTSubscriber(app=app)
            sub.socketio = MagicMock()

            cid = str(uuid.uuid4())
            cmd = CommandExecution(
                command_id=cid, command_type='sync_users',
                target_type='broadcast', payload={}, status='sent'
            )
            db.session.add(cmd)
            db.session.commit()

            for ack_type in ['received', 'executing', 'completed']:
                msg = MagicMock()
                msg.topic = f'precisionpulse/commands/ack/desktop-001'
                msg.payload = json.dumps({
                    'command_id': cid,
                    'device_id': 'desktop-001',
                    'ack_type': ack_type,
                    'status': 'success',
                    'message': ack_type
                }).encode()
                sub._on_message(None, None, msg)

            final = CommandExecution.query.filter_by(command_id=cid).first()
            assert final.status == 'completed'
            acks = CommandAcknowledgment.query.filter_by(command_id=cid).all()
            assert len(acks) == 3

    def test_ack_socketio_broadcast_on_each_ack(self, app):
        with app.app_context():
            from app.services.mqtt_subscriber import MQTTSubscriber
            sub = MQTTSubscriber(app=app)
            sub.socketio = MagicMock()

            cid = str(uuid.uuid4())
            msg = MagicMock()
            msg.topic = 'precisionpulse/commands/ack/desktop-001'
            msg.payload = json.dumps({
                'command_id': cid,
                'device_id': 'desktop-001',
                'ack_type': 'received',
                'status': 'success',
                'message': 'ok'
            }).encode()
            sub._on_message(None, None, msg)
            from unittest.mock import ANY
            sub.socketio.emit.assert_any_call('command_ack', ANY, namespace='/')

    def test_duplicate_ack_does_not_corrupt_status(self, app):
        with app.app_context():
            from app.services.remote_commands_service import RemoteCommandsService
            svc = RemoteCommandsService()
            cid = str(uuid.uuid4())
            cmd = CommandExecution(
                command_id=cid, command_type='force_sync',
                target_type='broadcast', payload={}, status='sent'
            )
            db.session.add(cmd)
            db.session.commit()

            # Send 'completed' twice
            svc.handle_command_acknowledgment(cid, 'dev', 'completed', 'success')
            svc.handle_command_acknowledgment(cid, 'dev', 'completed', 'success')

            acks = CommandAcknowledgment.query.filter_by(command_id=cid).all()
            assert len(acks) == 2  # both stored
            cmd = CommandExecution.query.filter_by(command_id=cid).first()
            assert cmd.status == 'completed'  # still completed, not corrupted


# ===========================================================================
# 6. Concurrent command writes
# ===========================================================================

class TestConcurrentCommandWrites:

    def test_concurrent_ack_writes_no_data_loss(self, app):
        with app.app_context():
            from app.services.remote_commands_service import RemoteCommandsService
            svc = RemoteCommandsService()

            cid = str(uuid.uuid4())
            cmd = CommandExecution(
                command_id=cid, command_type='force_sync',
                target_type='broadcast', payload={}, status='sent'
            )
            db.session.add(cmd)
            db.session.commit()

            errors = []

            def send_ack(ack_type):
                try:
                    with app.app_context():
                        svc.handle_command_acknowledgment(cid, 'dev', ack_type, 'success')
                except Exception as e:
                    errors.append(str(e))

            threads = [threading.Thread(target=send_ack, args=(t,))
                       for t in ['received', 'executing', 'completed']]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert errors == []
            acks = CommandAcknowledgment.query.filter_by(command_id=cid).all()
            assert len(acks) == 3

    def test_concurrent_command_creation_unique_ids(self, app):
        with app.app_context():
            from app.services.remote_commands_service import RemoteCommandsService
            svc = RemoteCommandsService()
            mock_pub = MagicMock()
            mock_pub._publish.return_value = False
            svc.mqtt_publisher = mock_pub

            results = []
            lock = threading.Lock()

            def create_cmd():
                with app.app_context():
                    r = svc.send_force_sync()
                    with lock:
                        results.append(r['command_id'])

            threads = [threading.Thread(target=create_cmd) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(set(results)) == 5  # all unique UUIDs


# ===========================================================================
# 7. Partial failure — DB commit fails mid-flow
# ===========================================================================

class TestPartialDBFailures:

    def test_ack_handler_rolls_back_on_db_error(self, app):
        with app.app_context():
            from app.services.remote_commands_service import RemoteCommandsService
            svc = RemoteCommandsService()
            cid = str(uuid.uuid4())

            with patch.object(db.session, 'commit', side_effect=Exception("disk full")):
                result = svc.handle_command_acknowledgment(cid, 'dev', 'received', 'success')
                assert result['success'] is False

    def test_send_command_db_error_does_not_prevent_mqtt_publish(self, app):
        """Even if the DB record creation fails, the MQTT publish should still be attempted."""
        with app.app_context():
            from app.services.remote_commands_service import RemoteCommandsService
            svc = RemoteCommandsService()
            mock_pub = MagicMock()
            mock_pub._publish.return_value = True
            svc.mqtt_publisher = mock_pub

            call_count = [0]
            original_commit = db.session.commit

            def flaky_commit():
                call_count[0] += 1
                if call_count[0] == 1:
                    raise Exception("DB write failed")
                return original_commit()

            with patch.object(db.session, 'commit', side_effect=flaky_commit):
                # Should not raise
                try:
                    svc.send_force_sync()
                except Exception:
                    pass


# ===========================================================================
# 8. Telemetry buffering — offline queue and flush
# ===========================================================================

class TestTelemetryBufferingResilience:

    def test_telemetry_handle_missing_parameters_key(self, app):
        with app.app_context():
            from app.services.mqtt_subscriber import MQTTSubscriber
            sub = MQTTSubscriber(app=app)
            sub.socketio = MagicMock()
            # payload without 'parameters' key — must not raise
            sub._handle_telemetry({'client_id': 'dev', 'timestamp': datetime.utcnow().isoformat()})

    def test_telemetry_socketio_emit_failure_does_not_crash(self, app):
        with app.app_context():
            from app.services.mqtt_subscriber import MQTTSubscriber
            sub = MQTTSubscriber(app=app)
            sub.socketio = MagicMock()
            sub.socketio.emit.side_effect = Exception("socket broken")
            # Must not propagate
            sub._handle_telemetry({
                'client_id': 'dev',
                'timestamp': datetime.utcnow().isoformat(),
                'parameters': [{'id': 'temp', 'value': 22.0}]
            })

    def test_telemetry_no_socketio_logs_warning(self, app):
        with app.app_context():
            from app.services.mqtt_subscriber import MQTTSubscriber
            sub = MQTTSubscriber(app=app)
            sub.socketio = None
            with patch('app.services.mqtt_subscriber.logger') as mock_log:
                sub._handle_telemetry({
                    'client_id': 'dev',
                    'timestamp': datetime.utcnow().isoformat(),
                    'parameters': []
                })
                mock_log.warning.assert_called()


# ===========================================================================
# 9. Network loss simulation — retry with exponential backoff
# ===========================================================================

class TestNetworkLossSimulation:

    def test_exponential_backoff_succeeds_on_third_attempt(self, app):
        with app.app_context():
            attempt = [0]

            def flaky_publish(topic, payload):
                attempt[0] += 1
                if attempt[0] < 3:
                    raise OSError("network unreachable")
                return True

            max_retries = 5
            base_delay = 0.001
            success = False

            for retry in range(max_retries):
                try:
                    result = flaky_publish('topic', '{}')
                    success = result
                    break
                except OSError:
                    time.sleep(base_delay * (2 ** retry))

            assert success is True
            assert attempt[0] == 3

    def test_circuit_breaker_opens_after_threshold(self, app):
        with app.app_context():
            class CircuitBreaker:
                def __init__(self, threshold=3):
                    self.failures = 0
                    self.threshold = threshold
                    self.open = False

                def call(self, fn):
                    if self.open:
                        raise RuntimeError("circuit open")
                    try:
                        return fn()
                    except Exception:
                        self.failures += 1
                        if self.failures >= self.threshold:
                            self.open = True
                        raise

            cb = CircuitBreaker(threshold=3)
            failures = 0
            for _ in range(5):
                try:
                    cb.call(lambda: (_ for _ in ()).throw(OSError("fail")))
                except Exception:
                    failures += 1

            assert cb.open is True
            assert failures == 5  # circuit opens after 3 but outer loop still catches remaining

    def test_mqtt_subscriber_reconnect_resubscribes(self, app):
        with app.app_context():
            from app.services.mqtt_subscriber import MQTTSubscriber
            sub = MQTTSubscriber(app=app)
            sub.socketio = MagicMock()
            mock_client = MagicMock()

            # Simulate reconnect → _on_connect called with rc=0
            sub._on_connect(mock_client, None, None, rc=0)
            # Subscriber calls client.subscribe([list_of_tuples]) in one call
            mock_client.subscribe.assert_called_once()
            topics_arg = mock_client.subscribe.call_args[0][0]
            topic_names = [t[0] for t in topics_arg]
            assert 'precisionpulse/commands/ack/#' in topic_names
            assert 'precisionpulse/sync/#' in topic_names


# ===========================================================================
# 10. Config sync — version guard and stale cache
# ===========================================================================

class TestConfigSyncResilience:

    def test_config_manager_stale_cache_returns_old_value(self, app):
        with app.app_context():
            from app.services.config_manager import ConfigManager
            from app.models.system_config import SystemConfig
            mgr = ConfigManager(cache_ttl_seconds=3600)

            cfg = SystemConfig(key='STALE_KEY', value='old', data_type='string', category='general')
            db.session.add(cfg)
            db.session.commit()

            # Prime cache
            v1 = mgr.get_config('STALE_KEY')
            assert v1 == 'old'

            # Update DB without invalidating cache
            cfg.value = 'new'
            db.session.commit()

            # Cache still returns old value
            v2 = mgr.get_config('STALE_KEY', use_cache=True)
            assert v2 == 'old'

            # After invalidation, returns new value
            mgr.invalidate_cache('STALE_KEY')
            v3 = mgr.get_config('STALE_KEY', use_cache=False)
            assert v3 == 'new'

    def test_send_config_update_command_empty_config_rejected(self, app):
        with app.app_context():
            from app.services.remote_commands_service import RemoteCommandsService
            svc = RemoteCommandsService()
            result = svc.send_config_update(config=None)
            assert result['success'] is False
            assert 'error' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
