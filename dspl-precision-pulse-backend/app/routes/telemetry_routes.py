from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timedelta, timezone
from app.models.parameter_stream import ParameterStream
from app.models import db
from app.middleware.auth_middleware import token_required
from sqlalchemy import desc, func
from app.services.data_freshness_monitor import DataFreshnessMonitor
from telemetry_config import CONFIG_SUMMARY, TELEMETRY_FETCH_INTERVAL_MS
import logging

logger = logging.getLogger(__name__)

telemetry_bp = Blueprint('telemetry', __name__, url_prefix='/api/telemetry')

@telemetry_bp.route('/config', methods=['GET'])
def get_telemetry_config():
    """Return live system config values for the 5 core keys."""
    try:
        from app.services.config_manager import get_config_manager
        mgr = get_config_manager()
        return jsonify({
            'mqtt_broker':             mgr.get_config('MQTT_BROKER', 'localhost'),
            'mqtt_keep_alive':         mgr.get_config('MQTT_KEEP_ALIVE', 60),
            'fetch_interval_ms':       mgr.get_config('TELEMETRY_FETCH_INTERVAL_MS', 3000),
            'max_chart_data_points':   mgr.get_config('MAX_CHART_DATA_POINTS', 50),
            'retention_days':          mgr.get_config('TELEMETRY_RETENTION_DAYS', 30),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 200
    except Exception as e:
        logger.error(f"[TELEMETRY] Error getting config: {e}")
        return jsonify({
            'mqtt_broker': 'localhost', 'mqtt_keep_alive': 60,
            'fetch_interval_ms': 3000, 'max_chart_data_points': 50,
            'retention_days': 30, 'timestamp': datetime.now(timezone.utc).isoformat()
        }), 200


@telemetry_bp.route('/stream', methods=['POST'])
def stream_telemetry():
    """Receive telemetry stream from desktop client — broadcast only, NO DB write, NO alert check.
    DB writes and alert checks are handled exclusively by the MQTT subscriber
    (_handle_telemetry) to prevent duplicate rows and duplicate alert events.
    This endpoint exists only as an HTTP fallback for Socket.IO broadcast when
    the desktop cannot reach MQTT directly.
    """
    try:
        data = request.get_json()
        client_id = data.get('client_id')
        timestamp_str = data.get('timestamp')
        parameters = data.get('parameters', [])

        if not client_id or not parameters:
            return jsonify({'error': 'Missing client_id or parameters'}), 400

        try:
            timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now(timezone.utc)
        except Exception:
            timestamp = datetime.now(timezone.utc)

        # Record data freshness only — no DB write
        if hasattr(current_app, 'data_freshness_monitor'):
            try:
                current_app.data_freshness_monitor.record_data(client_id)
            except Exception as e:
                logger.error(f"[TELEMETRY] Error recording data freshness: {e}")

        # Broadcast via Socket.IO only — MQTT subscriber already wrote to DB
        if hasattr(current_app, 'socketio'):
            try:
                normalized_params = [
                    {
                        'id': p.get('parameter_id') or p.get('id'),
                        'name': p.get('name'),
                        'value': float(p.get('value', 0)),
                        'unit': p.get('unit', '')
                    }
                    for p in parameters
                ]
                current_app.socketio.emit(
                    'telemetry',
                    {
                        'client_id': client_id,
                        'timestamp': timestamp.isoformat(),
                        'data': {'parameters': normalized_params}
                    },
                    namespace='/'
                )
            except Exception as e:
                logger.error(f"[TELEMETRY] Error broadcasting: {e}")

        # NO alert check here — mqtt_subscriber._handle_telemetry() already calls
        # check_range_alert() for every MQTT tick. Calling it again here would
        # create duplicate AlertEvent rows for the same value.

        logger.info(f"[TELEMETRY] Broadcast-only: {len(parameters)} params from {client_id}")
        return jsonify({'message': 'Telemetry received', 'count': len(parameters)}), 200
    except Exception as e:
        logger.error(f"[TELEMETRY] Unexpected error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@telemetry_bp.route('/latest', methods=['GET'])
def get_latest_telemetry():
    """Get latest telemetry data for all parameters"""
    try:
        logger.info("[TELEMETRY] /latest endpoint called")
        
        # Get latest record for each parameter
        latest_dict = {}
        all_records = db.session.query(ParameterStream).order_by(
            ParameterStream.parameter_id,
            ParameterStream.timestamp.desc()
        ).all()
        
        logger.info(f"[TELEMETRY] Found {len(all_records)} total records")
        
        for record in all_records:
            if record.parameter_id not in latest_dict:
                latest_dict[record.parameter_id] = record
        
        # Format response for frontend dashboard
        parameters = []
        for param_id in sorted(latest_dict.keys()):
            p = latest_dict[param_id]
            parameters.append({
                'id': p.parameter_id,
                'value': p.value,
                'timestamp': int(p.timestamp.timestamp() * 1000) if p.timestamp else None
            })
        
        logger.info(f"[TELEMETRY] Returning {len(parameters)} latest parameters")
        
        return jsonify({
            'data': {
                'parameters': parameters,
                'timestamp': datetime.now(timezone.utc).isoformat()
            },
            'count': len(parameters)
        }), 200
    except Exception as e:
        logger.error(f"[TELEMETRY] Error in /latest: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@telemetry_bp.route('/parameter/<int:param_id>/latest', methods=['GET'])
def get_parameter_latest(param_id):
    """Get latest value for specific parameter"""
    try:
        latest = db.session.query(ParameterStream).filter(
            ParameterStream.parameter_id == param_id
        ).order_by(desc(ParameterStream.timestamp)).first()
        
        if not latest:
            return jsonify({'error': 'Parameter not found'}), 404
        
        return jsonify({'telemetry': latest.to_dict()}), 200
    except Exception as e:
        logger.error(f"[TELEMETRY] Error in /parameter/<param_id>/latest: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@telemetry_bp.route('/parameter/<int:param_id>/history', methods=['GET'])
def get_parameter_history(param_id):
    """Get historical telemetry data for parameter"""
    try:
        minutes = request.args.get('minutes', 60, type=int)
        limit = request.args.get('limit', None, type=int)

        # Respect MAX_CHART_DATA_POINTS from system config
        try:
            from app.services.config_manager import get_config_manager
            max_pts = get_config_manager().get_config('MAX_CHART_DATA_POINTS', 50)
            limit = limit or int(max_pts)
        except Exception:
            limit = limit or 50

        start_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)

        history = db.session.query(ParameterStream).filter(
            (ParameterStream.parameter_id == param_id) &
            (ParameterStream.timestamp >= start_time)
        ).order_by(desc(ParameterStream.timestamp)).limit(limit).all()
        
        return jsonify({
            'parameter_id': param_id,
            'time_range_minutes': minutes,
            'data': [p.to_dict() for p in history],
            'count': len(history)
        }), 200
    except Exception as e:
        logger.error(f"[TELEMETRY] Error in /parameter/<param_id>/history: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@telemetry_bp.route('/parameter/<int:param_id>/history-range', methods=['GET'])
@token_required
def get_parameter_history_range(param_id):
    try:
        preset = request.args.get('preset', 'last_hour')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        limit = request.args.get('limit', 1000, type=int)

        # Use local time to match timezone-naive DB timestamps
        now = datetime.now()

        if preset == 'last_15_minutes':
            start_time = now - timedelta(minutes=15)
        elif preset == 'last_30_minutes':
            start_time = now - timedelta(minutes=30)
        elif preset == 'last_hour':
            start_time = now - timedelta(hours=1)
        elif preset == 'last_6_hours':
            start_time = now - timedelta(hours=6)
        elif preset == 'last_24_hours':
            start_time = now - timedelta(days=1)
        elif preset == 'last_7_days':
            start_time = now - timedelta(days=7)
        elif preset == 'last_30_days':
            start_time = now - timedelta(days=30)
        else:
            start_time = now - timedelta(hours=1)

        if preset == 'custom' and start_date_str:
            try:
                start_time = datetime.fromisoformat(start_date_str).replace(tzinfo=None)
            except (ValueError, TypeError):
                start_time = now - timedelta(hours=1)

        end_time = now
        if end_date_str:
            try:
                end_time = datetime.fromisoformat(end_date_str).replace(tzinfo=None)
            except (ValueError, TypeError):
                end_time = now
        
        # Deduplicate: keep only the lowest id per (parameter_id, timestamp) pair,
        # then filter by time range and return newest first.
        min_id_subq = (
            db.session.query(func.min(ParameterStream.id).label('min_id'))
            .filter(
                ParameterStream.parameter_id == param_id,
                ParameterStream.timestamp >= start_time.replace(tzinfo=None),
                ParameterStream.timestamp <= end_time.replace(tzinfo=None),
            )
            .group_by(ParameterStream.timestamp)
            .subquery()
        )

        records = (
            db.session.query(ParameterStream)
            .filter(ParameterStream.id.in_(db.session.query(min_id_subq.c.min_id)))
            .order_by(desc(ParameterStream.timestamp))
            .limit(limit)
            .all()
        )
        
        # Calculate statistics
        if records:
            values = [r.value for r in records]
            import statistics as stats_module
            
            stats = {
                'count': len(values),
                'minimum': min(values),
                'maximum': max(values),
                'average': sum(values) / len(values),
                'std_dev': stats_module.stdev(values) if len(values) > 1 else 0
            }
        else:
            stats = {
                'count': 0,
                'minimum': None,
                'maximum': None,
                'average': None,
                'std_dev': None
            }
        
        return jsonify({
            'parameter_id': param_id,
            'records': [{
                'timestamp': r.timestamp.isoformat(),
                'value': r.value,
                'id': r.id
            } for r in records],
            'statistics': stats,
            'time_range': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'preset': preset
            },
            'count': len(records)
        }), 200
    except Exception as e:
        logger.error(f"[TELEMETRY] Error in /parameter/<param_id>/history-range: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

