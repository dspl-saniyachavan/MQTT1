from functools import wraps
from flask import request, jsonify

ROLE_PERMISSIONS = {
    'admin': [
        # Dashboard
        'dashboard.view',
        # Users
        'user.create', 'user.read', 'user.update', 'user.delete',
        # Profile
        'profile.view', 'profile.update',
        # Parameters
        'parameter.view', 'parameter.create', 'parameter.update', 'parameter.delete',
        'parameter.edit_values',
        # Telemetry
        'telemetry.view', 'telemetry.stream',
        # Audit Logs
        'audit_log.view',
        # History
        'history.view',
        # Reports
        'report.view', 'report.generate',
        # Config
        'config.view', 'config.update',
        # Remote Commands
        'remote_command.view', 'remote_command.execute',
        # Buffer
        'buffer.view', 'buffer.manage',
        # Role & Permission Management
        'role.manage', 'permission.manage',
    ],
    'user': [
        # Dashboard
        'dashboard.view',
        # Profile
        'profile.view', 'profile.update',
        # Parameters
        'parameter.view',
        # Telemetry
        'telemetry.view', 'telemetry.stream',
        # History
        'history.view',
        # Remote Commands
        'remote_command.view',
    ],
    'client': []
}

def require_permission(permission):
    """Decorator to check if user has required permission"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(request, 'user'):
                return jsonify({'error': 'User not authenticated'}), 401
            
            user_role = request.user.get('role')
            allowed_permissions = ROLE_PERMISSIONS.get(user_role, [])
            
            if permission not in allowed_permissions:
                return jsonify({'error': f'Insufficient permissions. Required: {permission}'}), 403
            
            return f(*args, **kwargs)
        return decorated
    return decorator

def require_role(*allowed_roles):
    """Decorator to check if user has required role"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(request, 'user'):
                return jsonify({'error': 'User not authenticated'}), 401
            
            user_role = request.user.get('role')
            
            if user_role not in allowed_roles:
                return jsonify({'error': f'Insufficient role. Required: {", ".join(allowed_roles)}'}), 403
            
            return f(*args, **kwargs)
        return decorated
    return decorator

def validate_request_payload(required_fields):
    """Decorator to validate request payload"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            data = request.get_json()
            
            if not data:
                return jsonify({'error': 'Request body is required'}), 400
            
            missing_fields = [field for field in required_fields if field not in data or not data[field]]
            if missing_fields:
                return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400
            
            return f(*args, **kwargs)
        return decorated
    return decorator
