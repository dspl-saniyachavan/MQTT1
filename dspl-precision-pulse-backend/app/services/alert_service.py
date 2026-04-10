"""
Alert Service — threshold monitoring with Socket.IO broadcast
"""
import threading
from app.models import db
from app.models.parameter_alert import ParameterAlert
from app.models.parameter_history import ParameterHistory
from app.models.alert_event import AlertEvent, _fmt_duration
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)

# Per-parameter lock — prevents two threads from simultaneously opening
# a new AlertEvent row for the same parameter (race condition on INSERT).
_alert_locks: dict = {}
_alert_locks_mutex = threading.Lock()


def _get_param_lock(parameter_id: int) -> threading.Lock:
    """Return (creating if needed) the per-parameter threading.Lock."""
    with _alert_locks_mutex:
        if parameter_id not in _alert_locks:
            _alert_locks[parameter_id] = threading.Lock()
        return _alert_locks[parameter_id]


# Example alert definitions: (parameter_name, alert_type, threshold, message)
EXAMPLE_ALERTS = [
    ('Temperature', 'high', 45.0, '🌡️ Heat Alert: Temperature exceeded 45°C'),
    ('Wind Speed',  'high', 80.0, '🌪️ Storm Warning: Wind speed exceeded 80 km/h'),
]


