"""
MQTT Service for real-time bidirectional communication
"""

import json
import time
from PySide6.QtCore import QObject, Signal, QTimer
from src.core.config import Config
from src.services.mqtt_interface import IMQTTClient
from datetime import datetime


class MQTTService(QObject):
    """Service for MQTT communication with loose coupling"""
    
    # Signals
    connected = Signal()
    disconnected = Signal()
    message_received = Signal(str, dict)
    parameter_update_received = Signal(str, float)
    config_update_received = Signal(dict)
    command_received = Signal(dict)  # command payload
    
    def __init__(self, device_id: str, mqtt_client: IMQTTClient):
        super().__init__()
        self.device_id = device_id
        self.client = mqtt_client
        self.is_connected = False
        self.last_message_time = time.time()
        self._signal_emitted = False
        
        # Setup callbacks
        self.client.set_on_connect_callback(self._on_connect)
        self.client.set_on_disconnect_callback(self._on_disconnect)
        self.client.set_on_message_callback(self._on_message)
        
        # Connection monitor timer
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._check_connection)
        
        # Device-specific topics
        self.telemetry_topic = f"precisionpulse/{device_id}/telemetry"
        self.command_topic = f"precisionpulse/{device_id}/command"
        self.heartbeat_topic = f"precisionpulse/{device_id}/heartbeat"
    
    def connect(self):
        """Connect to MQTT broker with TLS only"""
        try:
            print(f"[MQTT] Connecting to {Config.MQTT_BROKER}:{Config.MQTT_PORT} (TLS)...")
            success = self.client.connect(Config.MQTT_BROKER, Config.MQTT_PORT, Config.MQTT_KEEPALIVE)
            if success:
                self.client.loop_start()
                self.monitor_timer.start(2000)
                print(f"[MQTT] Connection initiated successfully")
                return True
            else:
                print(f"[MQTT] Connection failed")
                return False
        except Exception as e:
            print(f"[MQTT] Connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.monitor_timer.stop()
        self.client.loop_stop()
        self.client.disconnect()
    
    def _check_connection(self):
        """Check if connection is still alive"""
        client_connected = self.client.is_connected()
        
        if client_connected != self.is_connected:
            self.is_connected = client_connected
            if client_connected:
                print(f"[MQTT] Connection restored - emitting signal")
                self.connected.emit()
            else:
                print(f"[MQTT] Connection lost - emitting signal")
                self.disconnected.emit()
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to broker"""
        if rc == 0:
            print(f"[MQTT] Connected to broker at {Config.MQTT_BROKER}:{Config.MQTT_PORT}")
            self.is_connected = True
            self.last_message_time = time.time()
            
            # Subscribe to topics
            self.client.subscribe(self.command_topic)
            self.client.subscribe(f"{Config.MQTT_TOPIC_COMMANDS}/config/update")
            self.client.subscribe("precisionpulse/config/update")
            self.client.subscribe("precisionpulse/config/bulk-update")
            self.client.subscribe(f"precisionpulse/commands/{self.device_id}/#")
            self.client.subscribe("precisionpulse/commands/broadcast/#")
            self.client.subscribe("precisionpulse/+/telemetry")
            self.client.subscribe("precisionpulse/+/heartbeat")
            self.client.subscribe("precisionpulse/sync/parameters")
            self.client.subscribe("precisionpulse/sync/users/#")
            self.client.subscribe("precisionpulse/sync/roles/#")
            self.client.subscribe("precisionpulse/sync/permissions/#")
            self.client.subscribe("precisionpulse/presence/#")
            print(f"[MQTT] Subscribed to topics")
            
            # Emit connected signal
            self.connected.emit()
            self._send_heartbeat()
        else:
            print(f"[MQTT] Connection failed (code: {rc})")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from broker"""
        print(f"[MQTT] Disconnected from broker (rc={rc})")
        self.is_connected = False
        self.disconnected.emit()
    
    def _on_message(self, client, userdata, msg):
        """Callback when message received"""
        self.last_message_time = time.time()
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            print(f"[MQTT] Received message on topic: {topic}")
            
            if "sync" in topic:
                self.message_received.emit(topic, payload)
            elif "commands" in topic:
                self.message_received.emit(topic, payload)  # CommandExecutor listens on message_received
                self.command_received.emit(payload)
            elif "config/update" in topic or "config/bulk-update" in topic:
                self.config_update_received.emit(payload)
            elif "telemetry" in topic and topic != self.telemetry_topic:
                if 'parameters' in payload:
                    for param in payload['parameters']:
                        self.parameter_update_received.emit(param['id'], param['value'])
            elif 'parameters/update' in topic or payload.get('type') == 'parameter_update':
                param_id = payload.get('parameter_id')
                value = payload.get('value')
                if param_id and value is not None:
                    self.parameter_update_received.emit(param_id, float(value))
        except Exception as e:
            print(f"[MQTT] Message handling error: {e}")
    
    def publish_telemetry(self, parameters: list) -> bool:
        """Publish telemetry data to MQTT broker only (API call handled by telemetry_service)"""
        if not parameters:
            return False
        
        try:
            payload = {
                'client_id': self.device_id,
                'timestamp': datetime.now().isoformat(),
                'parameters': parameters
            }
            
            if self.is_connected:
                success = self.client.publish(
                    self.telemetry_topic,
                    json.dumps(payload),
                    qos=1
                )
                if success:
                    print(f"[MQTT] Telemetry published to MQTT broker")
                return success
            
            return False
        except Exception as e:
            print(f"[MQTT] Publish error: {e}")
            return False
    
    def publish_buffered_data(self, buffered_data: list) -> bool:
        """Publish buffered historical data to MQTT"""
        if not buffered_data:
            return False
        
        if not self.client.is_connected():
            print(f"[MQTT] Cannot publish buffered data - client not connected")
            return False
        
        try:
            payload = {
                'device_id': self.device_id,
                'type': 'buffered_sync',
                'timestamp': datetime.now().isoformat(),
                'records': buffered_data
            }
            
            topic = f"precisionpulse/{self.device_id}/buffer/sync"
            success = self.client.publish(topic, json.dumps(payload), qos=2)
            if success:
                print(f"[MQTT] Published {len(buffered_data)} buffered records to {topic}")
            else:
                print(f"[MQTT] Failed to publish buffered data")
            return success
        except (json.JSONDecodeError, TypeError) as e:
            print(f"[MQTT] Error publishing buffered data: {e}")
            return False
    
    def acknowledge_command(self, command_id: str) -> bool:
        """Acknowledge received command"""
        if not self.is_connected:
            return False
        
        try:
            payload = {
                'device_id': self.device_id,
                'command_id': command_id,
                'status': 'acknowledged',
                'timestamp': datetime.now().isoformat() + 'Z'
            }
            
            return self.client.publish(
                f"{Config.MQTT_TOPIC_COMMANDS}/ack",
                json.dumps(payload),
                qos=1
            )
        except (json.JSONDecodeError, TypeError) as e:
            print(f"[MQTT] Error acknowledging command: {e}")
            return False
    
    def _send_heartbeat(self):
        """Send heartbeat to indicate device is online"""
        if not self.is_connected:
            return
        
        try:
            payload = {
                'client_id': self.device_id,
                'status': 'online',
                'timestamp': datetime.now().isoformat()
            }
            
            self.client.publish(
                self.heartbeat_topic,
                json.dumps(payload),
                qos=1
            )
        except Exception as e:
            pass

    def publish_user_presence(self, email: str, status: str = 'online'):
        """Publish user login/logout presence so manage-users page shows online status."""
        if not self.is_connected:
            return
        try:
            payload = {
                'email': email,
                'status': status,
                'device_id': self.device_id,
                'timestamp': datetime.now().isoformat()
            }
            self.client.publish(
                f'precisionpulse/presence/{self.device_id}',
                json.dumps(payload),
                qos=1
            )
        except Exception:
            pass
