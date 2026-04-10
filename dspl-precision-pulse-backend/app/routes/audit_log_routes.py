from flask import Blueprint, request, jsonify, send_file
from app.middleware.auth_middleware import token_required
from app.models.audit_log import AuditLog
from app.models import db
from datetime import datetime, timedelta, timezone
import io
import csv

audit_log_bp = Blueprint('audit_logs', __name__, url_prefix='/api/audit-logs')

@audit_log_bp.route('', methods=['GET'])
@token_required
def get_audit_logs():
    """Get audit logs with filtering"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    # Filters
    user_filter = request.args.get('user')
    action_filter = request.args.get('action')
    resource_type_filter = request.args.get('resource_type')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = AuditLog.query
    
    if user_filter:
        query = query.filter(AuditLog.actor_email.ilike(f'%{user_filter}%'))
    
    if action_filter:
        query = query.filter_by(action=action_filter)
    
    if resource_type_filter:
        query = query.filter_by(resource_type=resource_type_filter)
    
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            query = query.filter(AuditLog.created_at >= start_dt)
        except (ValueError, TypeError):
            pass
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            query = query.filter(AuditLog.created_at <= end_dt)
        except (ValueError, TypeError):
            pass
    
    # Paginate
    paginated = query.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'logs': [log.to_dict() for log in paginated.items],
        'total': paginated.total,
        'pages': paginated.pages,
        'current_page': page
    }), 200

@audit_log_bp.route('/search', methods=['GET'])
@token_required
def search_audit_logs():
    """Search audit logs"""
    query_str = request.args.get('q', '')
    
    if not query_str or len(query_str) < 2:
        return jsonify({'error': 'Query must be at least 2 characters'}), 400
    
    logs = AuditLog.query.filter(
        db.or_(
            AuditLog.actor_email.ilike(f'%{query_str}%'),
            AuditLog.resource_name.ilike(f'%{query_str}%'),
            AuditLog.resource_id.ilike(f'%{query_str}%')
        )
    ).order_by(AuditLog.created_at.desc()).limit(100).all()
    
    return jsonify({'logs': [log.to_dict() for log in logs]}), 200

@audit_log_bp.route('/export/csv', methods=['POST'])
@token_required
def export_csv():
    """Export audit logs as CSV"""
    data = request.get_json() or {}
    
    # Get filters from request
    user_filter = data.get('user')
    action_filter = data.get('action')
    resource_type_filter = data.get('resource_type')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    
    query = AuditLog.query
    
    if user_filter:
        query = query.filter(AuditLog.actor_email.ilike(f'%{user_filter}%'))
    
    if action_filter:
        query = query.filter_by(action=action_filter)
    
    if resource_type_filter:
        query = query.filter_by(resource_type=resource_type_filter)
    
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            query = query.filter(AuditLog.created_at >= start_dt)
        except (ValueError, TypeError):
            pass
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            query = query.filter(AuditLog.created_at <= end_dt)
        except (ValueError, TypeError):
            pass
    
    logs = query.order_by(AuditLog.created_at.desc()).all()
    
    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Timestamp', 'User', 'Action', 'Resource Type', 'Resource ID', 'Resource Name', 'Status', 'Error Message'])
    
    # Write data
    for log in logs:
        writer.writerow([
            log.created_at.isoformat(),
            log.actor_email,
            log.action,
            log.resource_type,
            log.resource_id,
            log.resource_name,
            log.status,
            log.error_message or ''
        ])
    
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'audit_logs_{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}.csv'
    )

@audit_log_bp.route('/cleanup', methods=['POST'])
@token_required
def cleanup_old_logs():
    """Delete audit logs older than specified days"""
    data = request.get_json() or {}
    days = data.get('days', 90)
    
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        deleted = AuditLog.query.filter(AuditLog.created_at < cutoff_date).delete()
        db.session.commit()
        
        return jsonify({
            'message': f'Deleted {deleted} audit logs older than {days} days'
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@audit_log_bp.route('/stats', methods=['GET'])
@token_required
def get_audit_stats():
    """Get audit log statistics"""
    try:
        total_logs = AuditLog.query.count()
        
        # Count by action
        actions = db.session.query(
            AuditLog.action,
            db.func.count(AuditLog.id)
        ).group_by(AuditLog.action).all()
        
        # Count by resource type
        resource_types = db.session.query(
            AuditLog.resource_type,
            db.func.count(AuditLog.id)
        ).group_by(AuditLog.resource_type).all()
        
        # Count by status
        statuses = db.session.query(
            AuditLog.status,
            db.func.count(AuditLog.id)
        ).group_by(AuditLog.status).all()
        
        return jsonify({
            'total_logs': total_logs,
            'by_action': {action: count for action, count in actions},
            'by_resource_type': {rt: count for rt, count in resource_types},
            'by_status': {status: count for status, count in statuses}
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
