"""
Paho MQTT Client Implementation with TLS
"""

import ssl
import paho.mqtt.client as mqtt
import threading
import time
from typing import Callable, Optional
from src.services.mqtt_interface import IMQTTClient


class PahoMQTTClient(IMQTTClient):
    """Paho MQTT client implementation"""
    
    def __init__(self, client_id: str, use_tls: bool = False, 
                 ca_certs: str = None, certfile: str = None, keyfile: str = None,
                 username: str = None, password: str = None, verify_certs: bool = True):
        self.client = mqtt.Client(client_id=client_id)
        self._is_connected = False
        self.reconnect_thread = None
        self.should_reconnect = True
        self.broker = None
        self.port = None
        self.keepalive = 60
        
        # Configure TLS only if explicitly enabled
        if use_tls and ca_certs:
            self.client.tls_set(
                ca_certs=ca_certs,
                certfile=certfile,
                keyfile=keyfile,
                cert_reqs=ssl.CERT_NONE,
                tls_version=ssl.PROTOCOL_TLSv1_2
            )
            self.client.tls_insecure_set(True)
        
        # Set credentials
        if username and password:
            self.client.username_pw_set(username, password)
        
        # Internal callbacks
        self.client.on_connect = self._internal_on_connect
        self.client.on_disconnect = self._internal_on_disconnect
        self.client.on_message = self._internal_on_message
        
        # User callbacks
        self._on_connect_callback = None
        self._on_disconnect_callback = None
        self._on_message_callback = None
    
    def connect(self, broker: str, port: int, keepalive: int = 60) -> bool:
        try:
            self.broker = broker
            self.port = port
            self.keepalive = keepalive
            print(f"[PAHO] Connecting to {broker}:{port}...")
            result = self.client.connect(broker, port, keepalive)
            print(f"[PAHO] Connect result: {result}")
            if result == 0:
                return True
            else:
                print(f"[PAHO] Connection failed with code: {result}")
                return False
        except Exception as e:
            print(f"[PAHO] Connection error: {e}")
            return False
    
    def disconnect(self):
        self.should_reconnect = False
        self.client.disconnect()
    
    def publish(self, topic: str, payload: str, qos: int = 0) -> bool:
        result = self.client.publish(topic, payload, qos)
        return result.rc == mqtt.MQTT_ERR_SUCCESS
    
    def subscribe(self, topic: str, qos: int = 0):
        self.client.subscribe(topic, qos)
    
    def set_on_connect_callback(self, callback: Callable):
        self._on_connect_callback = callback
    
    def set_on_disconnect_callback(self, callback: Callable):
        self._on_disconnect_callback = callback
    
    def set_on_message_callback(self, callback: Callable):
        self._on_message_callback = callback
    
    def is_connected(self) -> bool:
        return self._is_connected
    
    def loop_start(self):
        self.client.loop_start()
    
    def loop_stop(self):
        self.client.loop_stop()
    
    def _internal_on_connect(self, client, userdata, flags, rc):
        self._is_connected = (rc == 0)
        print(f"[PAHO] _internal_on_connect: rc={rc}, _is_connected={self._is_connected}")
        if self._on_connect_callback:
            self._on_connect_callback(client, userdata, flags, rc)
    
    def _internal_on_disconnect(self, client, userdata, rc):
        self._is_connected = False
        print(f"[PAHO] _internal_on_disconnect: rc={rc}, _is_connected={self._is_connected}")
        if rc != 0:
            print(f"[PAHO] Unexpected disconnect: {rc}")
            self._start_reconnect_thread()
        if self._on_disconnect_callback:
            self._on_disconnect_callback(client, userdata, rc)
    
    def _start_reconnect_thread(self):
        if self.reconnect_thread is None or not self.reconnect_thread.is_alive():
            self.reconnect_thread = threading.Thread(target=self._reconnect_loop, daemon=True)
            self.reconnect_thread.start()
    
    def _reconnect_loop(self):
        retry_count = 0
        max_retries = 10
        base_delay = 2
        
        while self.should_reconnect and not self._is_connected and retry_count < max_retries:
            try:
                delay = min(base_delay * (2 ** retry_count), 60)
                print(f"[PAHO] Reconnecting in {delay}s (attempt {retry_count + 1}/{max_retries})")
                time.sleep(delay)
                self.client.reconnect()
                retry_count = 0
            except Exception as e:
                print(f"[PAHO] Reconnection failed: {e}")
                retry_count += 1
    
    def _internal_on_message(self, client, userdata, msg):
        if self._on_message_callback:
            self._on_message_callback(client, userdata, msg)
