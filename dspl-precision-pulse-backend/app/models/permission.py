"""
Permission model for resource-based access control
"""

from app import db
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class Permission(db.Model):
    """Resource-based permissions for roles"""
    
    __tablename__ = 'permissions'
    
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(50), nullable=False)  # 'admin', 'user', 'client'
    resource = db.Column(db.String(100), nullable=False)  # 'user', 'parameter', 'config', 'report'
    action = db.Column(db.String(50), nullable=False)  # 'create', 'read', 'update', 'delete'
    allowed = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    __table_args__ = (
        db.UniqueConstraint('role', 'resource', 'action', name='uq_role_resource_action'),
    )
    
    def __repr__(self):
        return f'<Permission {self.role}:{self.resource}:{self.action}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'role': self.role,
            'resource': self.resource,
            'action': self.action,
            'allowed': self.allowed,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


# Default permissions for each role
DEFAULT_PERMISSIONS = {
    'admin': [
        ('user', 'create', True),
        ('user', 'read', True),
        ('user', 'update', True),
        ('user', 'delete', True),
        ('parameter', 'create', True),
        ('parameter', 'read', True),
        ('parameter', 'update', True),
        ('parameter', 'delete', True),
        ('config', 'create', True),
        ('config', 'read', True),
        ('config', 'update', True),
        ('config', 'delete', True),
        ('report', 'create', True),
        ('report', 'read', True),
        ('report', 'update', True),
        ('report', 'delete', True),
    ],
    'user': [
        ('user', 'read', True),
        ('user', 'update', True),  # Can update own profile
        ('parameter', 'read', True),
        ('parameter', 'create', True),
        ('parameter', 'update', True),
        ('config', 'read', True),
        ('report', 'create', True),
        ('report', 'read', True),
    ],
    'client': [
        ('parameter', 'read', True),
        ('report', 'read', True),
    ]
}


def init_default_permissions():
    """Initialize default permissions for all roles"""
    try:
        # Check if permissions table exists
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        if 'permissions' not in tables:
            logger.warning("[PERMISSION] Permissions table does not exist, skipping initialization")
            return
        
        # Check if table has the required columns
        columns = [col['name'] for col in inspector.get_columns('permissions')]
        required_columns = ['role', 'resource', 'action', 'allowed']
        
        if not all(col in columns for col in required_columns):
            logger.warning(f"[PERMISSION] Permissions table missing required columns. Found: {columns}")
            return
        
        for role, perms in DEFAULT_PERMISSIONS.items():
            for resource, action, allowed in perms:
                try:
                    # Check if permission already exists
                    existing = Permission.query.filter_by(
                        role=role,
                        resource=resource,
                        action=action
                    ).first()
                    
                    if not existing:
                        perm = Permission(
                            role=role,
                            resource=resource,
                            action=action,
                            allowed=allowed
                        )
                        db.session.add(perm)
                except Exception as e:
                    logger.warning(f"[PERMISSION] Error checking permission {role}:{resource}:{action}: {e}")
                    continue
        
        db.session.commit()
        logger.info("[PERMISSION] Initialized default permissions")
    
    except Exception as e:
        logger.error(f"[PERMISSION] Error initializing default permissions: {e}")
        db.session.rollback()
