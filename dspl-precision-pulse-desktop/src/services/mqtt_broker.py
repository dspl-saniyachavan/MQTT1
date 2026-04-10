"""
Embedded MQTT Broker Service
"""

import subprocess
import os
import signal
from PySide6.QtCore import QObject, Signal


class MQTTBroker(QObject):
    """Embedded MQTT broker using Mosquitto"""
    
    broker_started = Signal()
    broker_stopped = Signal()
    broker_error = Signal(str)
    
    def __init__(self, config_path: str = None):
        super().__init__()
        self.process = None
        self.config_path = config_path or self._create_default_config()
    
    def _create_default_config(self) -> str:
        """Create default mosquitto configuration with TLS on 18883"""
        config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config')
        os.makedirs(config_dir, exist_ok=True)
        
        config_path = os.path.join(config_dir, 'mosquitto.conf')
        
        config_content = """# Mosquitto Configuration
# Plain MQTT (disabled)
# listener 1883
# allow_anonymous true

# TLS MQTT (enabled)
listener 18883
allow_anonymous true
cafile {ca_cert}
certfile {server_cert}
keyfile {server_key}
require_certificate false
tls_version tlsv1.2

persistence true
persistence_location /tmp/mosquitto/
""".format(
            ca_cert=os.path.join(config_dir, 'ca.crt'),
            server_cert=os.path.join(config_dir, 'server.crt'),
            server_key=os.path.join(config_dir, 'server.key')
        )
        
        with open(config_path, 'w') as f:
            f.write(config_content)
        
        return config_path
    
    def start(self) -> bool:
        """Start the MQTT broker"""
        try:
            if self.is_running():
                print("MQTT broker already running")
                return True
            
            # Start mosquitto with config
            self.process = subprocess.Popen(
                ['mosquitto', '-c', self.config_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            print(f"MQTT broker started with PID: {self.process.pid}")
            self.broker_started.emit()
            return True
            
        except FileNotFoundError:
            error_msg = "Mosquitto not found. Install with: sudo apt-get install mosquitto"
            print(error_msg)
            self.broker_error.emit(error_msg)
            return False
        except Exception as e:
            error_msg = f"Failed to start MQTT broker: {e}"
            print(error_msg)
            self.broker_error.emit(error_msg)
            return False
    
    def stop(self):
        """Stop the MQTT broker"""
        if self.process:
            try:
                self.process.send_signal(signal.SIGTERM)
                self.process.wait(timeout=5)
                print("MQTT broker stopped")
                self.broker_stopped.emit()
            except Exception as e:
                print(f"Error stopping broker: {e}")
                self.process.kill()
    
    def is_running(self) -> bool:
        """Check if broker is running"""
        return self.process is not None and self.process.poll() is None
