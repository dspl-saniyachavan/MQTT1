"""
MQTT Client Interface for loose coupling
"""

from abc import ABC, abstractmethod
from typing import Callable, Optional


class IMQTTClient(ABC):
    """Interface for MQTT client implementations"""
    
    @abstractmethod
    def connect(self, broker: str, port: int, keepalive: int = 60) -> bool:
        """Connect to MQTT broker"""
        pass
    
    @abstractmethod
    def disconnect(self):
        """Disconnect from MQTT broker"""
        pass
    
    @abstractmethod
    def publish(self, topic: str, payload: str, qos: int = 0) -> bool:
        """Publish message to topic"""
        pass
    
    @abstractmethod
    def subscribe(self, topic: str, qos: int = 0):
        """Subscribe to topic"""
        pass
    
    @abstractmethod
    def set_on_connect_callback(self, callback: Callable):
        """Set callback for connection events"""
        pass
    
    @abstractmethod
    def set_on_disconnect_callback(self, callback: Callable):
        """Set callback for disconnection events"""
        pass
    
    @abstractmethod
    def set_on_message_callback(self, callback: Callable):
        """Set callback for message events"""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to broker"""
        pass
    
    @abstractmethod
    def loop_start(self):
        """Start network loop"""
        pass
    
    @abstractmethod
    def loop_stop(self):
        """Stop network loop"""
        pass
