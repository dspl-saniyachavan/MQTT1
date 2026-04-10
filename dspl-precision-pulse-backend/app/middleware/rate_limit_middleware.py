"""
Rate limiting middleware for API endpoints
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import request, jsonify
import logging

logger = logging.getLogger(__name__)


_RATE_30_MIN = '30/minute'

class RateLimitConfig:
    """Rate limiting configuration"""
    
    # Default limits
    DEFAULT_LIMIT = "500/hour"
    
    # Endpoint-specific limits
    LIMITS = {
        # Authentication endpoints — relaxed to avoid false 429s during dev/testing
        '/api/auth/login': '20/minute',
        '/api/auth/register': '10/minute',
        
        # User management - moderate
        '/api/users': _RATE_30_MIN,
        '/api/users/<int:user_id>': _RATE_30_MIN,
        
        # Telemetry - high volume
        '/api/telemetry/stream': '1000/minute',
        '/api/telemetry/latest': '100/minute',

        # Parameter stream - high volume (desktop pushes every 3s)
        '/api/parameter-stream/push': '1000/minute',
        '/api/parameter-stream/latest': '200/minute',

        # Parameters - moderate
        '/api/parameters': '50/minute',
        '/api/parameter-stream/parameter/<int:param_id>/value': '100/minute',
        
        # Configuration - moderate
        '/api/config': _RATE_30_MIN,
        
        # Remote commands - moderate
        '/api/remote-commands': '20/minute',
        
        # Buffer operations - high volume
        '/api/buffer': '500/minute',
        
        # Sync operations - low frequency
        '/api/sync': '10/minute',
    }


def create_limiter():
    """Create and configure rate limiter"""
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[RateLimitConfig.DEFAULT_LIMIT],
        storage_uri="memory://",
        strategy="fixed-window"
    )
    return limiter


def apply_rate_limits(app):
    """Apply rate limits to Flask app"""
    
    @app.errorhandler(429)
    def ratelimit_handler(e):
        """Handle rate limit exceeded"""
        logger.warning(f"Rate limit exceeded: {request.remote_addr} - {request.path}")
        return jsonify({
            'error': 'Rate limit exceeded',
            'message': 'Too many requests. Please try again later.',
            'retry_after': e.description
        }), 429
    
    logger.info("Rate limiting configured")


def get_rate_limit_status(limiter):
    """Get current rate limit status for a request"""
    try:
        # This is a helper function to check remaining requests
        # Implementation depends on limiter backend
        return {
            'limit': 'configured',
            'status': 'active'
        }
    except Exception as e:
        logger.error(f"Error getting rate limit status: {e}")
        return {
            'limit': 'unknown',
            'status': 'error'
        }
