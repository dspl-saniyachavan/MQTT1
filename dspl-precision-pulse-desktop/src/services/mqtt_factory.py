"""
MQTT Client Factory
"""

import os
from src.services.mqtt_interface import IMQTTClient
from src.services.paho_mqtt_client import PahoMQTTClient
from src.core.config import Config


class MQTTClientFactory:
    """Factory for creating MQTT clients"""
    
    @staticmethod
    def create_client(client_id: str) -> IMQTTClient:
        """Create MQTT client with configuration from Config"""
        
        # Get certificate paths
        config_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            'config'
        )
        
        ca_certs = os.path.join(config_dir, 'ca.crt')
        # Don't use client certificates for self-signed setup
        certfile = None
        keyfile = None
        
        return PahoMQTTClient(
            client_id=f"desktop_{client_id}",
            use_tls=Config.MQTT_USE_TLS,
            ca_certs=ca_certs,
            certfile=certfile,
            keyfile=keyfile,
            username=Config.MQTT_USERNAME,
            password=Config.MQTT_PASSWORD,
            verify_certs=False  # Disable verification for self-signed certs
        )
