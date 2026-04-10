"""
Security middleware for route protection and validation
"""

from functools import wraps
from flask import request, jsonify, current_app
from app.middleware.auth_middleware import token_required
import logging
import re
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Custom security exception"""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class InputValidator:
    """Validates user input"""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_password(password: str) -> tuple[bool, str]:
        """Validate password strength"""
        if len(password) < 8:
            return False, "Password must be at least 8 characters"
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain uppercase letter"
        if not re.search(r'[a-z]', password):
            return False, "Password must contain lowercase letter"
        if not re.search(r'[0-9]', password):
            return False, "Password must contain number"
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "Password must contain special character"
        return True, "Valid"
    
    @staticmethod
    def validate_string(value: str, min_length: int = 1, max_length: int = 255) -> bool:
        """Validate string length"""
        if not isinstance(value, str):
            return False
        return min_length <= len(value) <= max_length
    
    @staticmethod
    def validate_integer(value: Any, min_val: int = 0, max_val: int = 2147483647) -> bool:
        """Validate integer range"""
        try:
            val = int(value)
            return min_val <= val <= max_val
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_float(value: Any, min_val: float = 0.0, max_val: float = float('inf')) -> bool:
        """Validate float range"""
        try:
            val = float(value)
            return min_val <= val <= max_val
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def sanitize_string(value: str) -> str:
        """Remove potentially dangerous characters"""
        # Remove SQL injection attempts
        dangerous_patterns = [
            r"('|\")(.*?)(OR|AND|UNION|SELECT|DROP|INSERT|UPDATE|DELETE)",
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
        ]
        
        result = value
        for pattern in dangerous_patterns:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)
        
        return result.strip()


def require_auth(f: Callable) -> Callable:
    """Decorator to require authentication"""
    @wraps(f)
    @token_required
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated_function


def require_role(*roles: str) -> Callable:
    """Decorator to require specific role"""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        @token_required
        def decorated_function(*args, **kwargs):
            from flask_jwt_extended import get_jwt_identity
            from app.models.user import User
            
            user_id = get_jwt_identity()
            user = User.query.get(user_id)
            
            if not user or user.role not in roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def validate_json(*required_fields: str) -> Callable:
    """Decorator to validate JSON request"""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                return jsonify({'error': 'Request must be JSON'}), 400
            
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Empty request body'}), 400
            
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                return jsonify({
                    'error': f'Missing required fields: {", ".join(missing_fields)}'
                }), 400
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def validate_query_params(**param_specs: Dict[str, Any]) -> Callable:
    """Decorator to validate query parameters"""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            errors = {}
            
            for param_name, spec in param_specs.items():
                value = request.args.get(param_name)
                
                if spec.get('required') and not value:
                    errors[param_name] = f"{param_name} is required"
                    continue
                
                if value:
                    param_type = spec.get('type', str)
                    
                    try:
                        if param_type == int:
                            int(value)
                        elif param_type == float:
                            float(value)
                        elif param_type == bool:
                            if value.lower() not in ['true', 'false']:
                                errors[param_name] = f"{param_name} must be boolean"
                    except ValueError:
                        errors[param_name] = f"{param_name} has invalid type"
            
            if errors:
                return jsonify({'errors': errors}), 400
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def rate_limit(max_requests: int = 100, window: int = 60) -> Callable:
    """Decorator for rate limiting"""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask_limiter import Limiter
            from flask_limiter.util import get_remote_address
            
            limiter = Limiter(
                key_func=get_remote_address,
                default_limits=[f"{max_requests} per {window} seconds"]
            )
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def handle_errors(f: Callable) -> Callable:
    """Decorator to handle errors"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except SecurityError as e:
            logger.warning(f"Security error: {e.message}")
            return jsonify({'error': e.message}), e.status_code
        except ValueError as e:
            logger.warning(f"Validation error: {str(e)}")
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return jsonify({'error': 'Internal server error'}), 500
    return decorated_function


class SecurityMiddleware:
    """Security middleware for Flask app"""
    
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize middleware with Flask app"""
        self.app = app
        
        # Add security headers
        @app.after_request
        def add_security_headers(response):
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            response.headers['Content-Security-Policy'] = "default-src 'self'"
            return response
        
        # Add request logging
        @app.before_request
        def log_request():
            logger.debug(f"Request: {request.method} {request.path}")
        
        # Add error handlers
        @app.errorhandler(400)
        def bad_request(error):
            return jsonify({'error': 'Bad request', 'status': 400}), 400

        @app.errorhandler(401)
        def unauthorized(error):
            return jsonify({'error': 'Unauthorized — valid JWT token required', 'status': 401}), 401

        @app.errorhandler(403)
        def forbidden(error):
            return jsonify({'error': 'Forbidden — insufficient permissions', 'status': 403}), 403

        @app.errorhandler(404)
        def not_found(error):
            return jsonify({'error': f'Endpoint not found: {request.path}', 'status': 404}), 404

        @app.errorhandler(405)
        def method_not_allowed(error):
            return jsonify({'error': f'Method {request.method} not allowed on {request.path}', 'status': 405}), 405

        @app.errorhandler(500)
        def internal_error(error):
            logger.error(f"Internal error: {str(error)}")
            return jsonify({'error': 'Internal server error', 'status': 500}), 500


# Export validators and decorators
__all__ = [
    'SecurityError',
    'InputValidator',
    'require_auth',
    'require_role',
    'validate_json',
    'validate_query_params',
    'rate_limit',
    'handle_errors',
    'SecurityMiddleware'
]
