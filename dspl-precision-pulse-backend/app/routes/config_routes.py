from flask import Blueprint, request, jsonify
from app.models import db
from app.models.system_config import SystemConfig
from app.middleware.auth_middleware import token_required
from datetime import datetime, timezone
import json

config_bp = Blueprint('config', __name__, url_prefix='/api/config')

_CONFIG_NOT_FOUND = 'Configuration not found'

@config_bp.route('/', methods=['GET'])
@token_required
def get_all_configs():
    """Get all configuration settings"""
    try:
        from app.services.cache_service import cache_get, cache_set
        category = request.args.get('category')
        cache_key = f'configs:{category or "all"}'
        cached = cache_get(cache_key)
        if cached:
            return jsonify(cached), 200

        if category:
            configs = SystemConfig.query.filter_by(category=category).all()
        else:
            configs = SystemConfig.query.all()
        max_version = db.session.query(db.func.max(SystemConfig.version)).scalar() or 1
        result = {'configs': [c.to_dict() for c in configs], 'count': len(configs), 'global_version': max_version}
        cache_set(cache_key, result, ttl=60)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@config_bp.route('/<key>', methods=['GET'])
@token_required
def get_config(key):
    """Get specific configuration by key"""
    try:
        config = SystemConfig.query.filter_by(key=key).first()
        
        if not config:
            return jsonify({'error': _CONFIG_NOT_FOUND}), 404
        
        return jsonify({'config': config.to_dict()}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@config_bp.route('/', methods=['POST'])
@token_required
def create_config():
    """Create new configuration setting"""
    try:
        data = request.get_json()
        user = request.user
        
        # Validate required fields
        if not data.get('key') or not data.get('value'):
            return jsonify({'error': 'Key and value are required'}), 400
        
        # Check if key already exists
        existing = SystemConfig.query.filter_by(key=data['key']).first()
        if existing:
            return jsonify({'error': 'Configuration key already exists'}), 400
        
        config = SystemConfig(
            key=data['key'],
            value=str(data['value']),
            description=data.get('description'),
            category=data.get('category', 'general'),
            data_type=data.get('data_type', 'string'),
            is_sensitive=data.get('is_sensitive', False),
            version=1,
            updated_by=user.get('email')
        )
        
        db.session.add(config)
        db.session.commit()
        
        # Broadcast config change via Socket.IO and MQTT
        _broadcast_config_change('created', config)
        
        return jsonify({
            'message': 'Configuration created',
            'config': config.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@config_bp.route('/<key>', methods=['PUT'])
@token_required
def update_config(key):
    """Update existing configuration"""
    # Keys that must not be changed via the web UI
    _READONLY_KEYS = {
        'MQTT_BROKER', 'AUTO_FLUSH_ENABLED', 'SYNC_ENABLED',
        'SYNC_INTERVAL', 'MQTT_USE_TLS'
    }
    if key.upper() in _READONLY_KEYS:
        return jsonify({'error': f'{key} is read-only and cannot be changed via the web UI'}), 403

    try:
        data = request.get_json()
        user = request.user

        config = SystemConfig.query.filter_by(key=key).first()
        if not config:
            return jsonify({'error': _CONFIG_NOT_FOUND}), 404

        old_value = config.value

        # Snapshot into ConfigVersion — use a savepoint so a schema error
        # does NOT roll back the main config update.
        try:
            from app.models.config_version import ConfigVersion
            snapshot = ConfigVersion(
                config_id=config.id,
                version_number=config.version,
                config_data={'value': config.value, 'key': config.key},
                changed_by=user.get('email'),
                change_description=data.get('change_description',
                                            f'Updated by {user.get("email")}'),
            )
            db.session.add(snapshot)
            db.session.flush()   # validate FK before touching config row
        except Exception as cv_err:
            db.session.rollback()   # discard bad snapshot, keep session clean
            print(f'[CONFIG] ConfigVersion snapshot failed (ignored): {cv_err}')

        # Apply updates
        if 'value' in data:
            config.value = str(data['value'])
        if 'description' in data:
            config.description = data['description']
        if 'category' in data:
            config.category = data['category']
        if 'data_type' in data:
            config.data_type = data['data_type']
        if 'is_sensitive' in data:
            config.is_sensitive = data['is_sensitive']

        config.version += 1
        config.updated_by = user.get('email')
        config.updated_at = datetime.now(timezone.utc)

        db.session.commit()

        # Invalidate caches
        try:
            from app.services.cache_service import cache_delete_pattern
            cache_delete_pattern('configs:*')
        except Exception:
            pass
        try:
            from app.services.config_manager import get_config_manager
            get_config_manager().on_config_updated(config.key)
        except Exception:
            pass

        _broadcast_config_change('updated', config, old_value)

        return jsonify({'message': 'Configuration updated', 'config': config.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@config_bp.route('/<key>', methods=['DELETE'])
@token_required
def delete_config(key):
    """Delete configuration"""
    try:
        config = SystemConfig.query.filter_by(key=key).first()
        if not config:
            return jsonify({'error': _CONFIG_NOT_FOUND}), 404
        
        db.session.delete(config)
        db.session.commit()
        
        # Broadcast config deletion via Socket.IO and MQTT
        _broadcast_config_change('deleted', config)
        
        return jsonify({'message': 'Configuration deleted'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@config_bp.route('/bulk-update', methods=['PUT'])
@token_required
def bulk_update_configs():
    """Update multiple configurations at once"""
    try:
        data = request.get_json()
        user = request.user
        configs = data.get('configs', [])
        
        if not configs:
            return jsonify({'error': 'No configurations provided'}), 400
        
        _READONLY_KEYS = {
            'MQTT_BROKER', 'AUTO_FLUSH_ENABLED', 'SYNC_ENABLED',
            'SYNC_INTERVAL', 'MQTT_USE_TLS'
        }
        updated_count = 0
        updated_configs = []

        for config_data in configs:
            key = config_data.get('key')
            value = config_data.get('value')

            if not key or value is None:
                continue
            if key.upper() in _READONLY_KEYS:
                continue   # silently skip read-only keys in bulk updates
            
            config = SystemConfig.query.filter_by(key=key).first()
            if config:
                config.value = str(value)
                config.version += 1
                config.updated_by = user.get('email')
                config.updated_at = datetime.now(timezone.utc)
                updated_count += 1
                updated_configs.append(config)
        
        db.session.commit()
        
        # Broadcast bulk config change
        _broadcast_bulk_config_change(updated_configs)
        
        return jsonify({
            'message': f'Updated {updated_count} configurations',
            'count': updated_count,
            'configs': [c.to_dict() for c in updated_configs]
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@config_bp.route('/categories', methods=['GET'])
@token_required
def get_categories():
    """Get all configuration categories"""
    try:
        categories = db.session.query(SystemConfig.category).distinct().all()
        return jsonify({
            'categories': [cat[0] for cat in categories if cat[0]]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@config_bp.route('/version', methods=['GET'])
@token_required
def get_config_version():
    """Get current global configuration version"""
    try:
        max_version = db.session.query(db.func.max(SystemConfig.version)).scalar() or 1
        return jsonify({
            'version': max_version,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@config_bp.route('/history', methods=['GET'])
@token_required
def get_config_history():
    """Get configuration change history (version log)"""
    try:
        from app.models.config_version import ConfigVersion
        limit = request.args.get('limit', 50, type=int)
        config_key = request.args.get('key')

        query = db.session.query(ConfigVersion, SystemConfig.key).join(
            SystemConfig, ConfigVersion.config_id == SystemConfig.id
        )
        if config_key:
            query = query.filter(SystemConfig.key == config_key)

        rows = query.order_by(ConfigVersion.created_at.desc()).limit(limit).all()
        history = []
        for cv, key in rows:
            entry = cv.to_dict()
            entry['key'] = key
            history.append(entry)

        # If no version history yet, synthesize from current configs (version 1 = initial state)
        if not history:
            configs = SystemConfig.query.all() if not config_key else SystemConfig.query.filter_by(key=config_key).all()
            for c in configs:
                history.append({
                    'id': c.id,
                    'config_id': c.id,
                    'key': c.key,
                    'version_number': c.version,
                    'config_data': {'value': c.value, 'key': c.key},
                    'changed_by': c.updated_by or 'system',
                    'change_description': 'Current value',
                    'created_at': c.updated_at.isoformat() if c.updated_at else c.created_at.isoformat()
                })

        return jsonify({'history': history, 'count': len(history)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@config_bp.route('/rollback/<key>/<int:version_number>', methods=['POST'])
@token_required
def rollback_config(key, version_number):
    """Rollback a config key to a specific version"""
    try:
        from app.models.config_version import ConfigVersion
        user = request.user

        config = SystemConfig.query.filter_by(key=key).first()
        if not config:
            return jsonify({'error': _CONFIG_NOT_FOUND}), 404

        version = ConfigVersion.query.filter_by(
            config_id=config.id, version_number=version_number
        ).first()
        if not version:
            return jsonify({'error': 'Version not found'}), 404

        old_value = config.value
        config.value = str(version.config_data.get('value', config.value))
        config.version += 1
        config.updated_by = user.get('email')
        config.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        _broadcast_config_change('updated', config, old_value)

        return jsonify({
            'message': f'Rolled back {key} to version {version_number}',
            'config': config.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@config_bp.route('/sync-status', methods=['GET'])
@token_required
def get_sync_status():
    """Get configuration sync status for all devices"""
    try:
        max_version = db.session.query(db.func.max(SystemConfig.version)).scalar() or 1
        return jsonify({
            'current_version': max_version,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'devices': []
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def _broadcast_config_change(action, config, old_value=None):
    """Broadcast configuration change via Socket.IO and MQTT"""
    try:
        from app import get_socketio
        
        payload = {
            'action': action,
            'key': config.key,
            'value': config.value,
            'old_value': old_value,
            'category': config.category,
            'data_type': config.data_type,
            'version': config.version,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'updated_by': config.updated_by
        }
        
        # Emit via Socket.IO
        socketio = get_socketio()
        if socketio:
            socketio.emit('config_update', payload, namespace='/')
            print(f"[CONFIG] Emitted {action} for {config.key} via Socket.IO (version {config.version})")
        
        # Publish to MQTT if available
        try:
            from app.services.mqtt_publisher import get_mqtt_publisher
            publisher = get_mqtt_publisher()
            if publisher and publisher.connected:
                topic = 'precisionpulse/config/update'
                publisher._publish(topic, payload)
                print(f"[CONFIG] Broadcasted {action} for {config.key} via MQTT (version {config.version})")
        except Exception as mqtt_err:
            print(f"[CONFIG] MQTT broadcast skipped: {mqtt_err}")
        
    except Exception as e:
        print(f"[CONFIG] Error broadcasting change: {e}")

def _broadcast_bulk_config_change(configs):
    """Broadcast bulk configuration changes"""
    try:
        from app import get_socketio
        
        max_version = max([c.version for c in configs]) if configs else 1
        
        payload = {
            'action': 'bulk_update',
            'configs': [
                {
                    'key': config.key,
                    'value': config.value,
                    'category': config.category,
                    'data_type': config.data_type,
                    'version': config.version
                }
                for config in configs
            ],
            'global_version': max_version,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Emit via Socket.IO
        socketio = get_socketio()
        if socketio:
            socketio.emit('config_bulk_update', payload, namespace='/')
            print(f"[CONFIG] Emitted bulk update via Socket.IO (version {max_version})")
        
        # Publish to MQTT if available
        try:
            from app.services.mqtt_publisher import get_mqtt_publisher
            publisher = get_mqtt_publisher()
            if publisher and publisher.connected:
                topic = 'precisionpulse/config/bulk-update'
                publisher._publish(topic, payload)
                print(f"[CONFIG] Broadcasted bulk update via MQTT (version {max_version})")
        except Exception as mqtt_err:
            print(f"[CONFIG] MQTT broadcast skipped: {mqtt_err}")
        
    except Exception as e:
        print(f"[CONFIG] Error broadcasting bulk change: {e}")
