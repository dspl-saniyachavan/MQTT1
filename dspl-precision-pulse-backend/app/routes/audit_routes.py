"""
Audit API routes matching frontend expectations
"""
from flask import Blueprint, request, jsonify, send_file
from app.middleware.auth_middleware import token_required
from app.models.audit_log import AuditLog
from app.models import db
from datetime import datetime, timedelta, timezone
import io
import csv

audit_bp = Blueprint('audit', __name__, url_prefix='/api/audit')

def create_audit_log():
    """Create a new audit log entry"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        log = AuditLog(
            event_type=data.get('event_type'),
            severity=data.get('severity', 'info'),
            actor_email=data.get('actor_email'),
            actor_ip=data.get('actor_ip'),
            resource_type=data.get('resource_type'),
            resource_id=data.get('resource_id'),
            resource_name=data.get('resource_name'),
            action=data.get('action'),
            description=data.get('description'),
            old_values=data.get('old_values'),
            new_values=data.get('new_values'),
            context=data.get('metadata'),
            status=data.get('status', 'success'),
            error_message=data.get('error_message'),
            device_id=data.get('device_id')
        )
        
        db.session.add(log)
        db.session.commit()
        
        return jsonify(log.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@audit_bp.route('/logs', methods=['GET', 'POST'])
@token_required
def handle_logs():
    """Handle both GET (retrieve) and POST (create) for audit logs"""
    if request.method == 'POST':
        return create_audit_log()
    
    # GET request - retrieve logs
    try:
        # Pagination
        limit = request.args.get('limit', 20, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Filters
        event_type = request.args.get('event_type')
        resource_type = request.args.get('resource_type')
        actor_email = request.args.get('actor_email')
        severity = request.args.get('severity')
        status = request.args.get('status')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        query = AuditLog.query
        
        # Apply filters
        if event_type:
            query = query.filter_by(event_type=event_type)
        if resource_type:
            query = query.filter_by(resource_type=resource_type)
        if actor_email:
            query = query.filter(AuditLog.actor_email.ilike(f'%{actor_email}%'))
        if severity:
            query = query.filter_by(severity=severity)
        if status:
            query = query.filter_by(status=status)
        
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
        
        # Get total count before pagination
        total_count = query.count()
        
        # Sort by newest first and apply pagination
        logs = query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset).all()
        
        return jsonify({
            'logs': [log.to_dict() for log in logs],
            'total_count': total_count
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@audit_bp.route('/events', methods=['GET'])
@token_required
def get_event_types():
    """Get list of unique event types"""
    try:
        event_types = db.session.query(AuditLog.event_type).distinct().all()
        return jsonify({
            'event_types': [et[0] for et in event_types if et[0]]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@audit_bp.route('/statistics', methods=['GET'])
@token_required
def get_statistics():
    """Get audit log statistics for the last N days"""
    try:
        days = request.args.get('days', 7, type=int)
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        query = AuditLog.query.filter(AuditLog.created_at >= cutoff_date)
        
        total_events = query.count()
        
        # Event distribution
        event_dist = db.session.query(
            AuditLog.event_type,
            db.func.count(AuditLog.id)
        ).filter(AuditLog.created_at >= cutoff_date).group_by(AuditLog.event_type).all()
        
        # Resource distribution
        resource_dist = db.session.query(
            AuditLog.resource_type,
            db.func.count(AuditLog.id)
        ).filter(AuditLog.created_at >= cutoff_date).group_by(AuditLog.resource_type).all()
        
        # Status distribution
        status_dist = db.session.query(
            AuditLog.status,
            db.func.count(AuditLog.id)
        ).filter(AuditLog.created_at >= cutoff_date).group_by(AuditLog.status).all()
        
        # Severity distribution
        severity_dist = db.session.query(
            AuditLog.severity,
            db.func.count(AuditLog.id)
        ).filter(AuditLog.created_at >= cutoff_date).group_by(AuditLog.severity).all()
        
        # Top actors
        top_actors = db.session.query(
            AuditLog.actor_email,
            db.func.count(AuditLog.id)
        ).filter(AuditLog.created_at >= cutoff_date).group_by(AuditLog.actor_email).order_by(
            db.func.count(AuditLog.id).desc()
        ).limit(10).all()
        
        return jsonify({
            'total_events': total_events,
            'event_distribution': [{'event_type': et, 'count': count} for et, count in event_dist],
            'resource_distribution': [{'resource_type': rt, 'count': count} for rt, count in resource_dist],
            'status_distribution': [{'status': s, 'count': count} for s, count in status_dist],
            'severity_distribution': [{'severity': sev, 'count': count} for sev, count in severity_dist],
            'top_actors': [{'actor_email': email, 'count': count} for email, count in top_actors]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@audit_bp.route('/export', methods=['GET'])
@token_required
def export_logs():
    """Export audit logs as CSV"""
    try:
        # Get filters
        event_type = request.args.get('event_type')
        resource_type = request.args.get('resource_type')
        actor_email = request.args.get('actor_email')
        severity = request.args.get('severity')
        status = request.args.get('status')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        query = AuditLog.query
        
        # Apply filters
        if event_type:
            query = query.filter_by(event_type=event_type)
        if resource_type:
            query = query.filter_by(resource_type=resource_type)
        if actor_email:
            query = query.filter(AuditLog.actor_email.ilike(f'%{actor_email}%'))
        if severity:
            query = query.filter_by(severity=severity)
        if status:
            query = query.filter_by(status=status)
        
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
        writer.writerow([
            'Timestamp', 'Event Type', 'Resource Type', 'Resource ID', 'Resource Name',
            'Actor Email', 'Actor IP', 'Action', 'Severity', 'Status', 'Description', 'Error Message'
        ])
        
        # Write data
        for log in logs:
            writer.writerow([
                log.created_at.isoformat() if log.created_at else '',
                log.event_type or '',
                log.resource_type or '',
                log.resource_id or '',
                log.resource_name or '',
                log.actor_email or '',
                log.actor_ip or '',
                log.action or '',
                log.severity or '',
                log.status or '',
                log.description or '',
                log.error_message or ''
            ])
        
        return send_file(
            io.BytesIO(output.getvalue().encode()),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'audit_logs_{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}.csv'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500