class AlertService:

    @staticmethod
    def seed_example_alerts():
        """Seed the two example alerts if the parameters exist and alerts don't yet exist."""
        try:
            from app.models.parameter import Parameter
            for param_name, alert_type, threshold, message in EXAMPLE_ALERTS:
                param = Parameter.query.filter(
                    db.func.lower(Parameter.name) == param_name.lower()
                ).first()
                if not param:
                    logger.info('[ALERT] Seed skipped — parameter not found: %s', param_name)
                    continue
                exists = ParameterAlert.query.filter_by(
                    parameter_id=param.id, alert_type=alert_type
                ).first()
                if exists:
                    continue
                alert = ParameterAlert(
                    parameter_id=param.id,
                    alert_type=alert_type,
                    threshold=threshold,
                    message=message,
                    is_active=True,
                )
                db.session.add(alert)
                logger.info('[ALERT] Seeded alert: %s %s > %s', param_name, alert_type, threshold)
            db.session.commit()
        except Exception as exc:
            logger.error('[ALERT] Error seeding example alerts: %s', exc)
            db.session.rollback()

    @staticmethod
    def create_alert(parameter_id: int, alert_type: str, threshold: float,
                     message: str = None) -> ParameterAlert:
        try:
            existing = ParameterAlert.query.filter_by(
                parameter_id=parameter_id, alert_type=alert_type
            ).first()
            if existing:
                return existing

            alert = ParameterAlert(
                parameter_id=parameter_id,
                alert_type=alert_type,
                threshold=threshold,
                message=message,
                is_active=True,
            )
            db.session.add(alert)
            db.session.commit()
            logger.info('[ALERT] Created: param=%s type=%s threshold=%s', parameter_id, alert_type, threshold)
            return alert
        except Exception as exc:
            logger.error('[ALERT] Error creating alert: %s', exc)
            db.session.rollback()
            raise

    @staticmethod
    def check_alert(parameter_id: int, current_value: float,
                    parameter_name: str = None) -> list:
        """Check thresholds and emit Socket.IO events for any triggered alerts."""
        try:
            alerts = ParameterAlert.query.filter_by(
                parameter_id=parameter_id, is_active=True
            ).all()

            triggered = []
            for alert in alerts:
                should_trigger = (
                    (alert.alert_type == 'high'     and current_value > alert.threshold) or
                    (alert.alert_type == 'low'      and current_value < alert.threshold) or
                    (alert.alert_type == 'critical' and current_value < alert.threshold)
                )
                if not should_trigger:
                    continue

                alert.triggered_count += 1
                alert.last_triggered = datetime.now(timezone.utc)
                db.session.commit()

                payload = {
                    **alert.to_dict(),
                    'parameter_name': parameter_name,
                    'current_value': current_value,
                    'triggered_at': datetime.now(timezone.utc).isoformat(),
                }
                triggered.append(payload)

                try:
                    from app import get_socketio
                    sio = get_socketio()
                    if sio:
                        sio.emit('alert_triggered', payload, namespace='/')
                        logger.warning(
                            '[ALERT] Triggered & emitted: param=%s value=%s threshold=%s msg=%s',
                            parameter_name, current_value, alert.threshold, alert.message
                        )
                except Exception as emit_exc:
                    logger.error('[ALERT] Socket.IO emit error: %s', emit_exc)

            return triggered
        except Exception as exc:
            logger.error('[ALERT] Error checking alerts: %s', exc)
            return []

    @staticmethod
    def disable_alert(alert_id: int) -> bool:
        try:
            alert = ParameterAlert.query.get(alert_id)
            if not alert:
                return False
            alert.is_active = False
            db.session.commit()
            return True
        except Exception as exc:
            logger.error('[ALERT] Error disabling alert: %s', exc)
            db.session.rollback()
            return False

    @staticmethod
    def delete_alert(alert_id: int) -> bool:
        try:
            alert = ParameterAlert.query.get(alert_id)
            if not alert:
                return False
            db.session.delete(alert)
            db.session.commit()
            return True
        except Exception as exc:
            logger.error('[ALERT] Error deleting alert: %s', exc)
            db.session.rollback()
            return False

    @staticmethod
    def get_parameter_alerts(parameter_id: int) -> list:
        try:
            return [a.to_dict() for a in ParameterAlert.query.filter_by(parameter_id=parameter_id).all()]
        except Exception as exc:
            logger.error('[ALERT] Error getting parameter alerts: %s', exc)
            return []

    @staticmethod
    def get_active_alerts() -> list:
        try:
            return [a.to_dict() for a in ParameterAlert.query.filter_by(is_active=True).all()]
        except Exception as exc:
            logger.error('[ALERT] Error getting active alerts: %s', exc)
            return []

    @staticmethod
    def get_triggered_alerts(hours: int = 24) -> list:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            alerts = ParameterAlert.query.filter(
                ParameterAlert.last_triggered >= cutoff
            ).all()
            return [a.to_dict() for a in alerts]
        except Exception as exc:
            logger.error('[ALERT] Error getting triggered alerts: %s', exc)
            return []

    @staticmethod
    def record_parameter_change(parameter_id: int, old_value: float, new_value: float,
                                changed_by: str = None, reason: str = None) -> ParameterHistory:
        try:
            history = ParameterHistory(
                parameter_id=parameter_id,
                old_value=old_value,
                new_value=new_value,
                changed_by=changed_by,
                change_reason=reason,
            )
            db.session.add(history)
            db.session.commit()
            return history
        except Exception as exc:
            logger.error('[ALERT] Error recording parameter change: %s', exc)
            db.session.rollback()
            raise

    @staticmethod
    def get_parameter_history(parameter_id: int, limit: int = 100) -> list:
        try:
            history = ParameterHistory.query.filter_by(
                parameter_id=parameter_id
            ).order_by(ParameterHistory.created_at.desc()).limit(limit).all()
            return [h.to_dict() for h in history]
        except Exception as exc:
            logger.error('[ALERT] Error getting parameter history: %s', exc)
            return []


alert_service = AlertService()



