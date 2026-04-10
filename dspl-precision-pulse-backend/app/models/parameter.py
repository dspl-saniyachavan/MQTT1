from app.models import db
from datetime import datetime, timezone

class Parameter(db.Model):
    __tablename__ = 'parameters'

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False, unique=True)
    unit        = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text)
    enabled     = db.Column(db.Boolean, default=True, nullable=False)
    # Critical thresholds — value outside this range = CRITICAL alert
    alert_min   = db.Column(db.Float, nullable=True)
    alert_max   = db.Column(db.Float, nullable=True)
    # Warning thresholds — value outside this range (but inside critical) = WARNING alert
    warn_min    = db.Column(db.Float, nullable=True)
    warn_max    = db.Column(db.Float, nullable=True)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f'<Parameter {self.name}>'

    def to_dict(self):
        return {
            'id':          self.id,
            'name':        self.name,
            'unit':        self.unit,
            'description': self.description,
            'enabled':     self.enabled,
            'alert_min':   self.alert_min,
            'alert_max':   self.alert_max,
            'warn_min':    self.warn_min,
            'warn_max':    self.warn_max,
            'created_at':  self.created_at.isoformat() if self.created_at else None,
            'updated_at':  self.updated_at.isoformat() if self.updated_at else None,
        }
