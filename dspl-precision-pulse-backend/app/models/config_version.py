from app.models import db
from datetime import datetime, timezone, timezone

class ConfigVersion(db.Model):
    __tablename__ = 'config_versions'
    
    id = db.Column(db.Integer, primary_key=True)
    config_id = db.Column(db.Integer, db.ForeignKey('system_config.id'), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    config_data = db.Column(db.JSON, nullable=False)
    changed_by = db.Column(db.String(120), nullable=True)
    change_description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        return {
            'id': self.id,
            'config_id': self.config_id,
            'version_number': self.version_number,
            'config_data': self.config_data,
            'changed_by': self.changed_by,
            'change_description': self.change_description,
            'created_at': self.created_at.isoformat()
        }