def check_range_alert(parameter_id: int, parameter_name: str,
                      current_value: float, alert_min, alert_max,
                      warn_min=None, warn_max=None) -> None:
    """
    Strict two-tier alert engine — one open episode per parameter at a time.

    WARNING  -> closes when value escalates to critical or returns to safe zone.
    CRITICAL -> closes when value drops to warning or safe zone.

    Uses PostgreSQL advisory lock to prevent concurrent MQTT threads from
    opening duplicate episodes. The in-process threading.Lock handles
    same-process concurrency; the advisory lock handles multi-worker deployments.
    """
    # Skip alert processing for disabled parameters
    from app.models.parameter import Parameter
    param = Parameter.query.get(parameter_id)
    if param and not param.enabled:
        return

    has_critical = alert_min is not None or alert_max is not None
    has_warning  = warn_min  is not None or warn_max  is not None
    if not has_critical and not has_warning:
        return

    param_lock = _get_param_lock(parameter_id)
    with param_lock:
        is_critical = has_critical and (
            (alert_min is not None and current_value < alert_min) or
            (alert_max is not None and current_value > alert_max)
        )
        is_warning = (not is_critical) and has_warning and (
            (warn_min is not None and current_value < warn_min) or
            (warn_max is not None and current_value > warn_max)
        )

        try:
            from sqlalchemy import text as _text
            lock_ok = db.session.execute(
                _text('SELECT pg_try_advisory_xact_lock(:k)'),
                {'k': int(parameter_id)}
            ).scalar()
            if not lock_ok:
                logger.debug('[ALERT] Advisory lock busy for param %s - skipping tick', parameter_id)
                return

            # Fetch ALL open episodes; close extras defensively
            open_events = (
                AlertEvent.query
                .filter_by(parameter_id=parameter_id, resolved_at=None)
                .order_by(AlertEvent.triggered_at.desc())
                .all()
            )
            if len(open_events) > 1:
                now_utc = datetime.now(timezone.utc)
                for stale in open_events[1:]:
                    stale.resolved_at = now_utc
                    logger.warning('[ALERT] Closed stale duplicate id=%s for %s', stale.id, parameter_name)
                db.session.flush()

            open_event = open_events[0] if open_events else None

            # -- CRITICAL zone -------------------------------------------------
            if is_critical:
                if open_event is not None and open_event.severity == 'warning':
                    open_event.resolved_at = datetime.now(timezone.utc)
                    db.session.flush()
                    logger.info('[ALERT] Closed WARNING -> entering CRITICAL: %s', parameter_name)
                    _emit_resolved(open_event)
                    open_event = None

                if open_event is None:
                    open_event = AlertEvent(
                        parameter_id=parameter_id,
                        parameter_name=parameter_name,
                        value_at_trigger=current_value,
                        peak_value=current_value,
                        alert_min=alert_min,
                        alert_max=alert_max,
                        severity='critical',
                        triggered_at=datetime.now(timezone.utc),
                    )
                    db.session.add(open_event)
                    db.session.flush()
                    logger.warning('[ALERT] OPENED CRITICAL: %s = %.2f  bounds=[%s, %s]',
                                   parameter_name, current_value, alert_min, alert_max)
                    _emit_triggered(open_event, current_value, alert_min, alert_max, 'critical')
                    _send_push_notification(parameter_name, current_value, alert_min, alert_max, 'critical')
                else:
                    if open_event.peak_value is None or abs(current_value) > abs(open_event.peak_value):
                        open_event.peak_value = current_value

            # -- WARNING zone --------------------------------------------------
            elif is_warning:
                if open_event is not None and open_event.severity == 'critical':
                    open_event.resolved_at = datetime.now(timezone.utc)
                    db.session.flush()
                    logger.info('[ALERT] Closed CRITICAL -> returning to WARNING: %s', parameter_name)
                    _emit_resolved(open_event)
                    open_event = None

                if open_event is None:
                    open_event = AlertEvent(
                        parameter_id=parameter_id,
                        parameter_name=parameter_name,
                        value_at_trigger=current_value,
                        peak_value=current_value,
                        alert_min=warn_min,
                        alert_max=warn_max,
                        severity='warning',
                        triggered_at=datetime.now(timezone.utc),
                    )
                    db.session.add(open_event)
                    db.session.flush()
                    logger.warning('[ALERT] OPENED WARNING: %s = %.2f  bounds=[%s, %s]',
                                   parameter_name, current_value, warn_min, warn_max)
                    _emit_triggered(open_event, current_value, warn_min, warn_max, 'warning')
                    _send_push_notification(parameter_name, current_value, warn_min, warn_max, 'warning')
                else:
                    if open_event.peak_value is None or abs(current_value) > abs(open_event.peak_value):
                        open_event.peak_value = current_value

            # -- SAFE zone -----------------------------------------------------
            else:
                if open_event is not None:
                    open_event.resolved_at = datetime.now(timezone.utc)
                    db.session.flush()
                    dur = open_event.duration_seconds()
                    logger.info('[ALERT] RESOLVED %s: %s  duration=%s',
                                open_event.severity.upper(), parameter_name, _fmt_duration(dur))
                    _emit_resolved(open_event)

            db.session.commit()

        except Exception as exc:
            logger.error('[ALERT] check_range_alert error: %s', exc)
            db.session.rollback()


