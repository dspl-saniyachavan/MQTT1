_MIME_CSV = 'text/csv'
from flask import Blueprint, request, jsonify, send_file, Response, stream_with_context
from app.middleware.auth_middleware import token_required
from app.services.report_service import report_service
from flask import g
import io
import json

report_bp = Blueprint('reports', __name__, url_prefix='/api/reports')


@report_bp.route('/parameter-history', methods=['GET'])
@token_required
def get_parameter_history():
    """Get time-series history for one or more parameters within a date range"""
    from app.models.parameter_stream import ParameterStream
    from app.models.parameter import Parameter
    from app.models import db
    from datetime import datetime

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    param_ids = request.args.getlist('param_ids', type=int)
    limit = request.args.get('limit', 500, type=int)

    try:
        start_dt = datetime.fromisoformat(start_date.rstrip('Z')) if start_date else None
        end_dt = datetime.fromisoformat(end_date.rstrip('Z')) if end_date else None
    except Exception:
        return jsonify({'error': 'Invalid date format'}), 400

    query = db.session.query(ParameterStream)
    if start_dt:
        query = query.filter(ParameterStream.timestamp >= start_dt)
    if end_dt:
        query = query.filter(ParameterStream.timestamp <= end_dt)
    if param_ids:
        query = query.filter(ParameterStream.parameter_id.in_(param_ids))

    records = query.order_by(ParameterStream.timestamp.asc()).limit(limit).all()

    param_names = {p.id: {'name': p.name, 'unit': p.unit} for p in Parameter.query.all()}

    # Group by parameter_id
    grouped: dict = {}
    for r in records:
        pid = r.parameter_id
        if pid not in grouped:
            grouped[pid] = {
                'parameter_id': pid,
                'name': param_names.get(pid, {}).get('name', str(pid)),
                'unit': param_names.get(pid, {}).get('unit', ''),
                'data': []
            }
        grouped[pid]['data'].append({'t': r.timestamp.isoformat(), 'v': r.value})

    return jsonify({'series': list(grouped.values()), 'count': len(records)}), 200

@report_bp.route('/dashboard', methods=['GET'])
@token_required
def get_dashboard_report():
    """Generate a full dashboard report from parameter_stream data"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    report_data = report_service.generate_dashboard_report(start_date, end_date)
    return jsonify(report_data), 200

@report_bp.route('/dashboard/export/json', methods=['GET'])
@token_required
def export_dashboard_json():
    """Export dashboard report as JSON file"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    report_data = report_service.generate_dashboard_report(start_date, end_date)
    json_str = report_service.export_report_json(report_data)
    return send_file(
        io.BytesIO(json_str.encode()),
        mimetype='application/json',
        as_attachment=True,
        download_name='dashboard_report.json'
    )

@report_bp.route('/dashboard/export/csv', methods=['GET'])
@token_required
def export_dashboard_csv():
    """Export dashboard report as CSV file"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    report_data = report_service.generate_dashboard_report(start_date, end_date)
    csv_str = report_service.export_report_csv(report_data)
    return send_file(
        io.BytesIO(csv_str.encode()),
        mimetype=_MIME_CSV,
        as_attachment=True,
        download_name='dashboard_report.csv'
    )

# ------------------------------------------------------------------
# Full report: data points + trends + alerts + comparison
# ------------------------------------------------------------------

@report_bp.route('/full', methods=['GET'])
@token_required
def get_full_report():
    """Full report: streamed data points, trends, alerts, comparison"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = request.args.get('limit', 500, type=int)
    report = report_service.generate_full_report(start_date, end_date, limit)
    return jsonify(report), 200


