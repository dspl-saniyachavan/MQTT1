"""
Config change buffer model for offline resilience
"""

from app import db
from datetime import datetime


class ConfigChangeBuffer(db.Model):
    """Buffer for config changes when MQTT is disconnected"""
    
    __tablename__ = 'config_change_buffer'
    
    id = db.Column(db.Integer, primary_key=True)
    config_key = db.Column(db.String(255), nullable=False)
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='pending')  # 'pending', 'synced', 'failed'
    retry_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    synced_at = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<ConfigChangeBuffer {self.config_key}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'config_key': self.config_key,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'status': self.status,
            'retry_count': self.retry_count,
            'created_at': self.created_at.isoformat(),
            'synced_at': self.synced_at.isoformat() if self.synced_at else None
        }
