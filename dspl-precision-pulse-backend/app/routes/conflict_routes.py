"""
Conflict resolution routes
"""

from flask import Blueprint, request, jsonify
from app.middleware.auth_middleware import token_required
from app.models.conflict_log import ConflictLog
from app import db
import logging

logger = logging.getLogger(__name__)

conflict_bp = Blueprint('conflicts', __name__, url_prefix='/api/conflicts')


@conflict_bp.route('', methods=['GET'])
@token_required
def get_conflicts():
    """Get all conflicts"""
    try:
        limit = request.args.get('limit', 100, type=int)
        conflicts = ConflictLog.query.order_by(ConflictLog.created_at.desc()).limit(limit).all()
        
        return jsonify({
            'status': 'success',
            'count': len(conflicts),
            'conflicts': [c.to_dict() for c in conflicts]
        }), 200
    except Exception as e:
        logger.error(f"[CONFLICT] Error getting conflicts: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@conflict_bp.route('/<int:conflict_id>', methods=['GET'])
@token_required
def get_conflict(conflict_id):
    """Get specific conflict"""
    try:
        conflict = ConflictLog.query.get(conflict_id)
        if not conflict:
            return jsonify({'status': 'error', 'message': 'Conflict not found'}), 404
        
        return jsonify({
            'status': 'success',
            'conflict': conflict.to_dict()
        }), 200
    except Exception as e:
        logger.error(f"[CONFLICT] Error getting conflict: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@conflict_bp.route('/<int:conflict_id>/resolve', methods=['POST'])
@token_required
def resolve_conflict(conflict_id):
    """Resolve a conflict"""
    try:
        data = request.get_json()
        resolution = data.get('resolution')  # 'local' or 'remote'
        
        if resolution not in ['local', 'remote']:
            return jsonify({'status': 'error', 'message': 'Invalid resolution'}), 400
        
        conflict = ConflictLog.query.get(conflict_id)
        if not conflict:
            return jsonify({'status': 'error', 'message': 'Conflict not found'}), 404
        
        # Mark conflict as resolved
        conflict.resolution_method = resolution
        conflict.resolved_at = __import__('datetime').datetime.now()
        db.session.commit()
        
        logger.info(f"[CONFLICT] Resolved conflict {conflict_id} with {resolution}")
        
        return jsonify({
            'status': 'success',
            'message': f'Conflict resolved with {resolution} version',
            'conflict': conflict.to_dict()
        }), 200
    except Exception as e:
        logger.error(f"[CONFLICT] Error resolving conflict: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@conflict_bp.route('/by-resource/<resource_type>/<resource_id>', methods=['GET'])
@token_required
def get_conflicts_by_resource(resource_type, resource_id):
    """Get conflicts for a specific resource"""
    try:
        conflicts = ConflictLog.query.filter_by(
            resource_type=resource_type,
            resource_id=str(resource_id)
        ).order_by(ConflictLog.created_at.desc()).all()
        
        return jsonify({
            'status': 'success',
            'count': len(conflicts),
            'conflicts': [c.to_dict() for c in conflicts]
        }), 200
    except Exception as e:
        logger.error(f"[CONFLICT] Error getting conflicts by resource: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
