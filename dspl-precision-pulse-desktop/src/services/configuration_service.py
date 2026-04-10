"""
Configuration management service for desktop application
Handles fetching, caching, and applying configuration changes
"""

import json
import threading
import time
from datetime import datetime
from typing import Dict, Optional, Any
from src.core.database import DatabaseManager
from src.core.auth_service import AuthService
from PySide6.QtCore import QObject, Signal

class ConfigurationService(QObject):
    """Service for managing system configuration"""

    config_changed = Signal(str, str)  # key, new_value — emitted on every live update
    
    def __init__(self, db: DatabaseManager, auth_service: AuthService):
        super().__init__()
        self.db = db
        self.auth_service = auth_service
        self.backend_url = "http://localhost:5000"
        self.local_config = {}
        self.config_version = 0
        self.last_sync = None
        self.sync_interval = 30  # Sync every 30 seconds
        self.is_syncing = False
        self.config_callbacks = {}  # Callbacks for config changes
        
    def register_callback(self, key: str, callback):
        """Register a callback for when a specific config changes"""
        if key not in self.config_callbacks:
            self.config_callbacks[key] = []
        self.config_callbacks[key].append(callback)
        print(f"[CONFIG] Registered callback for {key}")
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key"""
        if key in self.local_config:
            config = self.local_config[key]
            return self._convert_value(config.get('value'), config.get('data_type'))
        return default
    
    def get_all_configs(self) -> Dict[str, Any]:
        """Get all configurations"""
        return self.local_config
    
    def get_config_version(self) -> int:
        """Get current configuration version"""
        return self.config_version
    
    def _convert_value(self, value: str, data_type: str) -> Any:
        """Convert string value to proper type"""
        if data_type == 'integer':
            try:
                return int(value)
            except (ValueError, TypeError):
                return value
        elif data_type == 'boolean':
            return value.lower() in ('true', '1', 'yes')
        elif data_type == 'json':
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return value
    
    def sync_configurations(self) -> bool:
        """No-op: config arrives via MQTT (config_update / config_bulk_update topics).
        Initial values are loaded from SQLite by load_local_configs().
        """
        return True
    
    def _process_config_update(self, configs: list, new_version: int):
        """Process configuration update and trigger callbacks"""
        old_config = self.local_config.copy()
        self.local_config = {}
        
        for config in configs:
            key = config.get('key')
            self.local_config[key] = config
        
        self.config_version = new_version
        self.last_sync = datetime.now()
        
        # Store in local database
        self._store_configs_locally()
        
        # Trigger callbacks for changed configs
        self._trigger_callbacks(old_config)
        
        print(f"[CONFIG] Configuration synced successfully (v{new_version})")
    
    def _store_configs_locally(self):
        """Store configurations in local SQLite database"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Ensure config table has all required columns
                try:
                    cursor.execute('PRAGMA table_info(config)')
                    columns = {row[1] for row in cursor.fetchall()}
                    
                    # Add missing columns if needed
                    if 'category' not in columns:
                        cursor.execute('ALTER TABLE config ADD COLUMN category TEXT DEFAULT "general"')
                    if 'data_type' not in columns:
                        cursor.execute('ALTER TABLE config ADD COLUMN data_type TEXT DEFAULT "string"')
                    if 'version' not in columns:
                        cursor.execute('ALTER TABLE config ADD COLUMN version INTEGER DEFAULT 1')
                    if 'created_at' not in columns:
                        cursor.execute('ALTER TABLE config ADD COLUMN created_at TIMESTAMP DEFAULT (datetime("now", "localtime"))')
                    if 'updated_at' not in columns:
                        cursor.execute('ALTER TABLE config ADD COLUMN updated_at TIMESTAMP DEFAULT (datetime("now", "localtime"))')
                    if 'updated_by' not in columns:
                        cursor.execute('ALTER TABLE config ADD COLUMN updated_by TEXT')
                    
                    conn.commit()
                except Exception as e:
                    print(f"[CONFIG] Warning: Could not update table schema: {e}")
                
                # Clear and insert new configs
                cursor.execute('DELETE FROM config')
                
                for key, config in self.local_config.items():
                    cursor.execute('''
                        INSERT INTO config (key, value, category, data_type, version, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        key,
                        config.get('value'),
                        config.get('category', 'general'),
                        config.get('data_type', 'string'),
                        config.get('version', 1),
                        config.get('updated_at')
                    ))
                
                conn.commit()
                print(f"[CONFIG] Stored {len(self.local_config)} configurations locally")
                
        except Exception as e:
            print(f"[CONFIG] Error storing configurations locally: {e}")
    
    def _trigger_callbacks(self, old_config: Dict):
        """Trigger callbacks for changed configurations"""
        for key, callbacks in self.config_callbacks.items():
            old_value = old_config.get(key, {}).get('value')
            new_value = self.local_config.get(key, {}).get('value')
            
            if old_value != new_value:
                print(f"[CONFIG] Configuration changed: {key}")
                for callback in callbacks:
                    try:
                        callback(key, new_value, old_value)
                    except Exception as e:
                        print(f"[CONFIG] Error in callback for {key}: {e}")
    
    def load_local_configs(self) -> bool:
        """Load configurations from local database"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Ensure config table exists and has correct schema
                try:
                    cursor.execute('PRAGMA table_info(config)')
                    columns = {row[1] for row in cursor.fetchall()}
                    
                    # Add missing columns if needed
                    if 'category' not in columns:
                        cursor.execute('ALTER TABLE config ADD COLUMN category TEXT DEFAULT "general"')
                    if 'data_type' not in columns:
                        cursor.execute('ALTER TABLE config ADD COLUMN data_type TEXT DEFAULT "string"')
                    if 'version' not in columns:
                        cursor.execute('ALTER TABLE config ADD COLUMN version INTEGER DEFAULT 1')
                    if 'created_at' not in columns:
                        cursor.execute('ALTER TABLE config ADD COLUMN created_at TIMESTAMP DEFAULT (datetime("now", "localtime"))')
                    if 'updated_at' not in columns:
                        cursor.execute('ALTER TABLE config ADD COLUMN updated_at TIMESTAMP DEFAULT (datetime("now", "localtime"))')
                    if 'updated_by' not in columns:
                        cursor.execute('ALTER TABLE config ADD COLUMN updated_by TEXT')
                    
                    conn.commit()
                except Exception as e:
                    print(f"[CONFIG] Warning: Could not update table schema: {e}")
                
                cursor.execute('SELECT key, value, category, data_type, version, updated_at FROM config')
                rows = cursor.fetchall()
                
                if not rows:
                    print("[CONFIG] No local configurations found")
                    return False
                
                self.local_config = {}
                for row in rows:
                    key = row[0]
                    self.local_config[key] = {
                        'key': key,
                        'value': row[1],
                        'category': row[2] or 'general',
                        'data_type': row[3] or 'string',
                        'version': row[4] or 1,
                        'updated_at': row[5]
                    }

                # Restore config_version so sync_configurations() version guard works correctly
                max_ver = max((r[4] or 1 for r in rows), default=1)
                self.config_version = max_ver

                print(f"[CONFIG] Loaded {len(self.local_config)} configurations from local database (v{self.config_version})")

                # Fire callbacks so services (telemetry interval, chart points, etc.) pick up
                # persisted values immediately after login without waiting for a backend sync
                self._fire_all_callbacks()

                return True
                
        except Exception as e:
            print(f"[CONFIG] Error loading local configurations: {e}")
            return False
    
    def _fire_all_callbacks(self):
        """Fire callbacks for every registered key using the current local_config value.
        Called after load_local_configs so services apply persisted values on login.
        """
        for key, callbacks in self.config_callbacks.items():
            if key in self.local_config:
                value = self.local_config[key].get('value')
                for callback in callbacks:
                    try:
                        callback(key, value, None)
                    except Exception as e:
                        print(f"[CONFIG] Error in startup callback for {key}: {e}")

    def start_sync_thread(self):
        """Start background thread for periodic configuration sync"""
        def sync_loop():
            print("[CONFIG] Configuration sync thread started")
            # Initial sync after 3 seconds
            import time
            time.sleep(3)
            self.sync_configurations()
            while True:
                try:
                    time.sleep(self.sync_interval)
                    self.sync_configurations()
                except Exception as e:
                    print(f"[CONFIG] Error in sync loop: {e}")

        sync_thread = threading.Thread(target=sync_loop, daemon=True)
        sync_thread.start()
        print("[CONFIG] Configuration sync thread started")
    
    def apply_config_change(self, key: str, value: Any, old_value: Any = None):
        """Apply a configuration change locally, persist to SQLite, and fire registered callbacks."""
        if old_value is None and key in self.local_config:
            old_value = self.local_config[key].get('value')

        # Update in-memory store
        if key in self.local_config:
            self.local_config[key]['value'] = str(value)
        else:
            self.local_config[key] = {'key': key, 'value': str(value), 'data_type': 'string', 'category': 'general', 'version': 1}

        # Persist to SQLite so the value survives logout/login
        try:
            import sqlite3
            conn = sqlite3.connect(self.db.db_path)
            conn.execute('''
                INSERT INTO config (key, value, category, data_type, version, updated_at)
                VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))
                ON CONFLICT(key) DO UPDATE SET
                    value      = excluded.value,
                    updated_at = excluded.updated_at
            ''', (
                key,
                str(value),
                self.local_config[key].get('category', 'general'),
                self.local_config[key].get('data_type', 'string'),
                self.local_config[key].get('version', 1),
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[CONFIG] Error persisting {key} to SQLite: {e}")

        if key in self.config_callbacks:
            for callback in self.config_callbacks[key]:
                try:
                    callback(key, value, old_value)
                except Exception as e:
                    print(f"[CONFIG] Error in callback for {key}: {e}")

        # Notify UI components listening to the signal
        try:
            self.config_changed.emit(str(key), str(value))
        except Exception:
            pass

        print(f"[CONFIG] Applied+persisted: {key} = {value} (was {old_value})")
    
    def get_connection(self):
        """Get database connection"""
        import sqlite3
        return sqlite3.connect(self.db.db_path)
