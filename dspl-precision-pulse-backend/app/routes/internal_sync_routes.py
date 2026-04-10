"""Internal sync routes for desktop-to-backend communication"""
from flask import Blueprint, request, jsonify
from app.models import db
from app.models.user import User
from app.middleware.auth_middleware import token_required
import logging

logger = logging.getLogger(__name__)

internal_sync_bp = Blueprint('internal_sync', __name__, url_prefix='/api/internal')

@internal_sync_bp.route('/sync-user', methods=['POST'])
def sync_user():
    """Sync user from desktop to backend.
    IMPORTANT: password_hash is intentionally NOT synced from desktop → backend.
    PostgreSQL is the source of truth for passwords. The desktop hash may differ
    (argon2 vs bcrypt, or stale hash) and overwriting it would break web login.
    """
    try:
        data = request.get_json()
        email = data.get('email')
        name = data.get('name')
        role = data.get('role', 'user')
        is_active = data.get('is_active', True)
        # password_hash intentionally ignored — never overwrite PostgreSQL hash

        if not email:
            return jsonify({'error': 'Email required'}), 400

        user = User.query.filter_by(email=email).first()

        if user:
            user.name = name or user.name
            user.role = role
            user.is_active = is_active
            # Do NOT touch user.password_hash
            logger.info(f"[SYNC] Updated user {email} (password unchanged)")
        else:
            user = User(
                email=email,
                name=name or email.split('@')[0],
                role=role,
                is_active=is_active
            )
            # New user from desktop — set a random unusable password.
            # They must use the web app to set a real password.
            import bcrypt as _bcrypt, secrets
            user.password_hash = _bcrypt.hashpw(secrets.token_bytes(32), _bcrypt.gensalt()).decode('utf-8')
            db.session.add(user)
            logger.info(f"[SYNC] Created user {email} with random password (set via web app)")

        db.session.commit()

        # Broadcast to frontend via Socket.IO
        try:
            from app import get_socketio
            sio = get_socketio()
            if sio:
                sio.emit('user_created' if not user else 'user_updated',
                         {'user': {'id': user.id, 'email': user.email,
                                   'name': user.name, 'role': user.role,
                                   'is_active': user.is_active}}, namespace='/')
        except Exception:
            pass

        return jsonify({'message': 'User synced', 'user': {
            'id': user.id, 'email': user.email,
            'name': user.name, 'role': user.role, 'is_active': user.is_active
        }}), 200
    except Exception as e:
        logger.error(f"[SYNC] Error syncing user: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@internal_sync_bp.route('/sync-user-role', methods=['PUT'])
def sync_user_role():
    """Update user role from desktop - no auth required (internal desktop call)"""
    try:
        data = request.get_json()
        email = data.get('email')
        role = data.get('role')

        if not email or not role:
            return jsonify({'error': 'Email and role required'}), 400

        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        user.role = role
        db.session.commit()
        logger.info(f"[SYNC] Updated role for {email} to {role}")

        try:
            from app import get_socketio
            sio = get_socketio()
            if sio:
                sio.emit('user_updated', {'user': {'id': user.id, 'email': user.email,
                                                    'name': user.name, 'role': user.role,
                                                    'is_active': user.is_active}}, namespace='/')
        except Exception:
            pass

        return jsonify({'message': 'Role updated', 'user': {
            'id': user.id, 'email': user.email, 'role': user.role
        }}), 200
    except Exception as e:
        logger.error(f"[SYNC] Error updating role: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@internal_sync_bp.route('/sync-user-delete', methods=['DELETE'])
def sync_user_delete():
    """Delete user from backend - no auth required (internal desktop call)"""
    try:
        data = request.get_json()
        email = data.get('email')

        if not email:
            return jsonify({'error': 'Email required'}), 400

        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        user_id = user.id
        db.session.delete(user)
        db.session.commit()
        logger.info(f"[SYNC] Deleted user {email}")

        try:
            from app import get_socketio
            sio = get_socketio()
            if sio:
                sio.emit('user_deleted', {'user_id': user_id, 'email': email}, namespace='/')
        except Exception:
            pass

        return jsonify({'message': 'User deleted'}), 200
    except Exception as e:
        logger.error(f"[SYNC] Error deleting user: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@internal_sync_bp.route('/get-all-users', methods=['GET'])
@token_required
def get_all_users():
    """Get all users - Admin only"""
    try:
        current_user = request.user
        # Check admin permission
        if current_user.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        users = User.query.all()
        return jsonify({
            'users': [{
                'id': u.id,
                'email': u.email,
                'name': u.name,
                'role': u.role,
                'is_active': u.is_active,
                'created_at': u.created_at.isoformat() if u.created_at else None
            } for u in users]
        }), 200
    except Exception as e:
        logger.error(f"[SYNC] Error fetching users: {e}")
        return jsonify({'error': str(e)}), 500