@report_bp.route('/full/stream', methods=['GET'])
def stream_full_report():
    """SSE stream of data points for the report page (token via query param for EventSource)"""
    from app.utils.jwt_utils import verify_token
    from flask import g
    token = request.args.get('token') or (request.headers.get('Authorization', '').split(' ')[-1])
    if not token:
        return jsonify({'error': 'Token missing'}), 401
    payload = verify_token(token)
    if not payload:
        return jsonify({'error': 'Invalid or expired token'}), 401
    g.user = payload
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = request.args.get('limit', 500, type=int)

    def generate():
        report = report_service.generate_full_report(start_date, end_date, limit)
        # Stream meta first
        yield f"data: {json.dumps({'type': 'meta', 'total_data_points': report['total_data_points'], 'generated_at': report['generated_at'], 'start_date': report['start_date'], 'end_date': report['end_date']})}\n\n"
        # Stream data points one by one
        for dp in report['data_points']:
            yield f"data: {json.dumps({'type': 'data_point', 'payload': dp})}\n\n"
        # Send trends, alerts, comparison as single events
        yield f"data: {json.dumps({'type': 'trends', 'payload': report['trends']})}\n\n"
        yield f"data: {json.dumps({'type': 'alerts', 'payload': report['alerts']})}\n\n"
        yield f"data: {json.dumps({'type': 'comparison', 'payload': report['comparison']})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )


@report_bp.route('/full/export/csv', methods=['GET'])
@token_required
def export_full_csv():
    """Export full report as CSV"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = request.args.get('limit', 500, type=int)
    report = report_service.generate_full_report(start_date, end_date, limit)
    csv_str = report_service.export_full_report_csv(report)
    return send_file(
        io.BytesIO(csv_str.encode()),
        mimetype=_MIME_CSV,
        as_attachment=True,
        download_name='precisionpulse_report.csv'
    )


@report_bp.route('/full/export/pdf', methods=['GET'])
@token_required
def export_full_pdf():
    """Export full report as PDF"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = request.args.get('limit', 500, type=int)
    report = report_service.generate_full_report(start_date, end_date, limit)
    pdf_bytes = report_service.export_full_report_pdf(report)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name='precisionpulse_report.pdf'
    )


@report_bp.route('/templates', methods=['GET'])
@token_required
def get_templates():
    """Get all report templates"""
    include_private = request.args.get('include_private', 'false').lower() == 'true'
    templates = report_service.get_templates(include_private)
    return jsonify({'templates': templates}), 200

@report_bp.route('/templates', methods=['POST'])
@token_required
def create_template():
    """Create new report template"""
    data = request.get_json()
    if not data or not data.get('name') or not data.get('template_config'):
        return jsonify({'error': 'name and template_config required'}), 400
    actor_email = g.user.get('email') if hasattr(g, 'user') else None
    result = report_service.create_template(
        data['name'], data.get('description', ''), data['template_config'],
        actor_email, data.get('is_public', False)
    )
    if result:
        return jsonify(result), 201
    return jsonify({'error': 'Failed to create template'}), 500

@report_bp.route('/generate/<int:template_id>', methods=['POST'])
@token_required
def generate_report(template_id):
    """Generate report from template"""
    data = request.get_json() or {}
    report_data = report_service.generate_report(template_id, data.get('start_date'), data.get('end_date'))
    if report_data:
        return jsonify(report_data), 200
    return jsonify({'error': 'Failed to generate report'}), 500

@report_bp.route('/export/<int:template_id>/json', methods=['POST'])
@token_required
def export_json(template_id):
    """Export report as JSON"""
    data = request.get_json() or {}
    report_data = report_service.generate_report(template_id, data.get('start_date'), data.get('end_date'))
    if report_data:
        json_str = report_service.export_report_json(report_data)
        return send_file(
            io.BytesIO(json_str.encode()), mimetype='application/json',
            as_attachment=True, download_name=f'report_{template_id}.json'
        )
    return jsonify({'error': 'Failed to export report'}), 500

@report_bp.route('/export/<int:template_id>/csv', methods=['POST'])
@token_required
def export_csv(template_id):
    """Export report as CSV"""
    data = request.get_json() or {}
    report_data = report_service.generate_report(template_id, data.get('start_date'), data.get('end_date'))
    if report_data:
        csv_str = report_service.export_report_csv(report_data)
        return send_file(
            io.BytesIO(csv_str.encode()), mimetype=_MIME_CSV,
            as_attachment=True, download_name=f'report_{template_id}.csv'
        )
    return jsonify({'error': 'Failed to export report'}), 500
