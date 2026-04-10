"""
Permission middleware for enforcing RBAC on endpoints
"""
from functools import wraps
from flask import g, jsonify
from app.services.rbac_service import rbac_service
import logging

logger = logging.getLogger(__name__)

def permission_required(resource: str, action: str):
    """Decorator to check if user has permission for resource action"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'user') or not g.user:
                return jsonify({'error': 'Unauthorized'}), 401
            
            user_id = g.user.get('id')
            if not user_id:
                return jsonify({'error': 'Unauthorized'}), 401
            
            # Check permission
            if not rbac_service.check_permission(user_id, resource, action):
                logger.warning(f"[PERMISSION] User {user_id} denied access to {resource}:{action}")
                return jsonify({'error': f'Permission denied for {resource}:{action}'}), 403
            
            logger.info(f"[PERMISSION] User {user_id} granted access to {resource}:{action}")
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def get_user_permissions():
    """Get current user's permissions"""
    if not hasattr(g, 'user') or not g.user:
        return {}
    
    user_id = g.user.get('id')
    if not user_id:
        return {}
    
    return rbac_service.get_user_permissions(user_id)
