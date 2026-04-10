from flask import Blueprint, request, jsonify
from app.middleware.auth_middleware import token_required
from app.models.alert_event import AlertEvent
from app.models import db
from datetime import datetime, timezone, timedelta

alert_events_bp = Blueprint('alert_events', __name__, url_prefix='/api/alert-events')


# ── List episodes ─────────────────────────────────────────────────────────────

@alert_events_bp.route('', methods=['GET'])
@token_required
def get_alert_events():
    """
    Return alert episodes (one row = one continuous breach episode).

    Query params
    ------------
    hours       : int   — look-back window (default 24)
    active      : bool  — 'true' = only open, 'false' = only resolved
    parameter_id: int   — filter to one parameter
    severity    : str   — 'warning' | 'critical'
    """
    hours    = request.args.get('hours', 24, type=int)
    active   = request.args.get('active')
    param_id = request.args.get('parameter_id', type=int)
    severity = request.args.get('severity')

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).replace(tzinfo=None)
    q = AlertEvent.query.filter(AlertEvent.triggered_at >= cutoff)

    if active == 'true':
        q = q.filter(AlertEvent.resolved_at.is_(None))
    elif active == 'false':
        q = q.filter(AlertEvent.resolved_at.isnot(None))
    if param_id:
        q = q.filter(AlertEvent.parameter_id == param_id)
    if severity:
        q = q.filter(AlertEvent.severity == severity)

    # Exclude events for disabled parameters
    from app.models.parameter import Parameter
    disabled_ids = [
        p.id for p in Parameter.query.filter_by(enabled=False).all()
    ]
    if disabled_ids:
        q = q.filter(AlertEvent.parameter_id.notin_(disabled_ids))

    events = q.order_by(AlertEvent.triggered_at.desc()).limit(500).all()
    return jsonify({'events': [e.to_dict() for e in events], 'count': len(events)}), 200


@alert_events_bp.route('/active', methods=['GET'])
@token_required
def get_active_events():
    """Return all currently open (unresolved) alert episodes."""
    from app.models.parameter import Parameter
    disabled_ids = [p.id for p in Parameter.query.filter_by(enabled=False).all()]
    q = AlertEvent.query.filter_by(resolved_at=None)
    if disabled_ids:
        q = q.filter(AlertEvent.parameter_id.notin_(disabled_ids))
    events = q.order_by(AlertEvent.triggered_at.desc()).all()
    return jsonify({'events': [e.to_dict() for e in events], 'count': len(events)}), 200


@alert_events_bp.route('/<int:event_id>', methods=['GET'])
@token_required
def get_alert_event(event_id):
    """Return a single alert episode by ID."""
    event = AlertEvent.query.get_or_404(event_id)
    return jsonify(event.to_dict()), 200


# ── Per-parameter report ──────────────────────────────────────────────────────

@alert_events_bp.route('/report', methods=['GET'])
@token_required
def get_alert_report():
    """
    Summary report: per-parameter stats over a time window.

    Each entry in 'report' represents one parameter and contains:
      - total_events      : total episodes in the window
      - active_events     : currently open episodes
      - critical_events   : episodes that were / are critical
      - warning_events    : episodes that were / are warning
      - max_value_reached : worst peak value across all episodes
      - min_value_reached : lowest peak value across all episodes
      - avg_duration_s    : average duration of resolved episodes (seconds)
      - max_duration_s    : longest resolved episode (seconds)
      - total_duration_s  : sum of all resolved episode durations (seconds)
      - events            : list of individual episode dicts (newest first)
    """
    hours  = request.args.get('hours', 24, type=int)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).replace(tzinfo=None)

    rows = AlertEvent.query.filter(AlertEvent.triggered_at >= cutoff).all()

    # Group by parameter
    by_param: dict = {}
    for e in rows:
        pid = e.parameter_id
        if pid not in by_param:
            by_param[pid] = {
                'parameter_id':   pid,
                'parameter_name': e.parameter_name,
                'alert_min':      e.alert_min,
                'alert_max':      e.alert_max,
                'events':         [],
            }
        by_param[pid]['events'].append(e)

    report = []
    for pid, info in by_param.items():
        evts      = info['events']
        values    = [e.peak_value or e.value_at_trigger for e in evts]
        durations = [e.duration_seconds() for e in evts if e.duration_seconds() is not None]
        report.append({
            'parameter_id':     pid,
            'parameter_name':   info['parameter_name'],
            'alert_min':        info['alert_min'],
            'alert_max':        info['alert_max'],
            'total_events':     len(evts),
            'active_events':    sum(1 for e in evts if e.resolved_at is None),
            'critical_events':  sum(1 for e in evts if e.severity == 'critical'),
            'warning_events':   sum(1 for e in evts if e.severity == 'warning'),
            'max_value_reached': round(max(values), 4) if values else None,
            'min_value_reached': round(min(values), 4) if values else None,
            'avg_duration_s':   round(sum(durations) / len(durations)) if durations else None,
            'max_duration_s':   max(durations) if durations else None,
            'total_duration_s': sum(durations) if durations else None,
            'events': [e.to_dict() for e in sorted(evts,
                       key=lambda x: x.triggered_at, reverse=True)],
        })

    report.sort(key=lambda x: x['total_events'], reverse=True)
    return jsonify({
        'report':       report,
        'hours':        hours,
        'generated_at': datetime.now(timezone.utc).isoformat(),
    }), 200
