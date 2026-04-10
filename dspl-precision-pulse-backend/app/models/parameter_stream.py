from app.models import db
from datetime import datetime, timezone


class ParameterStream(db.Model):
    """Model to store parameter streaming data from devices - matches desktop SQLite schema"""
    __tablename__ = 'parameter_stream'
    
    id = db.Column(db.Integer, primary_key=True)
    parameter_id = db.Column(db.Integer, db.ForeignKey('parameters.id'), nullable=False, index=True)
    value = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, index=True, default=lambda: datetime.now(timezone.utc))
    synced = db.Column(db.Boolean, default=False, index=True)
    
    __table_args__ = (
        db.Index('idx_parameter_stream_param_id', 'parameter_id'),
        db.Index('idx_parameter_stream_timestamp', 'timestamp'),
        db.Index('idx_parameter_stream_synced', 'synced'),
        # Composite index for the dedup window query (parameter_id + timestamp)
        db.Index('idx_parameter_stream_param_ts', 'parameter_id', 'timestamp'),
    )
    
    def to_dict(self):
        ts = self.timestamp
        # Ensure timezone-aware for ISO format
        if ts and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return {
            'id': self.id,
            'parameter_id': self.parameter_id,
            'value': self.value,
            'timestamp': ts.isoformat() if ts else None,
            'synced': self.synced
        }
