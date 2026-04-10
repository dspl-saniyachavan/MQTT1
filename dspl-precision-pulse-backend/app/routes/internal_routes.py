"""
Internal routes for desktop-backend synchronization
These endpoints are called by desktop app to sync data with backend
"""

from flask import Blueprint, request, jsonify
from app.models import db
from app.models.user import User
from app.services.mqtt_publisher import get_mqtt_publisher
from datetime import datetime, timezone, timezone
import logging

logger = logging.getLogger(__name__)

internal_bp = Blueprint('internal', __name__, url_prefix='/api/internal')

@internal_bp.route('/sync-user-password', methods=['POST'])
def sync_user_password():
    """
    Sync password change from desktop to backend.
    Only accepts the new hash if the user explicitly changed their password
    on the desktop (not a default/seeded hash).
    Requires the plaintext current_password to verify identity before accepting.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        email = data.get('email')
        password_hash = data.get('password_hash')
        # Optional: plaintext current password for verification
        current_password = data.get('current_password')

        if not email or not password_hash:
            return jsonify({'error': 'Email and password_hash required'}), 400

        user = User.query.filter_by(email=email).first()
        if not user:
            logger.warning(f"[SYNC] Password sync attempted for non-existent user: {email}")
            return jsonify({'error': 'User not found'}), 404

        # If current_password provided, verify it matches PostgreSQL before accepting new hash
        if current_password:
            if not user.check_password(current_password):
                logger.warning(f"[SYNC] Password sync rejected for {email}: current password mismatch")
                return jsonify({'error': 'Current password verification failed'}), 401
        else:
            # No verification provided — reject to prevent stale hash overwrites
            logger.warning(f"[SYNC] Password sync rejected for {email}: no current_password provided")
            return jsonify({'error': 'current_password required for verification'}), 400

        user.password_hash = password_hash
        user.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        logger.info(f"[SYNC] Password synchronized for user: {email}")
        
        # Broadcast password change event via MQTT
        try:
            publisher = get_mqtt_publisher()
            payload = {
                'event': 'user_password_changed',
                'email': email,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'source': 'desktop'
            }
            publisher._publish('precisionpulse/sync/users/password-changed', payload)
        except Exception as e:
            logger.error(f"[SYNC] Failed to broadcast password change: {e}")
        
        return jsonify({
            'success': True,
            'message': 'Password synchronized successfully',
            'email': email
        }), 200
    
    except Exception as e:
        logger.error(f"[SYNC] Error syncing password: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@internal_bp.route('/sync-user-profile', methods=['POST'])
def sync_user_profile():
    """
    Sync user profile changes from desktop to backend
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        email = data.get('email')
        name = data.get('name')
        
        if not email:
            return jsonify({'error': 'Email required'}), 400
        
        # Find user by email
        user = User.query.filter_by(email=email).first()
        
        if not user:
            logger.warning(f"[SYNC] Profile sync attempted for non-existent user: {email}")
            return jsonify({'error': 'User not found'}), 404
        
        # Update profile fields
        if name:
            user.name = name
        
        user.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        logger.info(f"[SYNC] Profile synchronized for user: {email}")
        
        # Broadcast profile change event via MQTT
        try:
            publisher = get_mqtt_publisher()
            payload = {
                'event': 'user_profile_changed',
                'email': email,
                'name': name,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'source': 'desktop'
            }
            publisher._publish('precisionpulse/sync/users/profile-changed', payload)
        except Exception as e:
            logger.error(f"[SYNC] Failed to broadcast profile change: {e}")
        
        return jsonify({
            'success': True,
            'message': 'Profile synchronized successfully',
            'email': email
        }), 200
    
    except Exception as e:
        logger.error(f"[SYNC] Error syncing profile: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@internal_bp.route('/sync-status', methods=['GET'])
def get_sync_status():
    """
    Get synchronization status
    """
    try:
        return jsonify({
            'status': 'online',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'version': '1.0'
        }), 200
    except Exception as e:
        logger.error(f"[SYNC] Error getting sync status: {e}")
        return jsonify({'error': str(e)}), 500

@internal_bp.route('/parameters', methods=['GET'])
def get_parameters():
    """
    Get all parameters for desktop app (no auth required)
    """
    try:
        from app.models.parameter import Parameter
        parameters = Parameter.query.order_by(Parameter.created_at.desc()).all()
        return jsonify({
            'parameters': [param.to_dict() for param in parameters]
        }), 200
    except Exception as e:
        logger.error(f"[INTERNAL] Error fetching parameters: {e}")
        return jsonify({'error': str(e)}), 500

@internal_bp.route('/sync-user', methods=['POST'])
def sync_user():
    """
    Sync user from desktop to backend (create or update)
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        email = data.get('email')
        name = data.get('name')
        password_hash = data.get('password_hash')
        role = data.get('role', 'user')

        if not email or not name:
            return jsonify({'error': 'Email and name required'}), 400

        user = User.query.filter_by(email=email).first()
        if user:
            user.name = name
            user.role = role
            if password_hash:
                user.password_hash = password_hash
            user.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            logger.info(f"[SYNC] User updated: {email}")
            return jsonify({'success': True, 'message': 'User updated', 'user': user.to_dict()}), 200
        else:
            user = User(email=email, name=name, password_hash=password_hash or '', role=role, is_active=True)
            db.session.add(user)
            db.session.commit()
            logger.info(f"[SYNC] User created: {email}")
            return jsonify({'success': True, 'message': 'User created', 'user': user.to_dict()}), 201
    except Exception as e:
        logger.error(f"[SYNC] Error syncing user: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@internal_bp.route('/sync-user-role', methods=['PUT'])
def sync_user_role():
    """
    Sync user role change from desktop to backend
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        email = data.get('email')
        role = data.get('role')

        if not email or not role:
            return jsonify({'error': 'Email and role required'}), 400

        user = User.query.filter_by(email=email).first()
        if not user:
            logger.warning(f"[SYNC] Role sync attempted for non-existent user: {email}")
            return jsonify({'error': 'User not found'}), 404

        old_role = user.role
        user.role = role
        user.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        logger.info(f"[SYNC] User role updated: {email} ({old_role} -> {role})")

        try:
            publisher = get_mqtt_publisher()
            payload = {'type': 'role_changed', 'email': email, 'old_role': old_role, 'new_role': role, 'timestamp': datetime.now(timezone.utc).isoformat(), 'source': 'desktop'}
            publisher._publish('precisionpulse/sync/roles/changed', payload)
        except Exception as e:
            logger.error(f"[SYNC] Failed to broadcast role change: {e}")

        return jsonify({'success': True, 'message': 'User role updated', 'email': email, 'old_role': old_role, 'new_role': role}), 200
    except Exception as e:
        logger.error(f"[SYNC] Error syncing user role: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@internal_bp.route('/sync-user-delete', methods=['DELETE'])
def sync_user_delete():
    """
    Sync user deletion from desktop to backend
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        email = data.get('email')
        if not email:
            return jsonify({'error': 'Email required'}), 400

        user = User.query.filter_by(email=email).first()
        if not user:
            logger.warning(f"[SYNC] Delete attempted for non-existent user: {email}")
            return jsonify({'error': 'User not found'}), 404

        db.session.delete(user)
        db.session.commit()
        logger.info(f"[SYNC] User deleted: {email}")

        try:
            publisher = get_mqtt_publisher()
            payload = {'type': 'user_deleted', 'email': email, 'timestamp': datetime.now(timezone.utc).isoformat(), 'source': 'desktop'}
            publisher._publish('precisionpulse/sync/users/deleted', payload)
        except Exception as e:
            logger.error(f"[SYNC] Failed to broadcast user deletion: {e}")

        return jsonify({'success': True, 'message': 'User deleted', 'email': email}), 200
    except Exception as e:
        logger.error(f"[SYNC] Error deleting user: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@internal_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint for desktop app
    """
    try:
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 200
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500
