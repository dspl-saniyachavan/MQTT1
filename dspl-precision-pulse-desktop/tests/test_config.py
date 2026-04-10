import pytest
from src.core.config import Config, ConfigManager

def test_config_defaults():
    """Test default configuration values match actual config"""
    assert Config.MQTT_PORT == 18883          # TLS port used by the project
    assert Config.TELEMETRY_INTERVAL == 3     # 3-second interval
    assert Config.APP_NAME == "PrecisionPulse Desktop"

def test_config_manager(qapp):
    """Test dynamic configuration manager"""
    manager = ConfigManager()

    # Initial value matches TELEMETRY_INTERVAL_SECONDS (3)
    assert manager.get('TELEMETRY_INTERVAL') == 3

    # Test update
    manager.update_config({'TELEMETRY_INTERVAL': 5})
    assert manager.get('TELEMETRY_INTERVAL') == 5
