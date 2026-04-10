"""
Sync verification service to track MQTT message delivery and verify sync status
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SyncVerificationService:
    """Track and verify MQTT message delivery"""
    
    def __init__(self):
        self.messages = {}  # msg_id -> {topic, payload, timestamp, status}
        self.acks = {}  # msg_id -> {timestamp, status}
    
    def track_message(self, msg_id: str, topic: str, payload: dict):
        """Track a message being published"""
        self.messages[msg_id] = {
            'topic': topic,
            'payload': payload,
            'timestamp': datetime.now(),
            'status': 'pending'
        }
        logger.debug(f"[SYNC_VERIFY] Tracking message {msg_id}")
    
    def mark_delivered(self, msg_id: str):
        """Mark message as delivered to MQTT broker"""
        if msg_id in self.messages:
            self.messages[msg_id]['status'] = 'delivered'
            logger.debug(f"[SYNC_VERIFY] Message {msg_id} delivered to broker")
    
    def mark_acknowledged(self, msg_id: str):
        """Mark message as acknowledged by desktop"""
        if msg_id in self.messages:
            self.messages[msg_id]['status'] = 'acknowledged'
            self.acks[msg_id] = {
                'timestamp': datetime.now(),
                'status': 'acked'
            }
            logger.info(f"[SYNC_VERIFY] Message {msg_id} acknowledged by desktop")
    
    def mark_failed(self, msg_id: str, reason: str):
        """Mark message as failed"""
        if msg_id in self.messages:
            self.messages[msg_id]['status'] = 'failed'
            self.messages[msg_id]['error'] = reason
            logger.warning(f"[SYNC_VERIFY] Message {msg_id} failed: {reason}")
    
    def get_message_status(self, msg_id: str) -> Optional[Dict]:
        """Get status of a message"""
        return self.messages.get(msg_id)
    
    def get_pending_messages(self) -> List[Dict]:
        """Get all pending messages"""
        return [
            {'msg_id': msg_id, **msg}
            for msg_id, msg in self.messages.items()
            if msg['status'] == 'pending'
        ]
    
    def get_unacknowledged_messages(self, timeout_seconds: int = 30) -> List[Dict]:
        """Get messages not acknowledged within timeout"""
        cutoff = datetime.now() - timedelta(seconds=timeout_seconds)
        return [
            {'msg_id': msg_id, **msg}
            for msg_id, msg in self.messages.items()
            if msg['status'] in ['pending', 'delivered'] and msg['timestamp'] < cutoff
        ]
    
    def get_sync_status(self) -> Dict:
        """Get overall sync status"""
        total = len(self.messages)
        delivered = sum(1 for m in self.messages.values() if m['status'] == 'delivered')
        acknowledged = sum(1 for m in self.messages.values() if m['status'] == 'acknowledged')
        failed = sum(1 for m in self.messages.values() if m['status'] == 'failed')
        pending = sum(1 for m in self.messages.values() if m['status'] == 'pending')
        
        return {
            'total_messages': total,
            'delivered': delivered,
            'acknowledged': acknowledged,
            'failed': failed,
            'pending': pending,
            'success_rate': (acknowledged / total * 100) if total > 0 else 0
        }
    
    def cleanup_old_messages(self, days: int = 7):
        """Clean up messages older than specified days"""
        cutoff = datetime.now() - timedelta(days=days)
        old_msgs = [
            msg_id for msg_id, msg in self.messages.items()
            if msg['timestamp'] < cutoff
        ]
        for msg_id in old_msgs:
            del self.messages[msg_id]
            if msg_id in self.acks:
                del self.acks[msg_id]
        logger.info(f"[SYNC_VERIFY] Cleaned up {len(old_msgs)} old messages")


# Global instance
_sync_verification_service = None


def get_sync_verification_service() -> SyncVerificationService:
    """Get or create sync verification service"""
    global _sync_verification_service
    if _sync_verification_service is None:
        _sync_verification_service = SyncVerificationService()
    return _sync_verification_service
