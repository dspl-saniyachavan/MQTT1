from flask import Blueprint, request, jsonify
from app.controllers.user_controller import UserController
from app.middleware.auth_middleware import token_required, etag_response
from app.services.cache_service import cache_get, cache_set, cache_delete_pattern

user_bp = Blueprint('users', __name__, url_prefix='/api/users')

_CACHE_TTL = 120  # seconds


@user_bp.route('', methods=['GET'])
@token_required
def get_users():
    cache_key = 'users:all'
    cached = cache_get(cache_key)
    if cached is not None:
        resp = jsonify(cached)
        return etag_response(resp)

    result, status = UserController.get_all_users()
    if status == 200:
        cache_set(cache_key, result, ttl=_CACHE_TTL)
    resp = jsonify(result)
    return etag_response(resp) if status == 200 else (resp, status)


@user_bp.route('/online', methods=['GET'])
@token_required
def get_online_users():
    """Return set of emails currently logged in (tracked via login/logout events)."""
    from app.services.online_users_service import get_online_emails
    return jsonify({'online_emails': list(get_online_emails())}), 200


@user_bp.route('', methods=['POST'])
@token_required
def create_user():
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password') or not data.get('name'):
        return jsonify({'error': 'Email, name, and password required'}), 400
    result, status = UserController.create_user(
        data['email'], data['name'], data['password'], data.get('role', 'user')
    )
    if status == 201:
        cache_delete_pattern('users:*')
    return jsonify(result), status


@user_bp.route('/<int:user_id>', methods=['GET'])
@token_required
def get_user(user_id):
    cache_key = f'users:{user_id}'
    cached = cache_get(cache_key)
    if cached is not None:
        resp = jsonify(cached)
        return etag_response(resp)

    from app.models.user import User
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    result = user.to_dict()
    cache_set(cache_key, result, ttl=_CACHE_TTL)
    resp = jsonify(result)
    return etag_response(resp)


@user_bp.route('/<int:user_id>', methods=['PUT'])
@token_required
def update_user(user_id):
    data = request.get_json()
    result, status = UserController.update_user(user_id, **data)
    if status == 200:
        cache_delete_pattern('users:*')
    return jsonify(result), status


@user_bp.route('/<int:user_id>', methods=['DELETE'])
@token_required
def delete_user(user_id):
    result, status = UserController.delete_user(user_id)
    if status == 200:
        cache_delete_pattern('users:*')
    return jsonify(result), status


@user_bp.route('/<int:user_id>/change-password', methods=['POST'])
@token_required
def change_password(user_id):
    data = request.get_json()
    if not data or not data.get('currentPassword') or not data.get('newPassword'):
        return jsonify({'error': 'Current password and new password required'}), 400
    result, status = UserController.change_password(
        user_id, data['currentPassword'], data['newPassword']
    )
    if status == 200:
        cache_delete_pattern('users:*')
    return jsonify(result), status
