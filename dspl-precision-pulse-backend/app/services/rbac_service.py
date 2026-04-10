"""
RBAC service for permission enforcement and checking
"""
from app.models import db
from app.models.role import Role
from app.models.permission import Permission
from app.models.user import User
import logging

logger = logging.getLogger(__name__)

class RBACService:
    """Service for role-based access control"""
    
    # Default system roles
    DEFAULT_ROLES = {
        'admin': {
            'description': 'Administrator with full access',
            'is_system': True,
            'permissions': [
                ('users', 'create'), ('users', 'read'), ('users', 'update'), ('users', 'delete'),
                ('parameters', 'create'), ('parameters', 'read'), ('parameters', 'update'), ('parameters', 'delete'),
                ('config', 'create'), ('config', 'read'), ('config', 'update'), ('config', 'delete'),
                ('reports', 'create'), ('reports', 'read'), ('reports', 'update'), ('reports', 'delete'),
                ('audit_logs', 'read'),
            ]
        },
        'operator': {
            'description': 'Operator with read/update access',
            'is_system': True,
            'permissions': [
                ('users', 'read'),
                ('parameters', 'read'), ('parameters', 'update'),
                ('config', 'read'),
                ('reports', 'read'),
            ]
        },
        'viewer': {
            'description': 'Viewer with read-only access',
            'is_system': True,
            'permissions': [
                ('users', 'read'),
                ('parameters', 'read'),
                ('config', 'read'),
                ('reports', 'read'),
            ]
        },
        'user': {
            'description': 'Regular user with limited access',
            'is_system': True,
            'permissions': [
                ('parameters', 'read'),
                ('reports', 'read'),
            ]
        }
    }
    
    @staticmethod
    def initialize_default_roles():
        """Initialize default system roles"""
        try:
            for role_name, role_config in RBACService.DEFAULT_ROLES.items():
                existing = Role.query.filter_by(name=role_name).first()
                if not existing:
                    role = Role(
                        name=role_name,
                        description=role_config['description'],
                        is_system=role_config['is_system']
                    )
                    db.session.add(role)
                    db.session.flush()
                    
                    # Add permissions
                    for resource, action in role_config['permissions']:
                        perm = Permission(
                            role_id=role.id,
                            resource=resource,
                            action=action,
                            allowed=True
                        )
                        db.session.add(perm)
                    
                    logger.info(f"[RBAC] Created default role: {role_name}")
            
            db.session.commit()
            logger.info("[RBAC] Default roles initialized")
            return True
        except Exception as e:
            logger.error(f"[RBAC] Error initializing default roles: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def check_permission(user_id: int, resource: str, action: str) -> bool:
        """Check if user has permission for resource action"""
        try:
            user = User.query.get(user_id)
            if not user:
                logger.warning(f"[RBAC] User {user_id} not found")
                return False
            
            role = Role.query.filter_by(name=user.role).first()
            if not role:
                logger.warning(f"[RBAC] Role {user.role} not found for user {user_id}")
                return False
            
            return role.has_permission(resource, action)
        except Exception as e:
            logger.error(f"[RBAC] Error checking permission: {e}")
            return False
    
    @staticmethod
    def get_user_permissions(user_id: int) -> dict:
        """Get all permissions for a user"""
        try:
            user = User.query.get(user_id)
            if not user:
                return {}
            
            role = Role.query.filter_by(name=user.role).first()
            if not role:
                return {}
            
            permissions = {}
            for perm in role.permissions:
                if perm.resource not in permissions:
                    permissions[perm.resource] = []
                if perm.allowed:
                    permissions[perm.resource].append(perm.action)
            
            return permissions
        except Exception as e:
            logger.error(f"[RBAC] Error getting user permissions: {e}")
            return {}
    
    @staticmethod
    def create_role(name: str, description: str = None, permissions: list = None) -> Role:
        """Create a new role"""
        try:
            if Role.query.filter_by(name=name).first():
                raise ValueError(f"Role {name} already exists")
            
            role = Role(name=name, description=description, is_system=False)
            db.session.add(role)
            db.session.flush()
            
            # Add permissions
            if permissions:
                for resource, action in permissions:
                    perm = Permission(
                        role_id=role.id,
                        resource=resource,
                        action=action,
                        allowed=True
                    )
                    db.session.add(perm)
            
            db.session.commit()
            logger.info(f"[RBAC] Created role: {name}")
            return role
        except Exception as e:
            logger.error(f"[RBAC] Error creating role: {e}")
            db.session.rollback()
            raise
    
    @staticmethod
    def update_role_permissions(role_id: int, permissions: list) -> bool:
        """Update role permissions"""
        try:
            role = Role.query.get(role_id)
            if not role:
                raise ValueError(f"Role {role_id} not found")
            
            if role.is_system:
                raise ValueError(f"Cannot modify system role {role.name}")
            
            # Clear existing permissions
            Permission.query.filter_by(role_id=role_id).delete()
            
            # Add new permissions
            for resource, action in permissions:
                perm = Permission(
                    role_id=role_id,
                    resource=resource,
                    action=action,
                    allowed=True
                )
                db.session.add(perm)
            
            db.session.commit()
            logger.info(f"[RBAC] Updated permissions for role {role.name}")
            return True
        except Exception as e:
            logger.error(f"[RBAC] Error updating role permissions: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def delete_role(role_id: int) -> bool:
        """Delete a role"""
        try:
            role = Role.query.get(role_id)
            if not role:
                raise ValueError(f"Role {role_id} not found")
            
            if role.is_system:
                raise ValueError(f"Cannot delete system role {role.name}")
            
            # Check if role is in use
            if User.query.filter_by(role=role.name).first():
                raise ValueError(f"Role {role.name} is in use by users")
            
            db.session.delete(role)
            db.session.commit()
            logger.info(f"[RBAC] Deleted role: {role.name}")
            return True
        except Exception as e:
            logger.error(f"[RBAC] Error deleting role: {e}")
            db.session.rollback()
            return False

# Global instance
rbac_service = RBACService()
