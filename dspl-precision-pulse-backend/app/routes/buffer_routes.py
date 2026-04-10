from flask import Blueprint, request, jsonify
from app.middleware.auth_middleware import token_required
from app.services.buffer_service import buffer_service

buffer_bp = Blueprint('buffer', __name__, url_prefix='/api/sync/buffer')

@buffer_bp.route('/status', methods=['GET'])
@token_required
def get_buffer_status():
    """Get buffer status"""
    user_count = buffer_service.get_user_buffer_count()
    config_count = buffer_service.get_config_buffer_count()
    return jsonify({
        'user_changes_buffered': user_count,
        'config_changes_buffered': config_count,
        'total_buffered': user_count + config_count
    }), 200

@buffer_bp.route('/user-entries', methods=['GET'])
@token_required
def get_user_entries():
    """Get buffered user changes"""
    entries = buffer_service.get_user_buffer_entries()
    return jsonify(entries), 200

@buffer_bp.route('/config-entries', methods=['GET'])
@token_required
def get_config_entries():
    """Get buffered config changes"""
    entries = buffer_service.get_config_buffer_entries()
    return jsonify(entries), 200

@buffer_bp.route('/flush', methods=['POST'])
@token_required
def flush_buffers():
    """Flush all buffered changes"""
    user_flushed = buffer_service.flush_user_changes()
    config_flushed = buffer_service.flush_config_changes()
    return jsonify({
        'user_changes_flushed': user_flushed,
        'config_changes_flushed': config_flushed,
        'total_flushed': user_flushed + config_flushed
    }), 200

@buffer_bp.route('/cleanup', methods=['POST'])
@token_required
def cleanup_buffers():
    """Clean up old buffered data"""
    days = request.json.get('days', 7) if request.json else 7
    deleted = buffer_service.cleanup_old_buffers(days)
    return jsonify({'deleted': deleted, 'message': f'Cleaned up {deleted} buffers older than {days} days'}), 200
