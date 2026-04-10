"""
Permission sync service for syncing permissions from backend to desktop
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from app.services.mqtt_publisher import get_mqtt_publisher
from app import db

logger = logging.getLogger(__name__)


class PermissionSyncService:
    """Service for syncing permissions to desktop via MQTT"""
    
    def __init__(self):
        self.cache = {}  # role -> {permissions, timestamp}
        self.cache_ttl = 3600  # 1 hour
    
    def publish_role_permissions(self, role: str, permissions: List[Dict]) -> bool:
        """Publish permissions for a role to MQTT"""
        try:
            mqtt_pub = get_mqtt_publisher()
            
            if not mqtt_pub or not mqtt_pub.connected:
                logger.debug(f"[PERM_SYNC] MQTT not connected, cannot publish permissions for {role}")
                return False
            
            mqtt_pub.publish_permission_changed(role, permissions)
            
            # Update cache
            self.cache[role] = {
                'permissions': permissions,
                'timestamp': datetime.now()
            }
            
            logger.info(f"[PERM_SYNC] Published {len(permissions)} permissions for role {role}")
            return True
        
        except Exception as e:
            logger.warning(f"[PERM_SYNC] Error publishing permissions: {e}")
            return False
    
    def get_cached_permissions(self, role: str) -> Optional[List[Dict]]:
        """Get cached permissions for a role"""
        try:
            if role not in self.cache:
                return None
            
            cached = self.cache[role]
            age = (datetime.now() - cached['timestamp']).total_seconds()
            
            if age > self.cache_ttl:
                del self.cache[role]
                return None
            
            return cached['permissions']
        except Exception as e:
            logger.warning(f"[PERM_SYNC] Error getting cached permissions: {e}")
            return None
    
    def clear_cache(self):
        """Clear permission cache"""
        try:
            self.cache.clear()
            logger.info("[PERM_SYNC] Cleared permission cache")
        except Exception as e:
            logger.warning(f"[PERM_SYNC] Error clearing cache: {e}")
    
    def sync_all_permissions(self) -> int:
        """Sync all role permissions to desktop"""
        try:
            from app.models.permission import Permission
            
            # Get all unique roles with error handling
            try:
                roles = db.session.query(Permission.role).distinct().all()
            except Exception as db_error:
                logger.warning(f"[PERM_SYNC] Database error querying roles: {db_error}")
                return 0
            
            if not roles:
                logger.debug("[PERM_SYNC] No roles found to sync")
                return 0
            
            synced_count = 0
            for (role,) in roles:
                try:
                    # Get all permissions for this role
                    perms = Permission.query.filter_by(role=role).all()
                    perm_list = [p.to_dict() for p in perms]
                    
                    if self.publish_role_permissions(role, perm_list):
                        synced_count += 1
                except Exception as e:
                    logger.warning(f"[PERM_SYNC] Error syncing permissions for role {role}: {e}")
                    continue
            
            logger.info(f"[PERM_SYNC] Synced permissions for {synced_count} roles")
            return synced_count
        
        except Exception as e:
            logger.warning(f"[PERM_SYNC] Error syncing all permissions: {e}")
            return 0


# Global instance
permission_sync_service = PermissionSyncService()
