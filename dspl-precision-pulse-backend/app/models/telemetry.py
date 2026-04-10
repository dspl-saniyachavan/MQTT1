from app.models import db
from datetime import datetime, timezone, timezone

class Telemetry(db.Model):
    """Model for storing telemetry data from devices"""
    __tablename__ = 'telemetry'
    
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(255), nullable=False, index=True)
    parameter_id = db.Column(db.Integer, nullable=False)
    parameter_name = db.Column(db.String(255), nullable=False)
    value = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'parameter_id': self.parameter_id,
            'parameter_name': self.parameter_name,
            'value': self.value,
            'unit': self.unit,
            'timestamp': self.timestamp.isoformat()
        }
