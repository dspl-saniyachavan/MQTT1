from app.models import db
from datetime import datetime, timezone


class AlertEvent(db.Model):
    __tablename__ = 'alert_events'

    id               = db.Column(db.Integer, primary_key=True)
    parameter_id     = db.Column(db.Integer, db.ForeignKey('parameters.id', ondelete='CASCADE'), nullable=False)
    parameter_name   = db.Column(db.String(100), nullable=False)
    value_at_trigger = db.Column(db.Float, nullable=False)          # value that opened the event
    peak_value       = db.Column(db.Float, nullable=True)           # worst value seen during event
    alert_min        = db.Column(db.Float, nullable=True)           # effective lower bound used
    alert_max        = db.Column(db.Float, nullable=True)           # effective upper bound used
    severity         = db.Column(db.String(20), nullable=False, default='warning')  # 'warning' | 'critical'
    triggered_at     = db.Column(db.DateTime, nullable=False,
                                 default=lambda: datetime.now(timezone.utc))
    resolved_at      = db.Column(db.DateTime, nullable=True)        # NULL = still active

    # ── Helpers ───────────────────────────────────────────────────────────────

    def duration_seconds(self):
        """Return integer seconds between trigger and resolution, or None if still active."""
        if not self.resolved_at:
            return None
        t = self.triggered_at.replace(tzinfo=None) if self.triggered_at.tzinfo else self.triggered_at
        r = self.resolved_at.replace(tzinfo=None)  if self.resolved_at.tzinfo  else self.resolved_at
        return max(0, round((r - t).total_seconds()))

    def to_dict(self):
        dur = self.duration_seconds()
        return {
            'id':               self.id,
            'parameter_id':     self.parameter_id,
            'parameter_name':   self.parameter_name,
            'value_at_trigger': self.value_at_trigger,
            'peak_value':       self.peak_value if self.peak_value is not None else self.value_at_trigger,
            'alert_min':        self.alert_min,
            'alert_max':        self.alert_max,
            'severity':         self.severity or 'warning',
            'triggered_at':     self.triggered_at.isoformat(),
            'resolved_at':      self.resolved_at.isoformat() if self.resolved_at else None,
            'duration_seconds': dur,
            'duration_label':   _fmt_duration(dur),
            'active':           self.resolved_at is None,
        }


def _fmt_duration(seconds):
    if seconds is None:
        return 'Ongoing'
    if seconds < 60:
        return f'{seconds}s'
    if seconds < 3600:
        return f'{seconds // 60}m {seconds % 60}s'
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f'{h}h {m}m'
