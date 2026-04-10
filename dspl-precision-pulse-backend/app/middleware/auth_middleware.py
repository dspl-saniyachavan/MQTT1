import hashlib
import time
import logging
from functools import wraps
from flask import request, jsonify
from app.utils.jwt_utils import verify_token

logger = logging.getLogger(__name__)

# ── Brute-force lockout (in-memory, resets on restart) ────────────────────────────
# Tracks failed login attempts per IP: {ip: {'count': int, 'locked_until': float}}
_login_attempts: dict = {}
_MAX_ATTEMPTS   = 10     # lock after 10 consecutive failures
_LOCKOUT_SECS   = 60     # 1-minute lockout window


def record_failed_login(ip: str) -> None:
    now = time.time()
    entry = _login_attempts.get(ip, {'count': 0, 'locked_until': 0})
    # Reset counter if previous lockout has expired
    if entry['locked_until'] and now > entry['locked_until']:
        entry = {'count': 0, 'locked_until': 0}
    entry['count'] += 1
    if entry['count'] >= _MAX_ATTEMPTS:
        entry['locked_until'] = now + _LOCKOUT_SECS
        logger.warning(f"[AUTH] IP {ip} locked out for {_LOCKOUT_SECS}s after {_MAX_ATTEMPTS} failed attempts")
    _login_attempts[ip] = entry


def clear_failed_login(ip: str) -> None:
    _login_attempts.pop(ip, None)


def is_locked_out(ip: str) -> bool:
    entry = _login_attempts.get(ip)
    if not entry:
        return False
    if entry['locked_until'] and time.time() < entry['locked_until']:
        return True
    return False


# ── JWT token_required decorator ────────────────────────────────────────────────────────────

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        if auth_header:
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'error': 'Invalid token format'}), 401
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        payload = verify_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401
        request.user = payload
        return f(*args, **kwargs)
    return decorated


# ── ETag helper for GET responses ────────────────────────────────────────────────────────────

def make_etag(data: str) -> str:
    """Generate a weak ETag from response body."""
    return 'W/"' + hashlib.md5(data.encode()).hexdigest() + '"'


def etag_response(response):
    """Add ETag header and return 304 if client already has current version."""
    import json as _json
    from flask import Response
    body = response.get_data(as_text=True)
    etag = make_etag(body)
    response.headers['ETag'] = etag
    response.headers['Cache-Control'] = 'private, max-age=0, must-revalidate'
    if_none_match = request.headers.get('If-None-Match')
    if if_none_match and if_none_match == etag:
        return Response(status=304, headers={'ETag': etag})
    return response
