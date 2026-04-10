from flask import Blueprint, request, jsonify
from app.middleware.auth_middleware import token_required
from app.services.permission_service import permission_service
from app.services.mqtt_publisher import get_mqtt_publisher

permission_bp = Blueprint('permissions', __name__, url_prefix='/api/permissions')

@permission_bp.route('/<role>', methods=['GET'])
@token_required
def get_role_permissions(role):
    """Get all permissions for a role"""
    perms = permission_service.get_permissions(role)
    return jsonify({'role': role, 'permissions': perms}), 200

@permission_bp.route('', methods=['POST'])
@token_required
def create_permission():
    """Create new permission"""
    data = request.get_json()
    
    if not data or not data.get('role') or not data.get('resource') or not data.get('action'):
        return jsonify({'error': 'role, resource, and action required'}), 400
    
    success = permission_service.set_permission(
        data['role'],
        data['resource'],
        data['action'],
        data.get('allowed', True)
    )
    
    if success:
        # Publish permission change via MQTT
        try:
            mqtt_pub = get_mqtt_publisher()
            perms = permission_service.get_permissions(data['role'])
            mqtt_pub.publish_permission_changed(data['role'], perms)
        except Exception as e:
            print(f"Error publishing permission change: {e}")
        
        return jsonify({'message': 'Permission created'}), 201
    return jsonify({'error': 'Failed to create permission'}), 500

@permission_bp.route('/<role>/<resource>/<action>', methods=['DELETE'])
@token_required
def delete_permission(role, resource, action):
    """Delete permission"""
    success = permission_service.delete_permission(role, resource, action)
    
    if success:
        # Publish permission change via MQTT
        try:
            mqtt_pub = get_mqtt_publisher()
            perms = permission_service.get_permissions(role)
            mqtt_pub.publish_permission_changed(role, perms)
        except Exception as e:
            print(f"Error publishing permission change: {e}")
        
        return jsonify({'message': 'Permission deleted'}), 200
    return jsonify({'error': 'Failed to delete permission'}), 500

@permission_bp.route('/init-defaults', methods=['POST'])
@token_required
def init_defaults():
    """Initialize default permissions"""
    permission_service.init_default_permissions()
    return jsonify({'message': 'Default permissions initialized'}), 200
