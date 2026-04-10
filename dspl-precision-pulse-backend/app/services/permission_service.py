"""
Permission management service for RBAC
"""
import logging
from datetime import datetime, timezone, timedelta
from app.models import db
from app.models.permission import Permission

logger = logging.getLogger(__name__)

class PermissionService:
    """Manage permissions with caching"""
    
    def __init__(self):
        self.permission_cache = {}
        self.cache_ttl = 300  # 5 minutes
        self.cache_time = {}
    
    def set_permission(self, role: str, resource: str, action: str, allowed: bool = True):
        """Set permission for role"""
        try:
            perm = Permission.query.filter_by(
                role=role, resource=resource, action=action
            ).first()
            
            if perm:
                perm.allowed = allowed
            else:
                perm = Permission(role=role, resource=resource, action=action, allowed=allowed)
                db.session.add(perm)
            
            db.session.commit()
            self._invalidate_cache(role)
            logger.info(f"[PERMISSION] Set {role}:{resource}:{action} = {allowed}")
            return True
        except Exception as e:
            logger.error(f"[PERMISSION] Error setting permission: {e}")
            return False
    
    def get_permissions(self, role: str):
        """Get all permissions for role with caching"""
        # Check cache
        if role in self.permission_cache:
            if datetime.now(timezone.utc) - self.cache_time.get(role, datetime.now(timezone.utc)) < timedelta(seconds=self.cache_ttl):
                return self.permission_cache[role]
        
        try:
            perms = Permission.query.filter_by(role=role).all()
            result = [p.to_dict() for p in perms]
            
            # Cache result
            self.permission_cache[role] = result
            self.cache_time[role] = datetime.now(timezone.utc)
            
            return result
        except Exception as e:
            logger.error(f"[PERMISSION] Error getting permissions: {e}")
            return []
    
    def has_permission(self, role: str, resource: str, action: str) -> bool:
        """Check if role has permission"""
        perms = self.get_permissions(role)
        for perm in perms:
            if perm['resource'] == resource and perm['action'] == action:
                return perm['allowed']
        return False
    
    def delete_permission(self, role: str, resource: str, action: str):
        """Delete permission"""
        try:
            Permission.query.filter_by(
                role=role, resource=resource, action=action
            ).delete()
            db.session.commit()
            self._invalidate_cache(role)
            logger.info(f"[PERMISSION] Deleted {role}:{resource}:{action}")
            return True
        except Exception as e:
            logger.error(f"[PERMISSION] Error deleting permission: {e}")
            return False
    
    def _invalidate_cache(self, role: str):
        """Invalidate cache for role"""
        if role in self.permission_cache:
            del self.permission_cache[role]
        if role in self.cache_time:
            del self.cache_time[role]
    
    def init_default_permissions(self):
        """Initialize default permissions for roles"""
        default_perms = {
            'admin': [
                ('users', 'create'), ('users', 'read'), ('users', 'update'), ('users', 'delete'),
                ('parameters', 'create'), ('parameters', 'read'), ('parameters', 'update'), ('parameters', 'delete'),
                ('config', 'read'), ('config', 'update'),
                ('reports', 'create'), ('reports', 'read'), ('reports', 'delete'),
                ('audit_logs', 'read')
            ],
            'user': [
                ('users', 'read'),
                ('parameters', 'read'),
                ('reports', 'read')
            ],
            'client': [
                ('parameters', 'read')
            ]
        }
        
        for role, perms in default_perms.items():
            for resource, action in perms:
                self.set_permission(role, resource, action, True)

permission_service = PermissionService()
