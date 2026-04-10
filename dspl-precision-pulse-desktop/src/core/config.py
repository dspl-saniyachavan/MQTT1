"""
Configuration management for PrecisionPulse Desktop
"""

import os
from dotenv import load_dotenv
from PySide6.QtCore import QObject, Signal

load_dotenv()

class ConfigManager(QObject):
    """Dynamic configuration manager"""
    
    config_updated = Signal(str, str)  # key, value
    
    def __init__(self):
        super().__init__()
        self._config = {}
        self._load_config()
    
    def _load_config(self):
        """Load configuration from environment"""
        self._config = {
            'TELEMETRY_INTERVAL': int(os.getenv('TELEMETRY_INTERVAL', 3)),
            'HEARTBEAT_INTERVAL': int(os.getenv('HEARTBEAT_INTERVAL', 30)),
            'MQTT_BROKER': os.getenv('MQTT_BROKER', 'localhost'),
            'MQTT_PORT': int(os.getenv('MQTT_PORT', 18883)),
        }           
    
    def update_config(self, updates: dict):
        """Update configuration from remote command"""
        for key, value in updates.items():
            if key in self._config:
                old_value = self._config[key]
                self._config[key] = value
                self.config_updated.emit(key, str(value))   
                print(f"Config updated: {key} = {value} (was {old_value})")
    
    def get(self, key: str, default=None):
        """Get configuration value"""
        return self._config.get(key, default)

class Config:
    """Application configuration"""
    
    # Database
    DATABASE_PATH = os.getenv('DATABASE_PATH', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'data', 'precision_pulse.db'))
    
    # MQTT Configuration
    MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
    MQTT_PORT = int(os.getenv('MQTT_PORT', 18883))
    MQTT_USERNAME = os.getenv('MQTT_USERNAME', '')
    MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', '')
    MQTT_USE_TLS = os.getenv('MQTT_USE_TLS', 'true').lower() == 'true'
    MQTT_CA_CERTS = os.getenv('MQTT_CA_CERTS', 'config/ca.crt')
    MQTT_KEEPALIVE = int(os.getenv('MQTT_KEEPALIVE', 60))
    MQTT_RECONNECT_DELAY = int(os.getenv('MQTT_RECONNECT_DELAY', 5))
    
    # Topics
    MQTT_TOPIC_TELEMETRY = 'precisionpulse/telemetry'  # Will be: precisionpulse/{device_id}/telemetry
    MQTT_TOPIC_COMMANDS = 'precisionpulse/commands'
    MQTT_TOPIC_SYNC = 'precisionpulse/sync'
    MQTT_TOPIC_SYNC_USERS = 'precisionpulse/sync/users'
    MQTT_TOPIC_SYNC_CONFIG = 'precisionpulse/sync/config'
    MQTT_TOPIC_SYNC_PARAMETERS = 'precisionpulse/sync/parameters'
    MQTT_TOPIC_HEARTBEAT = 'precisionpulse/heartbeat'  # Will be: precisionpulse/{device_id}/heartbeat
    MQTT_TOPIC_PARAMETERS = 'precisionpulse/parameters'
    
    # Telemetry

    TELEMETRY_INTERVAL = int(os.getenv('TELEMETRY_INTERVAL', 3))  # seconds
    HEARTBEAT_INTERVAL = int(os.getenv('HEARTBEAT_INTERVAL', 30))  # seconds
    
    # Web API
    WEB_API_BASE_URL = os.getenv('WEB_API_BASE_URL', 'http://localhost:5000/api')
    BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:5000')
    
    # Shared secret — must match backend JWT_SECRET for payload decryption
    JWT_SECRET = os.getenv('JWT_SECRET', '')

    # Application
    APP_NAME = "PrecisionPulse Desktop"
    APP_VERSION = "1.0.0"
    DEVICE_ID = os.getenv('DEVICE_ID', 'desktop-001')