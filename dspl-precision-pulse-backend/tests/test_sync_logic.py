"""
Unit tests for Sync Logic
Tests MQTT sync, parameter sync, user sync, and desktop sync operations
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from app.models.user import User
from app.models.parameter import Parameter
from app.models import db
import json


class TestMQTTSyncService:
    """Test MQTT sync service"""
    
    def test_sync_user_create_via_mqtt(self, app):
        """Test syncing user create via MQTT"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            service = MQTTSyncService(app)
            
            data = {
                'action': 'create',
                'user': {
                    'email': 'mqtt@example.com',
                    'name': 'MQTT User',
                    'password_hash': 'hash123',
                    'account_type': 'user'
                },
                'source': 'desktop'
            }
            
            service.sync_user(data)
            
            # Verify user created
            user = User.query.filter_by(email='mqtt@example.com').first()
            assert user is not None
            assert user.name == 'MQTT User'
            assert user.role == 'user'
    
    def test_sync_user_update_via_mqtt(self, app):
        """Test syncing user update via MQTT"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            
            # Create user first
            user = User(
                email='update@example.com',
                name='Original Name',
                password_hash='hash',
                role='user'
            )
            db.session.add(user)
            db.session.commit()
            
            service = MQTTSyncService(app)
            
            data = {
                'action': 'update',
                'user': {
                    'email': 'update@example.com',
                    'name': 'Updated Name',
                    'account_type': 'admin'
                },
                'source': 'desktop'
            }
            
            service.sync_user(data)
            
            # Verify user updated
            user = User.query.filter_by(email='update@example.com').first()
            assert user.name == 'Updated Name'
            assert user.role == 'admin'
    
    def test_sync_user_delete_via_mqtt(self, app):
        """Test syncing user delete via MQTT"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            
            # Create user first
            user = User(
                email='delete@example.com',
                name='To Delete',
                password_hash='hash',
                role='user'
            )
            db.session.add(user)
            db.session.commit()
            
            service = MQTTSyncService(app)
            
            data = {
                'action': 'delete',
                'user': {
                    'email': 'delete@example.com'
                },
                'source': 'desktop'
            }
            
            service.sync_user(data)
            
            # Verify user deleted
            user = User.query.filter_by(email='delete@example.com').first()
            assert user is None
    
    def test_sync_parameter_create_via_mqtt(self, app):
        """Test syncing parameter create via MQTT"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            
            service = MQTTSyncService(app)
            
            data = {
                'action': 'create',
                'parameter': {
                    'name': 'MQTT Parameter',
                    'unit': 'unit',
                    'enabled': True,
                    'description': 'Test parameter'
                },
                'source': 'desktop'
            }
            
            service.sync_parameter(data)
            
            # Verify parameter created
            param = Parameter.query.filter_by(name='MQTT Parameter').first()
            assert param is not None
            assert param.unit == 'unit'
            assert param.enabled is True
    
    def test_sync_parameter_update_via_mqtt(self, app):
        """Test syncing parameter update via MQTT"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            
            # Create parameter first
            param = Parameter(
                name='Original Param',
                unit='C',
                enabled=True
            )
            db.session.add(param)
            db.session.commit()
            param_id = param.id
            
            service = MQTTSyncService(app)
            
            data = {
                'action': 'update',
                'parameter': {
                    'id': param_id,
                    'name': 'Updated Param',
                    'unit': 'F',
                    'enabled': False
                },
                'source': 'desktop'
            }
            
            service.sync_parameter(data)
            
            # Verify parameter updated
            param = Parameter.query.get(param_id)
            assert param.name == 'Updated Param'
            assert param.unit == 'F'
            assert param.enabled is False
    
    def test_sync_parameter_delete_via_mqtt(self, app):
        """Test syncing parameter delete via MQTT"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            
            # Create parameter first
            param = Parameter(
                name='To Delete Param',
                unit='C',
                enabled=True
            )
            db.session.add(param)
            db.session.commit()
            param_id = param.id
            
            service = MQTTSyncService(app)
            
            data = {
                'action': 'delete',
                'parameter': {
                    'id': param_id
                },
                'source': 'desktop'
            }
            
            service.sync_parameter(data)
            
            # Verify parameter deleted
            param = Parameter.query.get(param_id)
            assert param is None
    
    def test_sync_user_duplicate_email_ignored(self, app):
        """Test that duplicate user creation is ignored"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            
            # Create user first
            user = User(
                email='duplicate@example.com',
                name='Original',
                password_hash='hash',
                role='user'
            )
            db.session.add(user)
            db.session.commit()
            
            service = MQTTSyncService(app)
            
            # Try to create duplicate
            data = {
                'action': 'create',
                'user': {
                    'email': 'duplicate@example.com',
                    'name': 'Duplicate',
                    'password_hash': 'hash2',
                    'account_type': 'admin'
                },
                'source': 'desktop'
            }
            
            service.sync_user(data)
            
            # Verify original user unchanged
            user = User.query.filter_by(email='duplicate@example.com').first()
            assert user.name == 'Original'
            assert user.role == 'user'
    
    def test_sync_parameter_duplicate_name_ignored(self, app):
        """Test that duplicate parameter creation is ignored"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            
            # Create parameter first
            param = Parameter(
                name='Duplicate Param',
                unit='C',
                enabled=True
            )
            db.session.add(param)
            db.session.commit()
            
            service = MQTTSyncService(app)
            
            # Try to create duplicate
            data = {
                'action': 'create',
                'parameter': {
                    'name': 'Duplicate Param',
                    'unit': 'F',
                    'enabled': False
                },
                'source': 'desktop'
            }
            
            service.sync_parameter(data)
            
            # Verify original parameter unchanged
            param = Parameter.query.filter_by(name='Duplicate Param').first()
            assert param.unit == 'C'
            assert param.enabled is True
    
    def test_sync_user_update_nonexistent_fails(self, app):
        """Test that updating nonexistent user fails gracefully"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            
            service = MQTTSyncService(app)
            
            data = {
                'action': 'update',
                'user': {
                    'email': 'nonexistent@example.com',
                    'name': 'Updated'
                },
                'source': 'desktop'
            }
            
            # Should not raise exception
            service.sync_user(data)
            
            # Verify no user created
            user = User.query.filter_by(email='nonexistent@example.com').first()
            assert user is None
    
    def test_sync_parameter_update_nonexistent_creates(self, app):
        """Test that updating nonexistent parameter creates it"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            
            service = MQTTSyncService(app)
            
            data = {
                'action': 'update',
                'parameter': {
                    'name': 'New Param',
                    'unit': 'C',
                    'enabled': True
                },
                'source': 'desktop'
            }
            
            service.sync_parameter(data)
            
            # Verify parameter created
            param = Parameter.query.filter_by(name='New Param').first()
            assert param is not None
            assert param.unit == 'C'


class TestParameterSync:
    """Test parameter synchronization"""
    
    def test_parameter_sync_preserves_timestamps(self, app):
        """Test that parameter sync preserves timestamps"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            
            # Create parameter with specific timestamp
            now = datetime.utcnow()
            param = Parameter(
                name='Timestamp Param',
                unit='C',
                enabled=True,
                created_at=now,
                updated_at=now
            )
            db.session.add(param)
            db.session.commit()
            
            original_created = param.created_at
            original_updated = param.updated_at
            
            # Sync parameter
            service = MQTTSyncService(app)
            data = {
                'action': 'update',
                'parameter': {
                    'id': param.id,
                    'unit': 'F'
                },
                'source': 'desktop'
            }
            
            service.sync_parameter(data)
            
            # Verify timestamps updated
            param = Parameter.query.get(param.id)
            assert param.created_at == original_created
            assert param.updated_at >= original_updated
    
    def test_parameter_sync_multiple_fields(self, app):
        """Test syncing multiple parameter fields"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            
            param = Parameter(
                name='Multi Field',
                unit='C',
                description='Original',
                enabled=True
            )
            db.session.add(param)
            db.session.commit()
            param_id = param.id
            
            service = MQTTSyncService(app)
            data = {
                'action': 'update',
                'parameter': {
                    'id': param_id,
                    'name': 'Updated Multi',
                    'unit': 'F',
                    'description': 'Updated',
                    'enabled': False
                },
                'source': 'desktop'
            }
            
            service.sync_parameter(data)
            
            param = Parameter.query.get(param_id)
            assert param.name == 'Updated Multi'
            assert param.unit == 'F'
            assert param.description == 'Updated'
            assert param.enabled is False
    
    def test_parameter_sync_partial_update(self, app):
        """Test syncing only some parameter fields"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            
            param = Parameter(
                name='Partial Update',
                unit='C',
                description='Original',
                enabled=True
            )
            db.session.add(param)
            db.session.commit()
            param_id = param.id
            
            service = MQTTSyncService(app)
            data = {
                'action': 'update',
                'parameter': {
                    'id': param_id,
                    'unit': 'F'
                },
                'source': 'desktop'
            }
            
            service.sync_parameter(data)
            
            param = Parameter.query.get(param_id)
            assert param.name == 'Partial Update'  # Unchanged
            assert param.unit == 'F'  # Changed
            assert param.description == 'Original'  # Unchanged
            assert param.enabled is True  # Unchanged


