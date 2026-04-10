from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timedelta, timezone
from app.models.parameter_stream import ParameterStream
from app.models import db
from app.middleware.auth_middleware import token_required
from sqlalchemy import and_, desc

parameter_stream_bp = Blueprint('parameter_stream', __name__, url_prefix='/api/parameter-stream')

@parameter_stream_bp.route('/push', methods=['POST'])
def push_parameter_stream():
    """Receive offline-buffered parameter stream data from desktop app.

    ONLY processes payloads with is_buffered=True.
    Live data is written exclusively by the MQTT subscriber (_handle_telemetry)
    to prevent duplicate rows in parameter_stream.

    Dedup strategy: skip any (parameter_id, timestamp) pair where a row already
    exists within a 1-second window — identical to the MQTT subscriber guard.
    This handles the case where the desktop flushes buffered rows that the MQTT
    subscriber already wrote when the connection was briefly restored.

    NO alert checks are performed here — alert episodes are opened/closed only
    by the MQTT subscriber on live ticks, not on historical buffered data.
    """
    try:
        data = request.get_json()
        client_id = data.get('client_id')
        payload_timestamp_str = data.get('timestamp')
        parameters = data.get('parameters', [])
        is_buffered = data.get('is_buffered', False)

        if not client_id or not parameters:
            return jsonify({'error': 'Missing client_id or parameters'}), 400

        # Reject live (non-buffered) pushes — MQTT subscriber handles those
        if not is_buffered:
            return jsonify({'message': 'Live data handled by MQTT subscriber', 'count': 0}), 200

        try:
            payload_ts = datetime.fromisoformat(payload_timestamp_str) if payload_timestamp_str else datetime.now(timezone.utc)
            if payload_ts.tzinfo is not None:
                payload_ts = payload_ts.replace(tzinfo=None)
        except Exception:
            payload_ts = datetime.now(timezone.utc).replace(tzinfo=None)

        stored_ids = []
        skipped = 0

        for param in parameters:
            param_id = param.get('parameter_id') or param.get('id')
            if param_id is None:
                skipped += 1
                continue
            ts_str = param.get('timestamp') or payload_timestamp_str
            try:
                ts = datetime.fromisoformat(ts_str) if ts_str else payload_ts
                if ts.tzinfo is not None:
                    ts = ts.replace(tzinfo=None)
            except Exception:
                ts = payload_ts
            try:
                # 3-second window dedup — matches mqtt_subscriber._handle_telemetry
                # and the desktop's 2-second SQLite guard. Prevents double-writes
                # when the desktop flushes rows that MQTT already wrote to PostgreSQL.
                window_start = ts - timedelta(seconds=3)
                window_end   = ts + timedelta(seconds=3)
                exists = db.session.query(ParameterStream.id).filter(
                    ParameterStream.parameter_id == int(param_id),
                    ParameterStream.timestamp    >= window_start,
                    ParameterStream.timestamp    <= window_end,
                ).first()
                if exists:
                    skipped += 1
                    continue
                stream_record = ParameterStream(
                    parameter_id=int(param_id),
                    value=float(param.get('value', 0)),
                    timestamp=ts,
                    synced=False
                )
                db.session.add(stream_record)
                db.session.flush()
                stored_ids.append(stream_record.id)
            except Exception as record_err:
                db.session.rollback()
                skipped += 1

        db.session.commit()

        # Broadcast stored buffered data to web app via Socket.IO
        if stored_ids and hasattr(current_app, 'socketio'):
            current_app.socketio.emit(
                'parameter_stream_update',
                {
                    'client_id': client_id,
                    'timestamp': payload_ts.isoformat(),
                    'is_buffered': True,
                    'data': {'parameters': parameters}
                },
                namespace='/'
            )
            current_app.socketio.emit(
                'telemetry',
                {
                    'client_id': client_id,
                    'timestamp': payload_ts.isoformat(),
                    'data': {'parameters': parameters}
                },
                namespace='/'
            )

        # Mark stored records as synced
        if stored_ids:
            db.session.query(ParameterStream).filter(
                ParameterStream.id.in_(stored_ids)
            ).update({'synced': True}, synchronize_session=False)
            db.session.commit()

        return jsonify({
            'message': 'Buffered data stored and streamed',
            'count': len(stored_ids),
            'skipped': skipped
        }), 200

    except Exception as e:
        print(f"[PARAM_STREAM] Error: {e}")
        return jsonify({'error': str(e)}), 500

