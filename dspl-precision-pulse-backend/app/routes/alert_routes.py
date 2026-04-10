from flask import Blueprint, request, jsonify
from app.middleware.auth_middleware import token_required
from app.services.alert_service import AlertService

alert_bp = Blueprint('alerts', __name__, url_prefix='/api/alerts')


@alert_bp.route('', methods=['GET'])
@token_required
def get_active_alerts():
    return jsonify({'alerts': AlertService.get_active_alerts()}), 200


@alert_bp.route('', methods=['POST'])
@token_required
def create_alert():
    data = request.get_json() or {}
    parameter_id = data.get('parameter_id')
    alert_type   = data.get('alert_type')
    threshold    = data.get('threshold')
    message      = data.get('message')

    if not all([parameter_id, alert_type, threshold is not None]):
        return jsonify({'error': 'parameter_id, alert_type and threshold are required'}), 400

    alert = AlertService.create_alert(parameter_id, alert_type, float(threshold), message)
    return jsonify({'alert': alert.to_dict()}), 201


@alert_bp.route('/<int:alert_id>', methods=['DELETE'])
@token_required
def delete_alert(alert_id):
    if AlertService.delete_alert(alert_id):
        return jsonify({'message': 'Alert deleted'}), 200
    return jsonify({'error': 'Alert not found'}), 404


@alert_bp.route('/<int:alert_id>/disable', methods=['POST'])
@token_required
def disable_alert(alert_id):
    if AlertService.disable_alert(alert_id):
        return jsonify({'message': 'Alert disabled'}), 200
    return jsonify({'error': 'Alert not found'}), 404


@alert_bp.route('/triggered', methods=['GET'])
@token_required
def get_triggered_alerts():
    hours = request.args.get('hours', 24, type=int)
    return jsonify({'alerts': AlertService.get_triggered_alerts(hours)}), 200


@alert_bp.route('/parameter/<int:parameter_id>', methods=['GET'])
@token_required
def get_parameter_alerts(parameter_id):
    return jsonify({'alerts': AlertService.get_parameter_alerts(parameter_id)}), 200


@alert_bp.route('/check', methods=['POST'])
@token_required
def check_alert():
    """Manually check a value against alerts for a parameter."""
    data = request.get_json() or {}
    parameter_id   = data.get('parameter_id')
    current_value  = data.get('value')
    parameter_name = data.get('parameter_name')

    if parameter_id is None or current_value is None:
        return jsonify({'error': 'parameter_id and value are required'}), 400

    triggered = AlertService.check_alert(parameter_id, float(current_value), parameter_name)
    return jsonify({'triggered': triggered, 'count': len(triggered)}), 200
