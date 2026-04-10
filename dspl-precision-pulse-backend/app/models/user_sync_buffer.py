"""
User sync buffer model for offline resilience
"""

from app import db
from datetime import datetime
import json


class UserSyncBuffer(db.Model):
    """Buffer for user changes when MQTT is disconnected"""
    
    __tablename__ = 'user_sync_buffer'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # 'create', 'update', 'delete'
    user_data = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(50), default='pending')  # 'pending', 'synced', 'failed'
    retry_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    synced_at = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<UserSyncBuffer {self.user_id} {self.action}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'user_data': self.user_data,
            'status': self.status,
            'retry_count': self.retry_count,
            'created_at': self.created_at.isoformat(),
            'synced_at': self.synced_at.isoformat() if self.synced_at else None
        }