@parameter_stream_bp.route('/latest', methods=['GET'])
def get_latest_parameter_stream():
    """Get latest parameter stream data for all parameters using efficient subquery"""
    try:
        from sqlalchemy import func

        # Subquery: max timestamp per parameter_id
        subq = db.session.query(
            ParameterStream.parameter_id,
            func.max(ParameterStream.timestamp).label('max_ts')
        ).group_by(ParameterStream.parameter_id).subquery()

        # Join back to get full records
        records = db.session.query(ParameterStream).join(
            subq,
            (ParameterStream.parameter_id == subq.c.parameter_id) &
            (ParameterStream.timestamp == subq.c.max_ts)
        ).all()

        return jsonify({
            'parameters': [p.to_dict() for p in records],
            'count': len(records)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@parameter_stream_bp.route('/parameter/<int:param_id>/latest', methods=['GET'])
def get_parameter_latest(param_id):
    """Get latest value for specific parameter"""
    try:
        latest = db.session.query(ParameterStream).filter(
            ParameterStream.parameter_id == param_id
        ).order_by(desc(ParameterStream.timestamp)).first()
        
        if not latest:
            return jsonify({'error': 'Parameter not found'}), 404
        
        return jsonify(latest.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@parameter_stream_bp.route('/parameter/<int:param_id>/history', methods=['GET'])
def get_parameter_history(param_id):
    """Get historical parameter stream data with time range filtering"""
    try:
        minutes = request.args.get('minutes', 60, type=int)
        limit = request.args.get('limit', 1000, type=int)
        
        start_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        
        history = db.session.query(ParameterStream).filter(
            and_(
                ParameterStream.parameter_id == param_id,
                ParameterStream.timestamp >= start_time
            )
        ).order_by(desc(ParameterStream.timestamp)).limit(limit).all()
        
        return jsonify({
            'parameter_id': param_id,
            'time_range_minutes': minutes,
            'data': [p.to_dict() for p in history],
            'count': len(history)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@parameter_stream_bp.route('/filter', methods=['POST'])
def filter_parameter_stream():
    """Filter parameter stream data by constraints"""
    try:
        filters = request.get_json()
        
        query = db.session.query(ParameterStream)
        
        # Parameter filter
        if filters.get('parameter_id'):
            query = query.filter(ParameterStream.parameter_id == filters['parameter_id'])
        
        # Value range filter
        if filters.get('min_value') is not None:
            query = query.filter(ParameterStream.value >= filters['min_value'])
        if filters.get('max_value') is not None:
            query = query.filter(ParameterStream.value <= filters['max_value'])
        
        # Time range filter
        if filters.get('start_time'):
            try:
                start = datetime.fromisoformat(filters['start_time'])
                query = query.filter(ParameterStream.timestamp >= start)
            except (ValueError, TypeError):
                pass
        
        if filters.get('end_time'):
            try:
                end = datetime.fromisoformat(filters['end_time'])
                query = query.filter(ParameterStream.timestamp <= end)
            except (ValueError, TypeError):
                pass
        
        # Synced filter
        if filters.get('synced') is not None:
            query = query.filter(ParameterStream.synced == filters['synced'])
        
        # Limit results
        limit = filters.get('limit', 1000)
        results = query.order_by(desc(ParameterStream.timestamp)).limit(limit).all()
        
        return jsonify({
            'filters': filters,
            'data': [p.to_dict() for p in results],
            'count': len(results)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@parameter_stream_bp.route('/statistics', methods=['GET'])
def get_statistics():
    """Get statistics for parameter stream data"""
    try:
        param_id = request.args.get('parameter_id', type=int)
        minutes = request.args.get('minutes', 60, type=int)
        
        start_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        
        query = db.session.query(ParameterStream).filter(
            ParameterStream.timestamp >= start_time
        )
        
        if param_id:
            query = query.filter(ParameterStream.parameter_id == param_id)
        
        records = query.all()
        
        if not records:
            return jsonify({'error': 'No data found'}), 404
        
        values = [r.value for r in records]
        
        stats = {
            'count': len(records),
            'min': min(values),
            'max': max(values),
            'avg': sum(values) / len(values),
            'latest': records[0].to_dict() if records else None,
            'time_range_minutes': minutes
        }
        
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@parameter_stream_bp.route('/cleanup', methods=['POST'])
@token_required
def cleanup_old_data():
    """Clean up old parameter stream data (admin only)"""
    if request.user.get('role') != 'admin':
        return jsonify({'error': 'Admin only'}), 403
    try:
        days = request.json.get('days', 30) if request.json else 30
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        deleted = db.session.query(ParameterStream).filter(
            ParameterStream.timestamp < cutoff_date
        ).delete()
        
        db.session.commit()
        
        return jsonify({
            'message': f'Deleted {deleted} records older than {days} days',
            'deleted_count': deleted
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@parameter_stream_bp.route('/sync-status', methods=['GET'])
def get_sync_status():
    """Return PostgreSQL parameter_stream count for sync diagnostics."""
    try:
        total   = db.session.query(ParameterStream).count()
        synced  = db.session.query(ParameterStream).filter(ParameterStream.synced == True).count()
        unsynced = total - synced
        return jsonify({
            'total':    total,
            'synced':   synced,
            'unsynced': unsynced,
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@parameter_stream_bp.route('/mark-all-unsynced', methods=['POST'])
@token_required
def mark_all_unsynced():
    """Mark all parameter_stream records as unsynced (called on MQTT disconnect)"""
    if request.user.get('role') != 'admin':
        return jsonify({'error': 'Admin only'}), 403
    try:
        updated = db.session.query(ParameterStream).filter(
            ParameterStream.synced == True
        ).update({'synced': False}, synchronize_session=False)
        db.session.commit()
        print(f"[PARAM_STREAM] Marked {updated} records as unsynced")
        return jsonify({'message': f'Marked {updated} records as unsynced'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@parameter_stream_bp.route('/mark-synced', methods=['PUT'])
def mark_synced():
    """Mark parameter stream records as synced"""
    try:
        data = request.get_json()
        stream_ids = data.get('ids', [])
        
        if not stream_ids:
            return jsonify({'error': 'No IDs provided'}), 400
        
        updated = db.session.query(ParameterStream).filter(
            ParameterStream.id.in_(stream_ids)
        ).update({'synced': True})
        
        db.session.commit()
        
        return jsonify({
            'message': f'Marked {updated} records as synced',
            'updated_count': updated
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@parameter_stream_bp.route('/parameter/<int:param_id>/value', methods=['POST'])
@token_required
def add_or_edit_parameter_value(param_id):
    """Admin endpoint to update parameter stream value"""
    user = request.user
    if user.get('role') != 'admin':
        return jsonify({'error': 'Only admins can edit parameter values'}), 403

    data = request.get_json()
    value = data.get('value') if data else None

    if value is None:
        return jsonify({'error': 'Missing value'}), 400

    try:
        value = float(value)
    except (ValueError, TypeError):
        return jsonify({'error': 'Value must be a number'}), 400

    try:
        timestamp = datetime.now(timezone.utc)
        stream_record = ParameterStream(
            parameter_id=param_id,
            value=value,
            timestamp=timestamp,
            synced=True
        )
        db.session.add(stream_record)
        db.session.commit()
        db.session.refresh(stream_record)
        record_id = stream_record.id
        print(f"[PARAM_STREAM] ✓ Admin-edit record {record_id}: parameter {param_id} = {value}")

        if hasattr(current_app, 'socketio'):
            try:
                ts_iso = timestamp.isoformat()
                # Emit parameter_value_updated so the frontend edit-values page
                # and the desktop both update their in-memory state.
                # Do NOT emit parameter_stream_update here — that would cause
                # the desktop to pick up the value and re-push it to
                # /api/parameter-stream/push, writing a duplicate row.
                current_app.socketio.emit(
                    'parameter_value_updated',
                    {'parameter_id': param_id, 'value': value, 'timestamp': ts_iso,
                     'updated_by': user.get('user_id'), 'source': 'admin'},
                    namespace='/'
                )
            except Exception as e:
                print(f'[PARAM_STREAM] Error broadcasting update: {e}')

        return jsonify({
            'message': 'Parameter value updated successfully',
            'parameter_id': param_id, 'value': value,
            'timestamp': timestamp.isoformat(), 'id': record_id
        }), 201
    except Exception as e:
        db.session.rollback()
        print(f"[PARAM_STREAM] Error: {e}")
        return jsonify({'error': str(e)}), 500
