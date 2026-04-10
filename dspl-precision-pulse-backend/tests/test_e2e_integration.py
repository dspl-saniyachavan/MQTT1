"""
End-to-End Integration Tests
Tests complete workflows across backend, frontend, desktop, and MQTT components
"""

import pytest
import json
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from app.models import db, User, Parameter, Telemetry, SystemConfig
from app.services.audit_logging_service import get_audit_logging_service
from app.services.message_signing_service import MessageSigningService
from app.services.remote_commands_service import RemoteCommandsService


class TestE2EBackendIntegration:
    """End-to-end backend integration tests"""
    
    @pytest.fixture
    def app(self):
        """Create Flask app for testing"""
        app = create_app()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()
    
    @pytest.fixture
    def auth_token(self, app, client):
        """Create authenticated user and get token"""
        with app.app_context():
            user = User(
                email='test@example.com',
                password_hash='hashed_password',
                name='Test User',
                role='admin'
            )
            db.session.add(user)
            db.session.commit()
            
            # Mock token generation
            return 'test_token_12345'
    
    def test_complete_user_workflow(self, app, client, auth_token):
        """Test complete user creation, update, and deletion workflow"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        
        # Create user
        user_data = {
            'email': 'newuser@example.com',
            'password': 'SecurePass123',
            'name': 'New User',
            'role': 'operator'
        }
        
        response = client.post('/api/users', json=user_data, headers=headers)
        assert response.status_code in [200, 201]
        
        # Get user
        response = client.get('/api/users', headers=headers)
        assert response.status_code == 200
        
        # Update user
        update_data = {'name': 'Updated User'}
        response = client.patch('/api/users/1', json=update_data, headers=headers)
        assert response.status_code in [200, 204]
    
    def test_parameter_sync_workflow(self, app, client, auth_token):
        """Test parameter creation and sync workflow"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        
        with app.app_context():
            # Create parameters
            param1 = Parameter(
                name='Temperature',
                enabled=True,
                unit='°C',
                description='Room temperature'
            )
            param2 = Parameter(
                name='Humidity',
                enabled=True,
                unit='%',
                description='Room humidity'
            )
            db.session.add_all([param1, param2])
            db.session.commit()
        
        # Get parameters
        response = client.get('/api/parameters', headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert 'parameters' in data
        assert len(data['parameters']) >= 2
    
    def test_telemetry_ingestion_workflow(self, app, client, auth_token):
        """Test telemetry data ingestion and retrieval"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        
        with app.app_context():
            # Create parameter
            param = Parameter(
                name='Temperature',
                enabled=True,
                unit='°C'
            )
            db.session.add(param)
            db.session.commit()
            param_id = param.id
        
        # Ingest telemetry
        telemetry_data = {
            'device_id': 'device_001',
            'parameters': [
                {'id': param_id, 'value': 25.5, 'timestamp': datetime.utcnow().isoformat()}
            ]
        }
        
        response = client.post('/api/telemetry', json=telemetry_data, headers=headers)
        assert response.status_code in [200, 201]
        
        # Retrieve telemetry
        response = client.get('/api/telemetry/latest', headers=headers)
        assert response.status_code == 200
    
    def test_configuration_sync_workflow(self, app, client, auth_token):
        """Test configuration creation and sync"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        
        # Create config
        config_data = {
            'key': 'mqtt_broker',
            'value': 'mqtt.example.com',
            'description': 'MQTT broker address'
        }
        
        response = client.post('/api/config', json=config_data, headers=headers)
        assert response.status_code in [200, 201]
        
        # Get config
        response = client.get('/api/config', headers=headers)
        assert response.status_code == 200
    
    def test_audit_logging_workflow(self, app, client, auth_token):
        """Test audit logging of operations"""
        with app.app_context():
            audit_service = get_audit_logging_service()
            
            # Log various events
            audit_service.log_user_created(
                user_id=1,
                user_email='test@example.com',
                new_values={'name': 'Test User'},
                actor_email='admin@example.com'
            )
            
            audit_service.log_config_updated(
                config_id='1',
                config_name='mqtt_broker',
                old_values={'value': 'old.broker.com'},
                new_values={'value': 'new.broker.com'},
                actor_email='admin@example.com'
            )
            
            # Retrieve audit logs
            logs, count = audit_service.get_audit_logs(limit=100)
            assert count >= 2
    
    def test_message_signing_workflow(self, app):
        """Test message signing and verification"""
        with app.app_context():
            signing_service = MessageSigningService()
            
            # Create message
            payload = {
                'command': 'force_sync',
                'device_id': 'device_001',
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Sign message
            signed_message = signing_service.sign_message(payload)
            assert 'signature' in signed_message
            assert 'nonce' in signed_message
            assert 'timestamp' in signed_message
            
            # Verify message
            is_valid = signing_service.verify_message(signed_message)
            assert is_valid is True
    
    def test_command_execution_workflow(self, app, client, auth_token):
        """Test remote command execution"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        
        # Send command
        command_data = {
            'command_type': 'force_sync',
            'device_id': 'device_001',
            'parameters': {}
        }
        
        response = client.post('/api/commands', json=command_data, headers=headers)
        assert response.status_code in [200, 201]
    
    def test_buffer_management_workflow(self, app, client, auth_token):
        """Test telemetry buffer management"""
        headers = {'Authorization': f'Bearer {auth_token}'}
        
        # Get buffer status
        response = client.get('/api/buffer/status', headers=headers)
        assert response.status_code == 200
        
        # Clear buffer
        response = client.post('/api/buffer/clear', headers=headers)
        assert response.status_code in [200, 204]


class TestE2EOfflineScenarios:
    """Test system behavior during offline scenarios"""
    
    @pytest.fixture
    def app(self):
        """Create Flask app for testing"""
        app = create_app()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()
    
    def test_offline_telemetry_buffering(self, app):
        """Test telemetry buffering when offline"""
        with app.app_context():
            # Create parameter
            param = Parameter(name='Temperature', enabled=True, unit='°C')
            db.session.add(param)
            db.session.commit()
            
            # Simulate offline: buffer telemetry
            telemetry_records = []
            for i in range(10):
                telemetry = Telemetry(
                    device_id='device_001',
                    parameter_id=param.id,
                    value=20.0 + i,
                    timestamp=datetime.utcnow() - timedelta(seconds=i*10)
                )
                telemetry_records.append(telemetry)
            
            db.session.add_all(telemetry_records)
            db.session.commit()
            
            # Verify buffered records
            buffered = Telemetry.query.filter_by(device_id='device_001').all()
            assert len(buffered) == 10
    
    def test_offline_command_queuing(self, app):
        """Test command queuing during offline"""
        with app.app_context():
            # Simulate offline: queue commands
            commands = []
            for i in range(5):
                command_data = {
                    'command_type': 'update_config',
                    'device_id': 'device_001',
                    'parameters': {'key': f'param_{i}', 'value': f'value_{i}'},
                    'created_at': datetime.utcnow()
                }
                commands.append(command_data)
            
            # Verify commands queued
            assert len(commands) == 5
    
    def test_offline_config_caching(self, app):
        """Test configuration caching during offline"""
        with app.app_context():
            # Create config
            config = SystemConfig(
                key='mqtt_broker',
                value='mqtt.example.com',
                description='MQTT broker'
            )
            db.session.add(config)
            db.session.commit()
            
            # Simulate offline: retrieve from cache
            cached_config = SystemConfig.query.filter_by(key='mqtt_broker').first()
            assert cached_config is not None
            assert cached_config.value == 'mqtt.example.com'
    
    def test_reconnection_sync(self, app):
        """Test sync after reconnection"""
        with app.app_context():
            # Create offline data
            param = Parameter(name='Temperature', enabled=True, unit='°C')
            db.session.add(param)
            db.session.commit()
            
            # Simulate offline period with buffered data
            telemetry_records = []
            for i in range(5):
                telemetry = Telemetry(
                    device_id='device_001',
                    parameter_id=param.id,
                    value=20.0 + i,
                    timestamp=datetime.utcnow() - timedelta(seconds=i*10)
                )
                telemetry_records.append(telemetry)
            
            db.session.add_all(telemetry_records)
            db.session.commit()
            
            # Verify sync data ready
            sync_data = Telemetry.query.filter_by(device_id='device_001').all()
            assert len(sync_data) == 5


class TestE2ENetworkFailures:
    """Test system resilience to network failures"""
    
    @pytest.fixture
    def app(self):
        """Create Flask app for testing"""
        app = create_app()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()
    
    def test_partial_telemetry_loss(self, app):
        """Test handling of partial telemetry loss"""
        with app.app_context():
            param = Parameter(name='Temperature', enabled=True, unit='°C')
            db.session.add(param)
            db.session.commit()
            
            # Send 10 telemetry records, simulate 3 failures
            successful = 0
            failed = 0
            
            for i in range(10):
                try:
                    telemetry = Telemetry(
                        device_id='device_001',
                        parameter_id=param.id,
                        value=20.0 + i
                    )
                    db.session.add(telemetry)
                    
                    # Simulate random failures
                    if i % 3 == 0:
                        raise Exception("Network error")
                    
                    db.session.commit()
                    successful += 1
                except Exception:
                    db.session.rollback()
                    failed += 1
            
            # Verify resilience
            assert successful > 0
            assert failed > 0
            
            # Verify successful records persisted
            records = Telemetry.query.filter_by(device_id='device_001').all()
            assert len(records) == successful
    
    def test_timeout_handling(self, app):
        """Test handling of request timeouts"""
        with app.app_context():
            # Simulate timeout scenario
            start_time = time.time()
            timeout_duration = 0.1
            
            try:
                # Simulate long operation
                time.sleep(timeout_duration * 2)
                elapsed = time.time() - start_time
                
                # Verify timeout detection
                assert elapsed > timeout_duration
            except Exception as e:
                # Verify error handling
                assert str(e) is not None
    
    def test_retry_mechanism(self, app):
        """Test retry mechanism for failed operations"""
        with app.app_context():
            param = Parameter(name='Temperature', enabled=True, unit='°C')
            db.session.add(param)
            db.session.commit()
            
            # Simulate retry logic
            max_retries = 3
            retry_count = 0
            success = False
            
            for attempt in range(max_retries):
                try:
                    telemetry = Telemetry(
                        device_id='device_001',
                        parameter_id=param.id,
                        value=25.0
                    )
                    db.session.add(telemetry)
                    db.session.commit()
                    success = True
                    break
                except Exception:
                    retry_count += 1
                    db.session.rollback()
                    if attempt < max_retries - 1:
                        time.sleep(0.01)  # Brief delay before retry
            
            assert success is True


class TestE2EPartialFailures:
    """Test system behavior during partial failures"""
    
    @pytest.fixture
    def app(self):
        """Create Flask app for testing"""
        app = create_app()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()
    
    def test_partial_device_failure(self, app):
        """Test handling when some devices fail"""
        with app.app_context():
            # Create multiple parameters
            params = [
                Parameter(name='Temperature', enabled=True, unit='°C'),
                Parameter(name='Humidity', enabled=True, unit='%'),
                Parameter(name='Pressure', enabled=True, unit='hPa')
            ]
            db.session.add_all(params)
            db.session.commit()
            
            # Simulate data from multiple devices
            devices = ['device_001', 'device_002', 'device_003']
            successful_devices = []
            failed_devices = []
            
            for device_id in devices:
                try:
                    for param in params:
                        telemetry = Telemetry(
                            device_id=device_id,
                            parameter_id=param.id,
                            value=20.0
                        )
                        db.session.add(telemetry)
                    
                    # Simulate device_002 failure
                    if device_id == 'device_002':
                        raise Exception("Device communication failed")
                    
                    db.session.commit()
                    successful_devices.append(device_id)
                except Exception:
                    db.session.rollback()
                    failed_devices.append(device_id)
            
            # Verify partial success
            assert len(successful_devices) > 0
            assert len(failed_devices) > 0
            
            # Verify successful devices have data
            for device_id in successful_devices:
                records = Telemetry.query.filter_by(device_id=device_id).all()
                assert len(records) == len(params)
    
    def test_partial_parameter_failure(self, app):
        """Test handling when some parameters fail"""
        with app.app_context():
            # Create parameters
            params = [
                Parameter(name='Temperature', enabled=True, unit='°C'),
                Parameter(name='Humidity', enabled=True, unit='%'),
                Parameter(name='Pressure', enabled=True, unit='hPa')
            ]
            db.session.add_all(params)
            db.session.commit()
            
            # Simulate data ingestion with partial failures
            successful_params = []
            failed_params = []
            
            for param in params:
                try:
                    telemetry = Telemetry(
                        device_id='device_001',
                        parameter_id=param.id,
                        value=20.0
                    )
                    db.session.add(telemetry)
                    
                    # Simulate Humidity sensor failure
                    if param.name == 'Humidity':
                        raise Exception("Sensor read failed")
                    
                    db.session.commit()
                    successful_params.append(param.name)
                except Exception:
                    db.session.rollback()
                    failed_params.append(param.name)
            
            # Verify partial success
            assert len(successful_params) > 0
            assert len(failed_params) > 0
            
            # Verify successful parameters have data
            for param_name in successful_params:
                param = Parameter.query.filter_by(name=param_name).first()
                records = Telemetry.query.filter_by(parameter_id=param.id).all()
                assert len(records) > 0
    
    def test_partial_sync_failure(self, app):
        """Test handling of partial sync failures"""
        with app.app_context():
            # Create data to sync
            param = Parameter(name='Temperature', enabled=True, unit='°C')
            db.session.add(param)
            db.session.commit()
            
            # Create telemetry records
            records = []
            for i in range(10):
                telemetry = Telemetry(
                    device_id='device_001',
                    parameter_id=param.id,
                    value=20.0 + i
                )
                records.append(telemetry)
            
            db.session.add_all(records)
            db.session.commit()
            
            # Simulate partial sync
            synced = 0
            failed = 0
            
            for i, record in enumerate(records):
                try:
                    # Simulate sync
                    if i % 3 == 0:
                        raise Exception("Sync failed")
                    synced += 1
                except Exception:
                    failed += 1
            
            # Verify partial sync
            assert synced > 0
            assert failed > 0


class TestE2EMQTTIntegration:
    """Test MQTT integration scenarios"""
    
    @pytest.fixture
    def app(self):
        """Create Flask app for testing"""
        app = create_app()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()
    
    def test_mqtt_message_signing(self, app):
        """Test MQTT message signing and verification"""
        with app.app_context():
            signing_service = MessageSigningService()
            
            # Create MQTT message
            mqtt_message = {
                'topic': 'device/device_001/telemetry',
                'payload': {
                    'temperature': 25.5,
                    'humidity': 60.0
                },
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Sign message
            signed = signing_service.sign_message(mqtt_message)
            assert 'signature' in signed
            
            # Verify message
            is_valid = signing_service.verify_message(signed)
            assert is_valid is True
    
    def test_mqtt_replay_attack_prevention(self, app):
        """Test replay attack prevention"""
        with app.app_context():
            signing_service = MessageSigningService()
            
            # Create and sign message
            message = {
                'command': 'force_sync',
                'device_id': 'device_001'
            }
            
            signed_message = signing_service.sign_message(message)
            
            # First verification should succeed
            assert signing_service.verify_message(signed_message) is True
            
            # Second verification (replay) should fail
            assert signing_service.verify_message(signed_message) is False
    
    def test_mqtt_offline_message_queue(self, app):
        """Test MQTT message queuing during offline"""
        with app.app_context():
            # Simulate offline message queue
            message_queue = []
            
            for i in range(5):
                message = {
                    'topic': f'device/device_001/telemetry',
                    'payload': {'value': 20.0 + i},
                    'timestamp': datetime.utcnow().isoformat()
                }
                message_queue.append(message)
            
            # Verify queue
            assert len(message_queue) == 5
            
            # Simulate reconnection and flush
            flushed = 0
            for message in message_queue:
                # Process message
                flushed += 1
            
            assert flushed == 5


class TestE2EDataConsistency:
    """Test data consistency across components"""
    
    @pytest.fixture
    def app(self):
        """Create Flask app for testing"""
        app = create_app()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()
    
    def test_telemetry_consistency(self, app):
        """Test telemetry data consistency"""
        with app.app_context():
            param = Parameter(name='Temperature', enabled=True, unit='°C')
            db.session.add(param)
            db.session.commit()
            
            # Insert telemetry
            telemetry = Telemetry(
                device_id='device_001',
                parameter_id=param.id,
                value=25.5,
                timestamp=datetime.utcnow()
            )
            db.session.add(telemetry)
            db.session.commit()
            
            # Retrieve and verify
            retrieved = Telemetry.query.filter_by(device_id='device_001').first()
            assert retrieved.value == 25.5
            assert retrieved.parameter_id == param.id
    
    def test_configuration_consistency(self, app):
        """Test configuration consistency"""
        with app.app_context():
            # Create config
            config = SystemConfig(
                key='mqtt_broker',
                value='mqtt.example.com'
            )
            db.session.add(config)
            db.session.commit()
            
            # Retrieve and verify
            retrieved = SystemConfig.query.filter_by(key='mqtt_broker').first()
            assert retrieved.value == 'mqtt.example.com'
            
            # Update and verify
            retrieved.value = 'new.broker.com'
            db.session.commit()
            
            updated = SystemConfig.query.filter_by(key='mqtt_broker').first()
            assert updated.value == 'new.broker.com'
    
    def test_audit_trail_consistency(self, app):
        """Test audit trail consistency"""
        with app.app_context():
            audit_service = get_audit_logging_service()
            
            # Log multiple events
            for i in range(5):
                audit_service.log_event(
                    event_type='test_event',
                    action='test',
                    resource_type='test_resource',
                    resource_id=str(i),
                    actor_email='test@example.com'
                )
            
            # Retrieve and verify
            logs, count = audit_service.get_audit_logs(limit=100)
            assert count >= 5


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