class TestUserSync:
    """Test user synchronization"""
    
    def test_user_sync_preserves_timestamps(self, app):
        """Test that user sync preserves timestamps"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            
            now = datetime.utcnow()
            user = User(
                email='timestamp@example.com',
                name='Timestamp User',
                password_hash='hash',
                role='user',
                created_at=now,
                updated_at=now
            )
            db.session.add(user)
            db.session.commit()
            
            original_created = user.created_at
            original_updated = user.updated_at
            
            service = MQTTSyncService(app)
            data = {
                'action': 'update',
                'user': {
                    'email': 'timestamp@example.com',
                    'name': 'Updated Name'
                },
                'source': 'desktop'
            }
            
            service.sync_user(data)
            
            user = User.query.filter_by(email='timestamp@example.com').first()
            assert user.created_at == original_created
            assert user.updated_at >= original_updated
    
    def test_user_sync_multiple_fields(self, app):
        """Test syncing multiple user fields"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            
            user = User(
                email='multi@example.com',
                name='Original Name',
                password_hash='hash',
                role='user',
                is_active=True
            )
            db.session.add(user)
            db.session.commit()
            
            service = MQTTSyncService(app)
            data = {
                'action': 'update',
                'user': {
                    'email': 'multi@example.com',
                    'name': 'Updated Name',
                    'account_type': 'admin',
                    'is_active': False
                },
                'source': 'desktop'
            }
            
            service.sync_user(data)
            
            user = User.query.filter_by(email='multi@example.com').first()
            assert user.name == 'Updated Name'
            assert user.role == 'admin'
            assert user.is_active is False
    
    def test_user_sync_partial_update(self, app):
        """Test syncing only some user fields"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            
            user = User(
                email='partial@example.com',
                name='Original Name',
                password_hash='hash',
                role='user',
                is_active=True
            )
            db.session.add(user)
            db.session.commit()
            
            service = MQTTSyncService(app)
            data = {
                'action': 'update',
                'user': {
                    'email': 'partial@example.com',
                    'name': 'Updated Name'
                },
                'source': 'desktop'
            }
            
            service.sync_user(data)
            
            user = User.query.filter_by(email='partial@example.com').first()
            assert user.name == 'Updated Name'
            assert user.role == 'user'  # Unchanged
            assert user.is_active is True  # Unchanged


class TestSyncErrorHandling:
    """Test sync error handling"""
    
    def test_sync_user_missing_email_fails(self, app):
        """Test that syncing user without email fails gracefully"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            
            service = MQTTSyncService(app)
            
            data = {
                'action': 'create',
                'user': {
                    'name': 'No Email',
                    'password_hash': 'hash'
                },
                'source': 'desktop'
            }
            
            # Should not raise exception
            service.sync_user(data)
    
    def test_sync_parameter_missing_name_fails(self, app):
        """Test that syncing parameter without name fails gracefully"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            
            service = MQTTSyncService(app)
            
            data = {
                'action': 'create',
                'parameter': {
                    'unit': 'C'
                },
                'source': 'desktop'
            }
            
            # Should not raise exception
            service.sync_parameter(data)
    
    def test_sync_invalid_action_ignored(self, app):
        """Test that invalid sync action is ignored"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            
            service = MQTTSyncService(app)
            
            data = {
                'action': 'invalid_action',
                'user': {
                    'email': 'test@example.com',
                    'name': 'Test'
                },
                'source': 'desktop'
            }
            
            # Should not raise exception
            service.sync_user(data)
    
    def test_sync_missing_data_ignored(self, app):
        """Test that sync with missing data is ignored"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            
            service = MQTTSyncService(app)
            
            data = {
                'action': 'update',
                'source': 'desktop'
            }
            
            # Should not raise exception
            service.sync_user(data)


class TestSyncDataIntegrity:
    """Test sync data integrity"""
    
    def test_sync_maintains_referential_integrity(self, app):
        """Test that sync maintains referential integrity"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            
            # Create user
            user = User(
                email='integrity@example.com',
                name='Integrity Test',
                password_hash='hash',
                role='user'
            )
            db.session.add(user)
            db.session.commit()
            user_id = user.id
            
            # Sync user update
            service = MQTTSyncService(app)
            data = {
                'action': 'update',
                'user': {
                    'email': 'integrity@example.com',
                    'name': 'Updated'
                },
                'source': 'desktop'
            }
            
            service.sync_user(data)
            
            # Verify user ID unchanged
            user = User.query.get(user_id)
            assert user.id == user_id
            assert user.name == 'Updated'
    
    def test_sync_concurrent_updates_last_wins(self, app):
        """Test that concurrent updates follow last-write-wins"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            
            user = User(
                email='concurrent@example.com',
                name='Original',
                password_hash='hash',
                role='user'
            )
            db.session.add(user)
            db.session.commit()
            
            service = MQTTSyncService(app)
            
            # First update
            data1 = {
                'action': 'update',
                'user': {
                    'email': 'concurrent@example.com',
                    'name': 'Update 1'
                },
                'source': 'desktop'
            }
            service.sync_user(data1)
            
            # Second update
            data2 = {
                'action': 'update',
                'user': {
                    'email': 'concurrent@example.com',
                    'name': 'Update 2'
                },
                'source': 'desktop'
            }
            service.sync_user(data2)
            
            # Verify last update wins
            user = User.query.filter_by(email='concurrent@example.com').first()
            assert user.name == 'Update 2'
    
    def test_sync_preserves_data_types(self, app):
        """Test that sync preserves data types"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            
            param = Parameter(
                name='Type Test',
                unit='C',
                enabled=True
            )
            db.session.add(param)
            db.session.commit()
            param_id = param.id
            
            service = MQTTSyncService(app)
            data = {
                'action': 'update',
                'parameter': {
                    'id': param_id,
                    'enabled': False
                },
                'source': 'desktop'
            }
            
            service.sync_parameter(data)
            
            param = Parameter.query.get(param_id)
            assert isinstance(param.enabled, bool)
            assert param.enabled is False


