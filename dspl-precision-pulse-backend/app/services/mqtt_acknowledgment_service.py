"""
MQTT Acknowledgment service to track message delivery from desktop clients
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Callable
import threading

logger = logging.getLogger(__name__)

class AckTracker:
    """Tracks acknowledgment status of a message"""
    
    def __init__(self, msg_id: str, timeout_seconds: int = 30):
        self.msg_id = msg_id
        self.created_at = datetime.now(timezone.utc)
        self.timeout_seconds = timeout_seconds
        self.acked_by = set()  # Set of client IDs that acknowledged
        self.callbacks = []
    
    def add_ack(self, client_id: str):
        """Record acknowledgment from a client"""
        self.acked_by.add(client_id)
        logger.info(f"[ACK] Message {self.msg_id} acked by {client_id}")
        self._trigger_callbacks()
    
    def add_callback(self, callback: Callable):
        """Add callback to trigger when ack received"""
        self.callbacks.append(callback)
    
    def _trigger_callbacks(self):
        """Trigger all registered callbacks"""
        for cb in self.callbacks:
            try:
                cb(self.msg_id, self.acked_by)
            except Exception as e:
                logger.error(f"[ACK] Callback error: {e}")
    
    def is_expired(self) -> bool:
        """Check if ack has expired"""
        return (datetime.now(timezone.utc) - self.created_at).total_seconds() > self.timeout_seconds
    
    def to_dict(self) -> dict:
        return {
            'msg_id': self.msg_id,
            'acked_by': list(self.acked_by),
            'created_at': self.created_at.isoformat(),
            'expired': self.is_expired()
        }


class MQTTAcknowledgmentService:
    """Service to track MQTT message acknowledgments"""
    
    def __init__(self):
        self.trackers: Dict[str, AckTracker] = {}
        self.cleanup_thread = None
        self.running = False
    
    def start(self):
        """Start cleanup worker"""
        if self.running:
            return
        self.running = True
        self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self.cleanup_thread.start()
        logger.info("[ACK] Acknowledgment service started")
    
    def stop(self):
        """Stop cleanup worker"""
        self.running = False
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=5)
        logger.info("[ACK] Acknowledgment service stopped")
    
    def track_message(self, msg_id: str, timeout_seconds: int = 30) -> AckTracker:
        """Start tracking a message"""
        tracker = AckTracker(msg_id, timeout_seconds)
        self.trackers[msg_id] = tracker
        logger.debug(f"[ACK] Tracking message {msg_id}")
        return tracker
    
    def record_ack(self, msg_id: str, client_id: str):
        """Record acknowledgment from client"""
        if msg_id in self.trackers:
            self.trackers[msg_id].add_ack(client_id)
        else:
            logger.warning(f"[ACK] Received ack for unknown message {msg_id}")
    
    def get_status(self, msg_id: str) -> dict:
        """Get acknowledgment status"""
        if msg_id not in self.trackers:
            return {'error': 'Message not found'}
        return self.trackers[msg_id].to_dict()
    
    def _cleanup_worker(self):
        """Remove expired trackers"""
        while self.running:
            try:
                expired = [mid for mid, tracker in self.trackers.items() if tracker.is_expired()]
                for mid in expired:
                    del self.trackers[mid]
                    logger.debug(f"[ACK] Cleaned up expired tracker {mid}")
                threading.Event().wait(10)  # Check every 10 seconds
            except Exception as e:
                logger.error(f"[ACK] Cleanup error: {e}")
                threading.Event().wait(10)


# Global instance
_ack_service = None

def get_ack_service() -> MQTTAcknowledgmentService:
    """Get or create acknowledgment service"""
    global _ack_service
    if _ack_service is None:
        _ack_service = MQTTAcknowledgmentService()
        _ack_service.start()
    return _ack_service
