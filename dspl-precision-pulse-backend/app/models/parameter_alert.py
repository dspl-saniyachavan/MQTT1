from app.models import db
from datetime import datetime, timezone

class ParameterAlert(db.Model):
    __tablename__ = 'parameter_alerts'

    id = db.Column(db.Integer, primary_key=True)
    parameter_id = db.Column(db.Integer, db.ForeignKey('parameters.id'), nullable=False)
    alert_type = db.Column(db.String(50), nullable=False)   # 'high', 'low', 'critical'
    threshold = db.Column(db.Float, nullable=False)
    message = db.Column(db.String(255), nullable=True)       # e.g. "heat alert"
    is_active = db.Column(db.Boolean, default=True)
    triggered_count = db.Column(db.Integer, default=0)
    last_triggered = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'parameter_id': self.parameter_id,
            'alert_type': self.alert_type,
            'threshold': self.threshold,
            'message': self.message,
            'is_active': self.is_active,
            'triggered_count': self.triggered_count,
            'last_triggered': self.last_triggered.isoformat() if self.last_triggered else None,
            'created_at': self.created_at.isoformat()
        }
