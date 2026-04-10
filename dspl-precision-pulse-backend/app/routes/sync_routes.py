from flask import Blueprint, jsonify
from app.services.sync_service import sync_service
from app.middleware.auth_middleware import token_required

sync_bp = Blueprint('sync', __name__, url_prefix='/api/sync')

@sync_bp.route('/to-sqlite', methods=['POST'])
@token_required
def sync_to_sqlite():
    """Sync PostgreSQL data to SQLite"""
    try:
        sync_service.full_sync_to_sqlite()
        return jsonify({'message': 'Sync to SQLite completed successfully'}), 200
    except Exception as e:
        return jsonify({'error': f'Sync failed: {str(e)}'}), 500

@sync_bp.route('/from-sqlite', methods=['POST'])
@token_required
def sync_from_sqlite():
    """Sync SQLite data to PostgreSQL"""
    try:
        sync_service.full_sync_from_sqlite()
        return jsonify({'message': 'Sync from SQLite completed successfully'}), 200
    except Exception as e:
        return jsonify({'error': f'Sync failed: {str(e)}'}), 500