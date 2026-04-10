"""
Desktop MQTT acknowledgment handler - sends acks back to backend
"""
import logging
import json
from typing import Optional
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

class DesktopAckHandler:
    """Handles sending acknowledgments to backend"""
    
    def __init__(self, mqtt_client: Optional[mqtt.Client] = None):
        self.mqtt_client = mqtt_client
        self.client_id = None
    
    def set_mqtt_client(self, client: mqtt.Client):
        """Set MQTT client instance"""
        self.mqtt_client = client
    
    def set_client_id(self, client_id: str):
        """Set this desktop's client ID"""
        self.client_id = client_id
        logger.info(f"[DESKTOP_ACK] Client ID set to {client_id}")
    
    def send_ack(self, msg_id: str, msg_type: str, status: str = 'success', error: Optional[str] = None):
        """Send acknowledgment to backend"""
        if not self.mqtt_client or not self.client_id:
            logger.warning("[DESKTOP_ACK] Cannot send ack - client not configured")
            return False
        
        try:
            payload = {
                'msg_id': msg_id,
                'msg_type': msg_type,
                'client_id': self.client_id,
                'status': status,
                'error': error,
                'timestamp': __import__('datetime').datetime.utcnow().isoformat()
            }
            
            topic = f'precisionpulse/ack/{msg_id}'
            result = self.mqtt_client.publish(topic, json.dumps(payload), qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"[DESKTOP_ACK] Sent ack for {msg_id} ({msg_type})")
                return True
            else:
                logger.error(f"[DESKTOP_ACK] Failed to send ack: rc={result.rc}")
                return False
        except Exception as e:
            logger.error(f"[DESKTOP_ACK] Error sending ack: {e}")
            return False


# Global instance
_ack_handler = None

def get_desktop_ack_handler() -> DesktopAckHandler:
    """Get or create desktop ack handler"""
    global _ack_handler
    if _ack_handler is None:
        _ack_handler = DesktopAckHandler()
    return _ack_handler
