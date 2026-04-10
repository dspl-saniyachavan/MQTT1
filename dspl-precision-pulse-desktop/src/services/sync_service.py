import json
from datetime import datetime
from PySide6.QtCore import QObject, Signal


class SyncService(QObject):
    """Handles automatic bidirectional sync via MQTT"""
    
    user_synced = Signal(dict)
    config_synced = Signal(dict)
    parameter_synced = Signal(dict)
    
    def __init__(self, mqtt_service, db_manager):
        super().__init__()
        self.mqtt = mqtt_service
        self.db = db_manager
        
        # Connect MQTT signals
        self.mqtt.connected.connect(self._on_connected)
        self.mqtt.message_received.connect(self._handle_message)
    
    def _on_connected(self):
        """Subscribe to sync topics on connection"""
        self.mqtt.client.subscribe("precisionpulse/sync/users/#")
        self.mqtt.client.subscribe("precisionpulse/sync/config")
        self.mqtt.client.subscribe("precisionpulse/sync/parameters")
        print(" Subscribed to sync topics")
    
    def _handle_message(self, topic, payload):
        """Route sync messages to appropriate handlers"""
        try:
            if "users" in topic:
                self._sync_user(payload)
            elif "config" in topic:
                self._sync_config(payload)
            elif "parameters" in topic:
                self._sync_parameter(payload)
        except Exception as e:
            print(f"Sync error: {e}")
    
    def _sync_user(self, data):
        """Sync user from remote"""
        action = data.get('action')
        user = data.get('user')
        source = data.get('source', 'unknown')
        
        if source == 'desktop':
            return  # Ignore our own messages
        
        import sqlite3
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            
            if action == 'create':
                cursor.execute('''
                    INSERT OR IGNORE INTO users (email, name, password_hash, role, is_active)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user['email'], user['name'], user['password_hash'], 
                      user['account_type'], user['is_active']))
                print(f"Synced user create: {user['email']}")
                
            elif action == 'update':
                cursor.execute('''
                    UPDATE users SET name=?, role=?, is_active=?, updated_at=CURRENT_TIMESTAMP
                    WHERE email=?
                ''', (user['name'], user['account_type'], user['is_active'], user['email']))
                print(f"Synced user update: {user['email']}")
                
            elif action == 'delete':
                cursor.execute('DELETE FROM users WHERE email=?', (user['email'],))
                print(f"Synced user delete: {user['email']}")
            
            conn.commit()
            self.user_synced.emit(user)
    
    def _sync_config(self, data):
        """Sync config from remote"""
        config = data.get('config', {})
        
        import sqlite3
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            for key, value in config.items():
                cursor.execute('''
                    INSERT OR REPLACE INTO config (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                ''', (key, str(value)))
            conn.commit()
        
        print(f"Synced config: {list(config.keys())}")
        self.config_synced.emit(config)
    
    def _sync_parameter(self, data):
        """Sync parameter from remote"""
        action = data.get('action', 'update')
        param = data.get('parameter')
        source = data.get('source', 'unknown')
        device_id = data.get('device_id', '')
        
        # Ignore our own messages
        if source == 'desktop' and device_id == self.mqtt.device_id:
            return
        
        print(f" Received parameter sync: {action} - {param.get('name', param.get('id', 'unknown'))}")
        
        # Save to local SQLite database
        import sqlite3
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            
            if action == 'delete':
                cursor.execute('DELETE FROM parameters WHERE id = ?', (param.get('id'),))
                print(f" Deleted parameter from SQLite: {param.get('id')}")
            else:
                cursor.execute('''
                    INSERT OR REPLACE INTO parameters (id, name, unit, enabled, description)
                    VALUES (?, ?, ?, ?, ?)
                ''', (param.get('id'), param.get('name'), param.get('unit'), 
                      param.get('enabled', True), param.get('description', '')))
                print(f" Synced parameter to SQLite: {param.get('name')}")
            
            conn.commit()
        
        # Emit signal to refresh UI
        self.parameter_synced.emit(param.copy())
    
    def publish_user_change(self, action, user):
        """Publish user change to MQTT"""
        if not self.mqtt.is_connected:
            print(" MQTT not connected, cannot publish user change")
            return
        
        payload = {
            'action': action,
            'user': {
                'email': user['email'],
                'name': user['name'],
                'password_hash': user.get('password_hash', ''),
                'account_type': user.get('role', 'user'),
                'is_active': user.get('is_active', True)
            },
            'source': 'desktop',
            'timestamp': datetime.now().isoformat() + 'Z'
        }
        
        self.mqtt.client.publish(
            f"precisionpulse/sync/users/{action}",
            json.dumps(payload),
            qos=1
        )
        print(f" Published user {action}: {user['email']}")
    
    def publish_parameter_change(self, parameter, action='update'):
        """Publish parameter change to MQTT"""
        if not self.mqtt.is_connected:
            print(" MQTT not connected, cannot publish parameter change")
            return
        
        payload = {
            'action': action,
            'parameter': parameter,
            'source': 'desktop',
            'device_id': self.mqtt.device_id,
            'timestamp': datetime.now().isoformat() + 'Z'
        }
        
        self.mqtt.client.publish(
            "precisionpulse/sync/parameters",
            json.dumps(payload),
            qos=1
        )
        print(f" Published parameter {action}: {parameter.get('name', parameter.get('id'))}")
