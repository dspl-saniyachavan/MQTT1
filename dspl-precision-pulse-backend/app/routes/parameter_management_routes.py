"""
Parameter management API routes
"""
from flask import Blueprint, request, jsonify
from app.middleware.auth_middleware import token_required

_PARAM_NOT_FOUND = 'Parameter not found'
from app.services.parameter_management_service import get_parameter_management_service, ParameterType
from app.models.parameter import Parameter
from app.models import db
from flask import g

param_bp = Blueprint('parameters', __name__, url_prefix='/api/parameters')
param_mgmt = get_parameter_management_service()

@param_bp.route('', methods=['GET'])
@token_required
def get_parameters():
    """Get all parameters"""
    try:
        params = Parameter.query.all()
        return jsonify([p.to_dict() for p in params]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@param_bp.route('', methods=['POST'])
@token_required
def create_parameter():
    """Create a new parameter"""
    try:
        data = request.get_json()
        
        if not data or not data.get('name') or not data.get('type'):
            return jsonify({'error': 'Name and type required'}), 400
        
        # Validate type
        try:
            param_type = ParameterType(data['type'])
        except ValueError:
            return jsonify({'error': f"Invalid type. Must be one of: {[t.value for t in ParameterType]}"}), 400
        
        # Create in database
        param = Parameter(
            name=data['name'],
            type=data['type'],
            value=data.get('value'),
            min_value=data.get('min_value'),
            max_value=data.get('max_value'),
            allowed_values=data.get('allowed_values'),
            description=data.get('description')
        )
        
        db.session.add(param)
        db.session.commit()
        
        # Log audit
        from app.services.audit_logging_service import get_audit_logging_service
        audit_service = get_audit_logging_service()
        actor_email = g.user.get('email') if hasattr(g, 'user') else None
        audit_service.log_event(
            event_type='parameter_created',
            action='create',
            resource_type='parameter',
            resource_id=str(param.id),
            resource_name=param.name,
            actor_email=actor_email,
            status='success'
        )
        
        return jsonify(param.to_dict()), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@param_bp.route('/<int:param_id>', methods=['GET'])
@token_required
def get_parameter(param_id):
    """Get parameter by ID"""
    try:
        param = Parameter.query.get(param_id)
        if not param:
            return jsonify({'error': _PARAM_NOT_FOUND}), 404
        return jsonify(param.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@param_bp.route('/<int:param_id>', methods=['PUT'])
@token_required
def update_parameter(param_id):
    """Update parameter value"""
    try:
        data = request.get_json()
        param = Parameter.query.get(param_id)
        
        if not param:
            return jsonify({'error': _PARAM_NOT_FOUND}), 404
        
        # Validate new value if provided
        if 'value' in data:
            param_type = ParameterType(param.type)
            from app.services.parameter_management_service import ParameterValidator
            valid, error = ParameterValidator.validate(
                data['value'], param_type, param.min_value, param.max_value, param.allowed_values
            )
            if not valid:
                return jsonify({'error': error}), 400
            
            param.value = data['value']
        
        # Update other fields
        if 'name' in data:
            param.name = data['name']
        if 'description' in data:
            param.description = data['description']
        
        db.session.commit()
        
        # Log audit
        from app.services.audit_logging_service import get_audit_logging_service
        audit_service = get_audit_logging_service()
        actor_email = g.user.get('email') if hasattr(g, 'user') else None
        audit_service.log_event(
            event_type='parameter_updated',
            action='update',
            resource_type='parameter',
            resource_id=str(param.id),
            resource_name=param.name,
            actor_email=actor_email,
            status='success'
        )
        
        return jsonify(param.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@param_bp.route('/<int:param_id>', methods=['DELETE'])
@token_required
def delete_parameter(param_id):
    """Delete parameter"""
    try:
        param = Parameter.query.get(param_id)
        if not param:
            return jsonify({'error': _PARAM_NOT_FOUND}), 404
        
        param_name = param.name
        db.session.delete(param)
        db.session.commit()
        
        # Log audit
        from app.services.audit_logging_service import get_audit_logging_service
        audit_service = get_audit_logging_service()
        actor_email = g.user.get('email') if hasattr(g, 'user') else None
        audit_service.log_event(
            event_type='parameter_deleted',
            action='delete',
            resource_type='parameter',
            resource_id=str(param_id),
            resource_name=param_name,
            actor_email=actor_email,
            status='success'
        )
        
        return jsonify({'message': 'Parameter deleted'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@param_bp.route('/<int:param_id>/history', methods=['GET'])
@token_required
def get_parameter_history(param_id):
    """Get parameter change history"""
    try:
        from app.models.parameter_history import ParameterHistory
        
        limit = request.args.get('limit', 100, type=int)
        history = ParameterHistory.query.filter_by(parameter_id=param_id).order_by(
            ParameterHistory.created_at.desc()
        ).limit(limit).all()
        
        return jsonify([h.to_dict() for h in history]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@param_bp.route('/<int:param_id>/alerts', methods=['POST'])
@token_required
def create_parameter_alert(param_id):
    """Create alert for parameter"""
    try:
        data = request.get_json()
        
        if not data or not data.get('threshold') or not data.get('condition'):
            return jsonify({'error': 'Threshold and condition required'}), 400
        
        from app.models.parameter_alert import ParameterAlert
        
        alert = ParameterAlert(
            parameter_id=param_id,
            threshold=data['threshold'],
            condition=data['condition'],
            enabled=data.get('enabled', True)
        )
        
        db.session.add(alert)
        db.session.commit()
        
        return jsonify(alert.to_dict()), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@param_bp.route('/<int:param_id>/alerts', methods=['GET'])
@token_required
def get_parameter_alerts(param_id):
    """Get alerts for parameter"""
    try:
        from app.models.parameter_alert import ParameterAlert
        
        alerts = ParameterAlert.query.filter_by(parameter_id=param_id).all()
        return jsonify([a.to_dict() for a in alerts]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
