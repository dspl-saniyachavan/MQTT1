"""Telemetry report generation routes"""
from flask import Blueprint, request, jsonify
from app.models.telemetry import Telemetry
from app.models.parameter import Parameter
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

report_bp = Blueprint('telemetry_report', __name__, url_prefix='/api/reports/telemetry-data')

@report_bp.route('/telemetry', methods=['POST'])
def generate_telemetry_report():
    """Generate report for single parameter"""
    try:
        data = request.get_json()
        parameter_name = data.get('parameter_name')
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        
        if not all([parameter_name, start_time, end_time]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Parse dates
        start = datetime.fromisoformat(start_time)
        end = datetime.fromisoformat(end_time)
        
        # Get parameter
        param = Parameter.query.filter_by(name=parameter_name).first()
        if not param:
            return jsonify({'error': 'Parameter not found'}), 404
        
        # Query telemetry data
        telemetry = Telemetry.query.filter(
            Telemetry.parameter_id == param.id,
            Telemetry.timestamp >= start,
            Telemetry.timestamp <= end
        ).order_by(Telemetry.timestamp).all()
        
        if not telemetry:
            return jsonify({'error': 'No data found for period'}), 404
        
        # Calculate statistics
        values = [t.value for t in telemetry]
        stats = {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'avg': sum(values) / len(values),
            'sum': sum(values)
        }
        
        report = {
            'id': 1,
            'parameter_name': parameter_name,
            'parameter_unit': param.unit,
            'start_time': start_time,
            'end_time': end_time,
            'statistics': stats,
            'data_points': len(telemetry),
            'created_at': datetime.now().isoformat()
        }
        
        logger.info(f"[REPORT] Generated report for {parameter_name}")
        return jsonify(report), 200
    except Exception as e:
        logger.error(f"[REPORT] Error generating report: {e}")
        return jsonify({'error': str(e)}), 500

@report_bp.route('/telemetry/multi', methods=['POST'])
def generate_multi_parameter_report():
    """Generate report for multiple parameters"""
    try:
        data = request.get_json()
        parameter_names = data.get('parameter_names', [])
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        
        if not all([parameter_names, start_time, end_time]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        start = datetime.fromisoformat(start_time)
        end = datetime.fromisoformat(end_time)
        
        reports = []
        for param_name in parameter_names:
            param = Parameter.query.filter_by(name=param_name).first()
            if not param:
                continue
            
            telemetry = Telemetry.query.filter(
                Telemetry.parameter_id == param.id,
                Telemetry.timestamp >= start,
                Telemetry.timestamp <= end
            ).all()
            
            if telemetry:
                values = [t.value for t in telemetry]
                reports.append({
                    'parameter_name': param_name,
                    'parameter_unit': param.unit,
                    'statistics': {
                        'count': len(values),
                        'min': min(values),
                        'max': max(values),
                        'avg': sum(values) / len(values)
                    }
                })
        
        logger.info(f"[REPORT] Generated multi-parameter report for {len(reports)} parameters")
        return jsonify({
            'id': 1,
            'start_time': start_time,
            'end_time': end_time,
            'parameters': reports,
            'created_at': datetime.now().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"[REPORT] Error generating multi-parameter report: {e}")
        return jsonify({'error': str(e)}), 500
