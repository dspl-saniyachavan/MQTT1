from app.models import db
from datetime import datetime, timezone, timezone

class ConflictLog(db.Model):
    __tablename__ = 'conflict_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    resource_type = db.Column(db.String(50), nullable=False)  # user, parameter, config
    resource_id = db.Column(db.String(255), nullable=False)
    backend_version = db.Column(db.JSON, nullable=True)
    desktop_version = db.Column(db.JSON, nullable=True)
    resolution_strategy = db.Column(db.String(50), nullable=True)  # backend_wins, desktop_wins, manual
    resolved_version = db.Column(db.JSON, nullable=True)
    resolved = db.Column(db.Boolean, default=False)
    resolved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        return {
            'id': self.id,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'backend_version': self.backend_version,
            'desktop_version': self.desktop_version,
            'resolution_strategy': self.resolution_strategy,
            'resolved': self.resolved,
            'created_at': self.created_at.isoformat()
        }
