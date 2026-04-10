import json
from datetime import datetime
from PySide6.QtCore import QObject, QTimer, Signal
from src.core.config import Config


class MQTTTelemetrySender(QObject):    
    telemetry_sent = Signal(str)
    offline_data_buffered = Signal(int)
    
    def __init__(self, mqtt_service, telemetry_service, database_manager):
        super().__init__()
        self.mqtt_service = mqtt_service
        self.telemetry_service = telemetry_service
        self.database_manager = database_manager
        self.timer = QTimer()
        self.timer.timeout.connect(self._send_mqtt_telemetry)
    
    def start(self, interval: int = 2):
        self.timer.start(interval * 1000)
        print(f"[mqtt sender] Started sending telemetry every {interval}s")
    
    def stop(self):
        self.timer.stop()
        print(f"[mqtt sender] Stopped")
    
    def _send_mqtt_telemetry(self):
        """Send telemetry via MQTT and store locally"""
        parameters = self.telemetry_service.get_parameters()
        if not parameters:
            return
        
        timestamp = datetime.now().isoformat()
        
        # Store in local database
        for param_id, param in parameters.items():
            try:
                self.database_manager.store_parameter_stream(
                    parameter_id=int(param_id),
                    value=param.get('value', 0)
                )
            except Exception as e:
                print(f"[mqtt sender] Error storing parameter stream: {e}")
        
        # If MQTT connected, send via MQTT
        if self.mqtt_service.is_connected:
            payload = {
                'client_id': self.mqtt_service.device_id,
                'timestamp': timestamp,
                'parameters': [
                    {
                        'parameter_id': p['id'],
                        'id': p['id'],
                        'name': p['name'],
                        'value': p['value'],
                        'unit': p['unit']
                    }
                    for p in parameters.values()
                ]
            }
            
            try:
                success = self.mqtt_service.client.publish(
                    self.mqtt_service.telemetry_topic,
                    json.dumps(payload),
                    qos=1
                )
                if success:
                    print(f"[mqtt sender] Published telemetry at {timestamp}")
                    self.telemetry_sent.emit(timestamp)
            except Exception as e:
                print(f"[mqtt sender] Error publishing: {e}")
        else:
            # Buffer data when offline
            buffered_count = len(parameters)
            print(f"[mqtt sender] MQTT offline - buffered {buffered_count} parameters")
            self.offline_data_buffered.emit(buffered_count)

    def publish_user_change(self, topic: str, payload: dict) -> bool:
        """Publish user change via MQTT"""
        if not self.mqtt_service.is_connected:
            return False
        
        try:
            success = self.mqtt_service.client.publish(topic, json.dumps(payload), qos=1)
            if success:
                print(f"[mqtt sender] Published user change to {topic}")
                return True
            return False
        except Exception as e:
            print(f"[mqtt sender] Error publishing user change: {e}")
            return False
