import pytest
from src.core.config import Config, ConfigManager

def test_config_defaults():
    """Test default configuration values"""
    assert Config.MQTT_PORT == 18883
    assert Config.TELEMETRY_INTERVAL == 2
    assert Config.APP_NAME == "PrecisionPulse Desktop"

def test_config_manager(qapp):
    """Test dynamic configuration manager"""
    manager = ConfigManager()
    
    # Test initial values
    assert manager.get('TELEMETRY_INTERVAL') == 2
    
    # Test update
    manager.update_config({'TELEMETRY_INTERVAL': 5})
    assert manager.get('TELEMETRY_INTERVAL') == 5
