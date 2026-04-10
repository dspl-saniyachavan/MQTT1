"""
Command Execution Model for tracking remote command delivery and execution status
"""

from app.models import db
from datetime import datetime, timezone, timezone
import json

class CommandExecution(db.Model):
    """Model for tracking command execution on remote devices"""
    
    __tablename__ = 'command_executions'
    
    id = db.Column(db.Integer, primary_key=True)
    command_id = db.Column(db.String(36), unique=True, nullable=False, index=True)
    command_type = db.Column(db.String(50), nullable=False)  # force_sync, update_config, restart, etc.
    device_id = db.Column(db.String(100), nullable=True, index=True)  # None for broadcast
    target_type = db.Column(db.String(20), default='device')  # device, broadcast, group
    
    # Command payload
    payload = db.Column(db.JSON, nullable=False)
    
    # Status tracking
    status = db.Column(db.String(20), default='pending')  # pending, sent, delivered, executing, completed, failed, timeout
    delivery_status = db.Column(db.String(20), default='pending')  # pending, sent, delivered, failed
    execution_status = db.Column(db.String(20), default='pending')  # pending, executing, completed, failed
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    sent_at = db.Column(db.DateTime, nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Results
    result_data = db.Column(db.JSON, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    
    # Metadata
    created_by = db.Column(db.String(255), nullable=True)
    retry_count = db.Column(db.Integer, default=0)
    max_retries = db.Column(db.Integer, default=3)
    timeout_seconds = db.Column(db.Integer, default=300)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'command_id': self.command_id,
            'command_type': self.command_type,
            'device_id': self.device_id,
            'target_type': self.target_type,
            'payload': self.payload,
            'status': self.status,
            'delivery_status': self.delivery_status,
            'execution_status': self.execution_status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'result_data': self.result_data,
            'error_message': self.error_message,
            'created_by': self.created_by,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'timeout_seconds': self.timeout_seconds
        }
    
    def __repr__(self):
        return f'<CommandExecution {self.command_id} - {self.command_type} - {self.status}>'


class CommandAcknowledgment(db.Model):
    """Model for tracking command acknowledgments from devices"""
    
    __tablename__ = 'command_acknowledgments'
    
    id = db.Column(db.Integer, primary_key=True)
    command_id = db.Column(db.String(36), nullable=False, index=True)
    device_id = db.Column(db.String(100), nullable=False, index=True)
    
    # Acknowledgment types
    ack_type = db.Column(db.String(20), nullable=False)  # received, executing, completed, failed
    
    # Status
    status = db.Column(db.String(20), nullable=False)  # success, error
    message = db.Column(db.Text, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Result data
    result_data = db.Column(db.JSON, nullable=True)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'command_id': self.command_id,
            'device_id': self.device_id,
            'ack_type': self.ack_type,
            'status': self.status,
            'message': self.message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'result_data': self.result_data
        }
    
    def __repr__(self):
        return f'<CommandAcknowledgment {self.command_id} - {self.device_id} - {self.ack_type}>'
