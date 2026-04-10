"""
Sync status routes for monitoring and debugging sync issues
"""

from flask import Blueprint, jsonify, request
from app.middleware.auth import token_required
from app.services.sync_verification_service import get_sync_verification_service
from app.services.buffer_service import buffer_service
import logging

logger = logging.getLogger(__name__)

sync_status_bp = Blueprint('sync_status', __name__, url_prefix='/api/sync')


@sync_status_bp.route('/status', methods=['GET'])
@token_required
def get_sync_status(current_user):
    """Get overall sync status"""
    try:
        verifier = get_sync_verification_service()
        status = verifier.get_sync_status()
        
        # Add buffer status
        buffer_status = {
            'user_changes_buffered': buffer_service.get_user_buffer_count(),
            'config_changes_buffered': buffer_service.get_config_buffer_count(),
            'total_buffered': buffer_service.get_total_buffer_count()
        }
        
        return jsonify({
            'status': 'success',
            'sync': status,
            'buffer': buffer_status,
            'timestamp': __import__('datetime').datetime.now().isoformat()
        }), 200
    
    except Exception as e:
        logger.error(f"[SYNC_STATUS] Error getting sync status: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@sync_status_bp.route('/messages/pending', methods=['GET'])
@token_required
def get_pending_messages(current_user):
    """Get pending MQTT messages"""
    try:
        verifier = get_sync_verification_service()
        pending = verifier.get_pending_messages()
        
        return jsonify({
            'status': 'success',
            'count': len(pending),
            'messages': pending
        }), 200
    
    except Exception as e:
        logger.error(f"[SYNC_STATUS] Error getting pending messages: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@sync_status_bp.route('/messages/unacknowledged', methods=['GET'])
@token_required
def get_unacknowledged_messages(current_user):
    """Get unacknowledged messages (potential sync issues)"""
    try:
        timeout = request.args.get('timeout', 30, type=int)
        verifier = get_sync_verification_service()
        unacked = verifier.get_unacknowledged_messages(timeout)
        
        return jsonify({
            'status': 'success',
            'count': len(unacked),
            'timeout_seconds': timeout,
            'messages': unacked
        }), 200
    
    except Exception as e:
        logger.error(f"[SYNC_STATUS] Error getting unacknowledged messages: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@sync_status_bp.route('/messages/<msg_id>', methods=['GET'])
@token_required
def get_message_status(current_user, msg_id):
    """Get status of a specific message"""
    try:
        verifier = get_sync_verification_service()
        msg_status = verifier.get_message_status(msg_id)
        
        if not msg_status:
            return jsonify({'status': 'error', 'message': 'Message not found'}), 404
        
        return jsonify({
            'status': 'success',
            'msg_id': msg_id,
            'message': msg_status
        }), 200
    
    except Exception as e:
        logger.error(f"[SYNC_STATUS] Error getting message status: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@sync_status_bp.route('/buffer/flush', methods=['POST'])
@token_required
def flush_buffer(current_user):
    """Manually flush buffered changes"""
    try:
        user_count = buffer_service.flush_user_changes()
        config_count = buffer_service.flush_config_changes()
        
        return jsonify({
            'status': 'success',
            'user_changes_flushed': user_count,
            'config_changes_flushed': config_count,
            'total_flushed': user_count + config_count
        }), 200
    
    except Exception as e:
        logger.error(f"[SYNC_STATUS] Error flushing buffer: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@sync_status_bp.route('/buffer/status', methods=['GET'])
@token_required
def get_buffer_status(current_user):
    """Get buffer status"""
    try:
        return jsonify({
            'status': 'success',
            'user_changes_buffered': buffer_service.get_user_buffer_count(),
            'config_changes_buffered': buffer_service.get_config_buffer_count(),
            'total_buffered': buffer_service.get_total_buffer_count()
        }), 200
    
    except Exception as e:
        logger.error(f"[SYNC_STATUS] Error getting buffer status: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@sync_status_bp.route('/health', methods=['GET'])
def get_sync_health():
    """Get sync health (no auth required for monitoring)"""
    try:
        verifier = get_sync_verification_service()
        status = verifier.get_sync_status()
        
        # Determine health based on success rate
        if status['success_rate'] >= 95:
            health = 'healthy'
        elif status['success_rate'] >= 80:
            health = 'degraded'
        else:
            health = 'unhealthy'
        
        return jsonify({
            'status': 'success',
            'health': health,
            'sync': status
        }), 200
    
    except Exception as e:
        logger.error(f"[SYNC_STATUS] Error getting sync health: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
