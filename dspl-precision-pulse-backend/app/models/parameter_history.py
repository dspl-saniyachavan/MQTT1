"""
Parameter History model to track parameter changes over time
"""
from app.models import db
from datetime import datetime, timezone, timezone

class ParameterHistory(db.Model):
    __tablename__ = 'parameter_history'
    
    id = db.Column(db.Integer, primary_key=True)
    parameter_id = db.Column(db.Integer, db.ForeignKey('parameters.id'), nullable=False)
    old_value = db.Column(db.Float, nullable=True)
    new_value = db.Column(db.Float, nullable=False)
    changed_by = db.Column(db.String(120), nullable=True)  # User email
    change_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        return {
            'id': self.id,
            'parameter_id': self.parameter_id,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'changed_by': self.changed_by,
            'change_reason': self.change_reason,
            'created_at': self.created_at.isoformat()
        }
