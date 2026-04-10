"""
Config synchronization service for desktop application
Handles config changes from backend via MQTT
"""

from typing import Dict
from PySide6.QtCore import QObject, Signal
import logging

logger = logging.getLogger(__name__)


class ConfigSyncService(QObject):
    """Service for syncing config changes from backend via MQTT"""
    
    config_updated = Signal(dict)
    config_error = Signal(str)
    
    def __init__(self, mqtt_service=None, database_manager=None):
        super().__init__()
        self.mqtt_service = mqtt_service
        self.database_manager = database_manager
        self.config_cache = {}
        
        # Connect to MQTT message signals
        if mqtt_service:
            mqtt_service.message_received.connect(self._on_mqtt_message)
    
    def _on_mqtt_message(self, topic: str, payload: dict):
        """Handle MQTT config sync messages"""
        try:
            msg_type = payload.get('type')
            
            if 'sync/config' in topic or msg_type == 'config_updated':
                config_data = payload.get('config', {})
                logger.info(f"[CONFIG_SYNC] Config updated: {config_data.get('key')}")
                
                # Update local cache
                self.config_cache.update(config_data)
                
                # Sync to local database
                if self.database_manager:
                    self._sync_config_to_db(config_data)
                
                self.config_updated.emit(config_data)
        
        except Exception as e:
            error = f"Error processing config sync message: {str(e)}"
            logger.error(f"[CONFIG_SYNC] {error}")
            self.config_error.emit(error)
    
    def _sync_config_to_db(self, config_data: Dict) -> bool:
        """Sync config to local SQLite config table"""
        try:
            import sqlite3
            with sqlite3.connect(self.database_manager.db_path) as conn:
                cursor = conn.cursor()
                for key, value in config_data.items():
                    cursor.execute('''
                        INSERT OR REPLACE INTO config (key, value, updated_at)
                        VALUES (?, ?, datetime('now', 'localtime'))
                    ''', (key, str(value)))
                conn.commit()
                logger.info(f"[CONFIG_SYNC] Synced {len(config_data)} config items to local database")
                return True
        except Exception as e:
            logger.error(f"[CONFIG_SYNC] Error syncing config to database: {e}")
            return False
    
    def get_config(self, key: str, default=None):
        """Get config value from cache"""
        return self.config_cache.get(key, default)
    
    def fetch_config_from_backend(self) -> bool:
        """No-op: configs arrive via MQTT config/update and config/bulk-update topics only."""
        return True
