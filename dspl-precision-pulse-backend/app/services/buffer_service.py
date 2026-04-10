"""
Buffer service for offline resilience
Buffers user and config changes when MQTT is disconnected
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from app.models.user_sync_buffer import UserSyncBuffer
from app.models.config_change_buffer import ConfigChangeBuffer
from app.services.mqtt_publisher import get_mqtt_publisher
from app import db

logger = logging.getLogger(__name__)


class BufferService:
    """Service for buffering changes during MQTT disconnection"""
    
    def __init__(self):
        self.max_retries = 3
        self.retry_delay = 5  # seconds
        self.app = None
    
    def set_app(self, app):
        """Set Flask app for context management"""
        self.app = app
    
    def buffer_user_change(self, user_id: int, email: str, action: str, user_data: dict) -> bool:
        """Buffer a user change (create/update/delete)"""
        try:
            buffer_entry = UserSyncBuffer(
                user_id=user_id,
                email=email,
                action=action,  # 'create', 'update', 'delete'
                user_data=user_data,
                status='pending',
                retry_count=0,
                created_at=datetime.now()
            )
            db.session.add(buffer_entry)
            db.session.commit()
            logger.info(f"[BUFFER] Buffered user {action}: {email}")
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"[BUFFER] Error buffering user change: {e}")
            return False
    
    def buffer_config_change(self, config_key: str, old_value: str, new_value: str) -> bool:
        """Buffer a config change"""
        try:
            buffer_entry = ConfigChangeBuffer(
                config_key=config_key,
                old_value=old_value,
                new_value=new_value,
                status='pending',
                retry_count=0,
                created_at=datetime.now()
            )
            db.session.add(buffer_entry)
            db.session.commit()
            logger.info(f"[BUFFER] Buffered config change: {config_key}")
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"[BUFFER] Error buffering config change: {e}")
            return False
    
    def flush_user_changes(self) -> int:
        """Flush buffered user changes to MQTT"""
        try:
            # Use app context if available
            if self.app:
                with self.app.app_context():
                    return self._do_flush_user_changes()
            else:
                return self._do_flush_user_changes()
        except Exception as e:
            logger.error(f"[BUFFER] Error flushing user changes: {e}")
            return 0
    
    def _do_flush_user_changes(self) -> int:
        """Internal method to flush user changes"""
        try:
            mqtt_pub = get_mqtt_publisher()
            
            # Get all pending user changes with error handling
            try:
                pending = UserSyncBuffer.query.filter_by(status='pending').all()
            except Exception as e:
                db.session.rollback()
                logger.warning(f"[BUFFER] Error querying user sync buffer (schema issue): {e}")
                logger.warning("[BUFFER] Skipping user buffer flush due to schema mismatch")
                return 0
            
            if not pending:
                logger.debug("[BUFFER] No pending user changes to flush")
                return 0
            
            flushed_count = 0
            for buffer_entry in pending:
                try:
                    # Check if MQTT is connected
                    if not mqtt_pub or not mqtt_pub.connected:
                        logger.warning("[BUFFER] MQTT not connected, cannot flush")
                        break
                    
                    # Publish based on action
                    if buffer_entry.action == 'create':
                        mqtt_pub.publish_user_created(buffer_entry.user_data)
                    elif buffer_entry.action == 'update':
                        mqtt_pub.publish_user_updated(buffer_entry.user_data)
                    elif buffer_entry.action == 'delete':
                        mqtt_pub.publish_user_deleted(buffer_entry.user_id, buffer_entry.email)
                    
                    # Mark as synced
                    buffer_entry.status = 'synced'
                    buffer_entry.synced_at = datetime.now()
                    db.session.commit()
                    flushed_count += 1
                    logger.info(f"[BUFFER] Flushed user {buffer_entry.action}: {buffer_entry.email}")
                
                except Exception as e:
                    db.session.rollback()
                    logger.error(f"[BUFFER] Error flushing user change: {e}")
                    buffer_entry.retry_count += 1
                    if buffer_entry.retry_count >= self.max_retries:
                        buffer_entry.status = 'failed'
                    db.session.commit()
            
            return flushed_count
        
        except Exception as e:
            logger.error(f"[BUFFER] Error in _do_flush_user_changes: {e}")
            return 0
    
    def flush_config_changes(self) -> int:
        """Flush buffered config changes to MQTT"""
        try:
            # Use app context if available
            if self.app:
                with self.app.app_context():
                    return self._do_flush_config_changes()
            else:
                return self._do_flush_config_changes()
        except Exception as e:
            logger.error(f"[BUFFER] Error flushing config changes: {e}")
            return 0
    
    def _do_flush_config_changes(self) -> int:
        """Internal method to flush config changes"""
        try:
            mqtt_pub = get_mqtt_publisher()
            
            # Get all pending config changes with error handling
            try:
                pending = ConfigChangeBuffer.query.filter_by(status='pending').all()
            except Exception as e:
                db.session.rollback()
                logger.warning(f"[BUFFER] Error querying config change buffer (schema issue): {e}")
                logger.warning("[BUFFER] Skipping config buffer flush due to schema mismatch")
                return 0
            
            if not pending:
                logger.debug("[BUFFER] No pending config changes to flush")
                return 0
            
            flushed_count = 0
            for buffer_entry in pending:
                try:
                    # Check if MQTT is connected
                    if not mqtt_pub or not mqtt_pub.connected:
                        logger.warning("[BUFFER] MQTT not connected, cannot flush")
                        break
                    
                    # Publish config change
                    mqtt_pub.publish_config_change(
                        buffer_entry.config_key,
                        buffer_entry.new_value
                    )
                    
                    # Mark as synced
                    buffer_entry.status = 'synced'
                    buffer_entry.synced_at = datetime.now()
                    db.session.commit()
                    flushed_count += 1
                    logger.info(f"[BUFFER] Flushed config change: {buffer_entry.config_key}")
                
                except Exception as e:
                    db.session.rollback()
                    logger.error(f"[BUFFER] Error flushing config change: {e}")
                    buffer_entry.retry_count += 1
                    if buffer_entry.retry_count >= self.max_retries:
                        buffer_entry.status = 'failed'
                    db.session.commit()
            
            return flushed_count
        
        except Exception as e:
            logger.error(f"[BUFFER] Error in _do_flush_config_changes: {e}")
            return 0
    
    def get_user_buffer_count(self) -> int:
        """Get count of buffered user changes"""
        try:
            return UserSyncBuffer.query.filter_by(status='pending').count()
        except Exception as e:
            logger.error(f"[BUFFER] Error getting user buffer count: {e}")
            return 0
    
    def get_config_buffer_count(self) -> int:
        """Get count of buffered config changes"""
        try:
            return ConfigChangeBuffer.query.filter_by(status='pending').count()
        except Exception as e:
            logger.error(f"[BUFFER] Error getting config buffer count: {e}")
            return 0
    
    def get_total_buffer_count(self) -> int:
        """Get total count of buffered changes"""
        return self.get_user_buffer_count() + self.get_config_buffer_count()
    
    def get_user_buffer_entries(self, limit: int = 100) -> List[Dict]:
        """Get buffered user changes"""
        try:
            entries = UserSyncBuffer.query.filter_by(status='pending').limit(limit).all()
            return [
                {
                    'id': e.id,
                    'user_id': e.user_id,
                    'email': e.email,
                    'action': e.action,
                    'status': e.status,
                    'retry_count': e.retry_count,
                    'created_at': e.created_at.isoformat()
                }
                for e in entries
            ]
        except Exception as e:
            logger.error(f"[BUFFER] Error getting user buffer entries: {e}")
            return []
    
    def get_config_buffer_entries(self, limit: int = 100) -> List[Dict]:
        """Get buffered config changes"""
        try:
            entries = ConfigChangeBuffer.query.filter_by(status='pending').limit(limit).all()
            return [
                {
                    'id': e.id,
                    'config_key': e.config_key,
                    'old_value': e.old_value,
                    'new_value': e.new_value,
                    'status': e.status,
                    'retry_count': e.retry_count,
                    'created_at': e.created_at.isoformat()
                }
                for e in entries
            ]
        except Exception as e:
            logger.error(f"[BUFFER] Error getting config buffer entries: {e}")
            return []
    
    def cleanup_old_buffers(self, days: int = 7) -> int:
        """Clean up old buffered entries"""
        try:
            cutoff = datetime.now() - timedelta(days=days)
            
            # Delete old synced user buffers
            user_deleted = UserSyncBuffer.query.filter(
                UserSyncBuffer.status == 'synced',
                UserSyncBuffer.synced_at < cutoff
            ).delete()
            
            # Delete old synced config buffers
            config_deleted = ConfigChangeBuffer.query.filter(
                ConfigChangeBuffer.status == 'synced',
                ConfigChangeBuffer.synced_at < cutoff
            ).delete()
            
            db.session.commit()
            total_deleted = user_deleted + config_deleted
            logger.info(f"[BUFFER] Cleaned up {total_deleted} old buffer entries")
            return total_deleted
        
        except Exception as e:
            logger.error(f"[BUFFER] Error cleaning up buffers: {e}")
            return 0
    
    def cleanup_failed_buffers(self, days: int = 30) -> int:
        """Clean up failed buffered entries"""
        try:
            cutoff = datetime.now() - timedelta(days=days)
            
            # Delete old failed user buffers
            user_deleted = UserSyncBuffer.query.filter(
                UserSyncBuffer.status == 'failed',
                UserSyncBuffer.created_at < cutoff
            ).delete()
            
            # Delete old failed config buffers
            config_deleted = ConfigChangeBuffer.query.filter(
                ConfigChangeBuffer.status == 'failed',
                ConfigChangeBuffer.created_at < cutoff
            ).delete()
            
            db.session.commit()
            total_deleted = user_deleted + config_deleted
            logger.info(f"[BUFFER] Cleaned up {total_deleted} failed buffer entries")
            return total_deleted
        
        except Exception as e:
            logger.error(f"[BUFFER] Error cleaning up failed buffers: {e}")
            return 0


# Global instance
buffer_service = BufferService()