def close_stale_open_events(stale_threshold_minutes: int = 10) -> int:
    """
    Close any open AlertEvent episodes older than stale_threshold_minutes.
    Called when the desktop goes offline so timers do not run forever.
    Returns the number of events closed.
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=stale_threshold_minutes)
        cutoff_naive = cutoff.replace(tzinfo=None)
        stale = (
            AlertEvent.query
            .filter(AlertEvent.resolved_at.is_(None),
                    AlertEvent.triggered_at <= cutoff_naive)
            .all()
        )
        if not stale:
            return 0
        now = datetime.now(timezone.utc)
        for ev in stale:
            ev.resolved_at = now
        db.session.commit()
        logger.info('[ALERT] Closed %d stale open events (threshold=%dm)', len(stale), stale_threshold_minutes)
        for ev in stale:
            _emit_resolved(ev)
        return len(stale)
    except Exception as exc:
        logger.error('[ALERT] close_stale_open_events error: %s', exc)
        db.session.rollback()
        return 0


def _emit_triggered(event: AlertEvent, current_value: float,
                    eff_min, eff_max, severity: str) -> None:
    """Emit alert_triggered via Socket.IO (safe from any thread)."""
    try:
        from app import get_socketio
        sio = get_socketio()
        if not sio:
            return
        payload = {
            'parameter_id':   event.parameter_id,
            'parameter_name': event.parameter_name,
            'current_value':  current_value,
            'alert_min':      eff_min,
            'alert_max':      eff_max,
            'severity':       severity,
            'triggered_at':   event.triggered_at.isoformat(),
            'message': (
                f'[{severity.upper()}] {event.parameter_name} = {current_value:.2f} '
                f'(range: {eff_min} \u2013 {eff_max})'
            ),
        }
        sio.emit('alert_triggered', payload, namespace='/')
        logger.info('[ALERT] Emitted alert_triggered: %s %s', event.parameter_name, severity)
    except Exception as e:
        logger.error('[ALERT] Socket.IO emit error: %s', e)


def _emit_resolved(event: AlertEvent) -> None:
    """Emit alert_resolved via Socket.IO (safe from any thread)."""
    try:
        from app import get_socketio
        sio = get_socketio()
        if sio:
            sio.emit('alert_resolved', event.to_dict(), namespace='/')
    except Exception as e:
        logger.error('[ALERT] Socket.IO resolve emit error: %s', e)


def _send_push_notification(parameter_name: str, value: float,
                             alert_min, alert_max, severity: str) -> None:
    """Send Web Push notification to all subscribed clients."""
    try:
        from app.models.push_subscription import PushSubscription
        from app.models import db as _db
        import json
        try:
            from pywebpush import webpush, WebPushException
        except ImportError:
            return

        import os
        vapid_private = os.environ.get('VAPID_PRIVATE_KEY', '')
        vapid_email   = os.environ.get('VAPID_EMAIL', 'mailto:admin@precisionpulse.com')
        if not vapid_private:
            return

        subs = PushSubscription.query.all()
        data = json.dumps({
            'title': f'[{severity.upper()}] {parameter_name} out of range',
            'body':  f'{parameter_name} = {value:.2f} (range: {alert_min} \u2013 {alert_max})',
            'severity': severity,
        })
        for sub in subs:
            try:
                webpush(
                    subscription_info=json.loads(sub.subscription_json),
                    data=data,
                    vapid_private_key=vapid_private,
                    vapid_claims={'sub': vapid_email},
                )
            except WebPushException as e:
                if '410' in str(e) or '404' in str(e):
                    _db.session.delete(sub)
                    _db.session.commit()
            except Exception:
                pass
    except Exception as exc:
        logger.debug('[PUSH] Push notification skipped: %s', exc)