class TestSyncBatchOperations:
    """Test batch sync operations"""
    
    def test_sync_multiple_users(self, app):
        """Test syncing multiple users"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            
            service = MQTTSyncService(app)
            
            for i in range(3):
                data = {
                    'action': 'create',
                    'user': {
                        'email': f'batch{i}@example.com',
                        'name': f'Batch User {i}',
                        'password_hash': 'hash',
                        'account_type': 'user'
                    },
                    'source': 'desktop'
                }
                service.sync_user(data)
            
            # Verify all users created
            users = User.query.filter(User.email.like('batch%@example.com')).all()
            assert len(users) == 3
    
    def test_sync_multiple_parameters(self, app):
        """Test syncing multiple parameters"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            
            service = MQTTSyncService(app)
            
            for i in range(3):
                data = {
                    'action': 'create',
                    'parameter': {
                        'name': f'Batch Param {i}',
                        'unit': 'unit',
                        'enabled': True
                    },
                    'source': 'desktop'
                }
                service.sync_parameter(data)
            
            # Verify all parameters created
            params = Parameter.query.filter(Parameter.name.like('Batch Param%')).all()
            assert len(params) == 3
    
    def test_sync_mixed_operations(self, app):
        """Test syncing mixed create/update/delete operations"""
        with app.app_context():
            from app.services.mqtt_sync_service import MQTTSyncService
            
            service = MQTTSyncService(app)
            
            # Create
            data = {
                'action': 'create',
                'user': {
                    'email': 'mixed@example.com',
                    'name': 'Mixed',
                    'password_hash': 'hash',
                    'account_type': 'user'
                },
                'source': 'desktop'
            }
            service.sync_user(data)
            
            # Update
            data = {
                'action': 'update',
                'user': {
                    'email': 'mixed@example.com',
                    'name': 'Mixed Updated'
                },
                'source': 'desktop'
            }
            service.sync_user(data)
            
            # Delete
            data = {
                'action': 'delete',
                'user': {
                    'email': 'mixed@example.com'
                },
                'source': 'desktop'
            }
            service.sync_user(data)
            
            # Verify final state
            user = User.query.filter_by(email='mixed@example.com').first()
            assert user is None
