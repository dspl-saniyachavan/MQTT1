"""
Unit tests for user, role, and permission MQTT synchronization
"""

import unittest
import json
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestMQTTPublisher(unittest.TestCase):
    """Test MQTT publisher for user/role/permission changes"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_client = Mock()
        self.mock_client.publish = Mock(return_value=Mock(rc=0))
    
    @patch('app.services.mqtt_publisher.mqtt.Client')
    @patch('app.services.mqtt_publisher.Config')
    def test_publish_user_created(self, mock_config, mock_mqtt_client):
        """Test publishing user creation event"""
        from app.services.mqtt_publisher import MQTTPublisher
        
        mock_config.MQTT_BROKER = 'localhost'
        mock_config.MQTT_PORT = 18883
        mock_config.MQTT_USE_TLS = True
        mock_config.MQTT_CA_CERTS = 'config/ca.crt'
        mock_config.MQTT_KEEPALIVE = 60
        
        mock_mqtt_client.return_value = self.mock_client
        publisher = MQTTPublisher()
        publisher.connected = True  # Simulate connected state
        
        user_data = {
            'id': 1,
            'email': 'test@example.com',
            'name': 'Test User',
            'role': 'user',
            'is_active': True
        }
        
        publisher.publish_user_created(user_data)
        
        # Verify publish was called
        self.mock_client.publish.assert_called()
        call_args = self.mock_client.publish.call_args
        topic = call_args[0][0]
        payload = json.loads(call_args[0][1])
        
        self.assertEqual(topic, 'precisionpulse/sync/users/created')
        self.assertEqual(payload['type'], 'user_created')
        self.assertEqual(payload['user']['email'], 'test@example.com')
    
    @patch('app.services.mqtt_publisher.mqtt.Client')
    @patch('app.services.mqtt_publisher.Config')
    def test_publish_user_updated(self, mock_config, mock_mqtt_client):
        """Test publishing user update event"""
        from app.services.mqtt_publisher import MQTTPublisher
        
        mock_config.MQTT_BROKER = 'localhost'
        mock_config.MQTT_PORT = 18883
        mock_config.MQTT_USE_TLS = True
        mock_config.MQTT_CA_CERTS = 'config/ca.crt'
        mock_config.MQTT_KEEPALIVE = 60
        
        mock_mqtt_client.return_value = self.mock_client
        publisher = MQTTPublisher()
        publisher.connected = True  # Simulate connected state
        
        user_data = {
            'id': 1,
            'email': 'test@example.com',
            'name': 'Updated User',
            'role': 'admin',
            'is_active': True
        }
        
        publisher.publish_user_updated(user_data)
        
        call_args = self.mock_client.publish.call_args
        topic = call_args[0][0]
        payload = json.loads(call_args[0][1])
        
        self.assertEqual(topic, 'precisionpulse/sync/users/updated')
        self.assertEqual(payload['type'], 'user_updated')
        self.assertEqual(payload['user']['role'], 'admin')
    
    @patch('app.services.mqtt_publisher.mqtt.Client')
    @patch('app.services.mqtt_publisher.Config')
    def test_publish_user_deleted(self, mock_config, mock_mqtt_client):
        """Test publishing user deletion event"""
        from app.services.mqtt_publisher import MQTTPublisher
        
        mock_config.MQTT_BROKER = 'localhost'
        mock_config.MQTT_PORT = 18883
        mock_config.MQTT_USE_TLS = True
        mock_config.MQTT_CA_CERTS = 'config/ca.crt'
        mock_config.MQTT_KEEPALIVE = 60
        
        mock_mqtt_client.return_value = self.mock_client
        publisher = MQTTPublisher()
        publisher.connected = True  # Simulate connected state
        
        publisher.publish_user_deleted(1, 'test@example.com')
        
        call_args = self.mock_client.publish.call_args
        topic = call_args[0][0]
        payload = json.loads(call_args[0][1])
        
        self.assertEqual(topic, 'precisionpulse/sync/users/deleted')
        self.assertEqual(payload['type'], 'user_deleted')
        self.assertEqual(payload['user']['id'], 1)
    
    @patch('app.services.mqtt_publisher.mqtt.Client')
    @patch('app.services.mqtt_publisher.Config')
    def test_publish_role_changed(self, mock_config, mock_mqtt_client):
        """Test publishing role change event"""
        from app.services.mqtt_publisher import MQTTPublisher
        
        mock_config.MQTT_BROKER = 'localhost'
        mock_config.MQTT_PORT = 18883
        mock_config.MQTT_USE_TLS = True
        mock_config.MQTT_CA_CERTS = 'config/ca.crt'
        mock_config.MQTT_KEEPALIVE = 60
        
        mock_mqtt_client.return_value = self.mock_client
        publisher = MQTTPublisher()
        publisher.connected = True  # Simulate connected state
        
        publisher.publish_role_changed(1, 'test@example.com', 'user', 'admin')
        
        call_args = self.mock_client.publish.call_args
        topic = call_args[0][0]
        payload = json.loads(call_args[0][1])
        
        self.assertEqual(topic, 'precisionpulse/sync/roles/changed')
        self.assertEqual(payload['type'], 'role_changed')
        self.assertEqual(payload['old_role'], 'user')
        self.assertEqual(payload['new_role'], 'admin')
    
    @patch('app.services.mqtt_publisher.mqtt.Client')
    @patch('app.services.mqtt_publisher.Config')
    def test_publish_permission_changed(self, mock_config, mock_mqtt_client):
        """Test publishing permission change event"""
        from app.services.mqtt_publisher import MQTTPublisher
        
        mock_config.MQTT_BROKER = 'localhost'
        mock_config.MQTT_PORT = 18883
        mock_config.MQTT_USE_TLS = True
        mock_config.MQTT_CA_CERTS = 'config/ca.crt'
        mock_config.MQTT_KEEPALIVE = 60
        
        mock_mqtt_client.return_value = self.mock_client
        publisher = MQTTPublisher()
        publisher.connected = True  # Simulate connected state
        
        permissions = ['user.read', 'user.create', 'user.update']
        publisher.publish_permission_changed('admin', permissions)
        
        call_args = self.mock_client.publish.call_args
        topic = call_args[0][0]
        payload = json.loads(call_args[0][1])
        
        self.assertEqual(topic, 'precisionpulse/sync/permissions/changed')
        self.assertEqual(payload['type'], 'permission_changed')
        self.assertEqual(payload['role'], 'admin')
        self.assertEqual(payload['permissions'], permissions)


class TestUserSyncService(unittest.TestCase):
    """Test user sync service for desktop"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_mqtt = Mock()
        self.mock_mqtt.message_received = Mock()
    
    def test_user_created_signal(self):
        """Test user created signal emission"""
        # Import from desktop path
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../dspl-precision-pulse-desktop'))
        from src.services.user_sync_service import UserSyncService
        
        service = UserSyncService(self.mock_mqtt)
        signal_emitted = False
        received_user = None
        
        def on_user_created(user):
            nonlocal signal_emitted, received_user
            signal_emitted = True
            received_user = user
        
        service.user_created.connect(on_user_created)
        
        user_data = {
            'id': 1,
            'email': 'test@example.com',
            'name': 'Test User',
            'role': 'user'
        }
        
        payload = {
            'type': 'user_created',
            'user': user_data
        }
        
        service._on_mqtt_message('precisionpulse/sync/users/created', payload)
        
        self.assertTrue(signal_emitted)
        self.assertEqual(received_user['email'], 'test@example.com')
        self.assertEqual(len(service.users), 1)
    
    def test_user_updated_signal(self):
        """Test user updated signal emission"""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../dspl-precision-pulse-desktop'))
        from src.services.user_sync_service import UserSyncService
        
        service = UserSyncService(self.mock_mqtt)
        service.users = [{'id': 1, 'email': 'test@example.com', 'name': 'Old Name', 'role': 'user'}]
        
        signal_emitted = False
        received_user = None
        
        def on_user_updated(user):
            nonlocal signal_emitted, received_user
            signal_emitted = True
            received_user = user
        
        service.user_updated.connect(on_user_updated)
        
        user_data = {
            'id': 1,
            'email': 'test@example.com',
            'name': 'New Name',
            'role': 'user'
        }
        
        payload = {
            'type': 'user_updated',
            'user': user_data
        }
        
        service._on_mqtt_message('precisionpulse/sync/users/updated', payload)
        
        self.assertTrue(signal_emitted)
        self.assertEqual(received_user['name'], 'New Name')
        self.assertEqual(service.users[0]['name'], 'New Name')
    
    def test_user_deleted_signal(self):
        """Test user deleted signal emission"""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../dspl-precision-pulse-desktop'))
        from src.services.user_sync_service import UserSyncService
        
        service = UserSyncService(self.mock_mqtt)
        service.users = [{'id': 1, 'email': 'test@example.com', 'name': 'Test User', 'role': 'user'}]
        
        signal_emitted = False
        received_id = None
        received_email = None
        
        def on_user_deleted(user_id, email):
            nonlocal signal_emitted, received_id, received_email
            signal_emitted = True
            received_id = user_id
            received_email = email
        
        service.user_deleted.connect(on_user_deleted)
        
        payload = {
            'type': 'user_deleted',
            'user': {'id': 1, 'email': 'test@example.com'}
        }
        
        service._on_mqtt_message('precisionpulse/sync/users/deleted', payload)
        
        self.assertTrue(signal_emitted)
        self.assertEqual(received_id, 1)
        self.assertEqual(received_email, 'test@example.com')
        self.assertEqual(len(service.users), 0)
    
    def test_role_changed_signal(self):
        """Test role changed signal emission"""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../dspl-precision-pulse-desktop'))
        from src.services.user_sync_service import UserSyncService
        
        service = UserSyncService(self.mock_mqtt)
        service.users = [{'id': 1, 'email': 'test@example.com', 'name': 'Test User', 'role': 'user'}]
        
        signal_emitted = False
        received_data = None
        
        def on_role_changed(user_id, email, old_role, new_role):
            nonlocal signal_emitted, received_data
            signal_emitted = True
            received_data = (user_id, email, old_role, new_role)
        
        service.role_changed.connect(on_role_changed)
        
        payload = {
            'type': 'role_changed',
            'user_id': 1,
            'email': 'test@example.com',
            'old_role': 'user',
            'new_role': 'admin'
        }
        
        service._on_mqtt_message('precisionpulse/sync/roles/changed', payload)
        
        self.assertTrue(signal_emitted)
        self.assertEqual(received_data[2], 'user')
        self.assertEqual(received_data[3], 'admin')
        self.assertEqual(service.users[0]['role'], 'admin')
    
    def test_permission_changed_signal(self):
        """Test permission changed signal emission"""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../dspl-precision-pulse-desktop'))
        from src.services.user_sync_service import UserSyncService
        
        service = UserSyncService(self.mock_mqtt)
        
        signal_emitted = False
        received_data = None
        
        def on_permission_changed(role, permissions):
            nonlocal signal_emitted, received_data
            signal_emitted = True
            received_data = (role, permissions)
        
        service.permission_changed.connect(on_permission_changed)
        
        permissions = ['user.read', 'user.create', 'user.update', 'user.delete']
        payload = {
            'type': 'permission_changed',
            'role': 'admin',
            'permissions': permissions
        }
        
        service._on_mqtt_message('precisionpulse/sync/permissions/changed', payload)
        
        self.assertTrue(signal_emitted)
        self.assertEqual(received_data[0], 'admin')
        self.assertEqual(len(received_data[1]), 4)
    
    def test_get_user_by_id(self):
        """Test retrieving user by ID"""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../dspl-precision-pulse-desktop'))
        from src.services.user_sync_service import UserSyncService
        
        service = UserSyncService(self.mock_mqtt)
        service.users = [
            {'id': 1, 'email': 'user1@example.com', 'name': 'User 1', 'role': 'user'},
            {'id': 2, 'email': 'user2@example.com', 'name': 'User 2', 'role': 'admin'}
        ]
        
        user = service.get_user_by_id(1)
        self.assertIsNotNone(user)
        self.assertEqual(user['email'], 'user1@example.com')
    
    def test_get_user_by_email(self):
        """Test retrieving user by email"""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../dspl-precision-pulse-desktop'))
        from src.services.user_sync_service import UserSyncService
        
        service = UserSyncService(self.mock_mqtt)
        service.users = [
            {'id': 1, 'email': 'user1@example.com', 'name': 'User 1', 'role': 'user'},
            {'id': 2, 'email': 'user2@example.com', 'name': 'User 2', 'role': 'admin'}
        ]
        
        user = service.get_user_by_email('user2@example.com')
        self.assertIsNotNone(user)
        self.assertEqual(user['id'], 2)


if __name__ == '__main__':
    unittest.main()
