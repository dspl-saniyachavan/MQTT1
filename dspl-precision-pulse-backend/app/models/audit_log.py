"""
Audit Log Model for tracking all critical system events
"""

from app.models import db
from datetime import datetime, timezone, timezone
from enum import Enum


class AuditEventType(Enum):
    """Types of audit events"""
    # Telemetry events
    TELEMETRY_RECEIVED = "telemetry_received"
    TELEMETRY_BUFFERED = "telemetry_buffered"
    TELEMETRY_FLUSHED = "telemetry_flushed"
    
    # Command execution events
    COMMAND_SENT = "command_sent"
    COMMAND_DELIVERED = "command_delivered"
    COMMAND_EXECUTED = "command_executed"
    COMMAND_FAILED = "command_failed"
    COMMAND_ACKNOWLEDGED = "command_acknowledged"
    
    # Configuration events
    CONFIG_CREATED = "config_created"
    CONFIG_UPDATED = "config_updated"
    CONFIG_DELETED = "config_deleted"
    CONFIG_SYNCED = "config_synced"
    CONFIG_BULK_UPDATE = "config_bulk_update"
    
    # User management events
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_PASSWORD_CHANGED = "user_password_changed"
    USER_ROLE_CHANGED = "user_role_changed"
    USER_ACTIVATED = "user_activated"
    USER_DEACTIVATED = "user_deactivated"
    
    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    TOKEN_GENERATED = "token_generated"
    TOKEN_REVOKED = "token_revoked"
    
    # Parameter events
    PARAMETER_CREATED = "parameter_created"
    PARAMETER_UPDATED = "parameter_updated"
    PARAMETER_DELETED = "parameter_deleted"
    PARAMETER_SYNCED = "parameter_synced"
    
    # System events
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    MQTT_CONNECTED = "mqtt_connected"
    MQTT_DISCONNECTED = "mqtt_disconnected"
    
    # Security events
    SECURITY_VIOLATION = "security_violation"
    REPLAY_ATTACK_DETECTED = "replay_attack_detected"
    SIGNATURE_VERIFICATION_FAILED = "signature_verification_failed"
    UNAUTHORIZED_ACCESS = "unauthorized_access"


class AuditSeverity(Enum):
    """Severity levels for audit events"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditLog(db.Model):
    """Model for audit logging"""
    
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Event information
    event_type = db.Column(db.String(50), nullable=False, index=True)
    severity = db.Column(db.String(20), default='info', nullable=False)
    
    # Actor information
    actor_id = db.Column(db.Integer, nullable=True, index=True)  # User ID who performed action
    actor_email = db.Column(db.String(120), nullable=True)
    actor_ip = db.Column(db.String(45), nullable=True)  # IPv4 or IPv6
    
    # Resource information
    resource_type = db.Column(db.String(50), nullable=True)  # user, config, command, parameter, etc.
    resource_id = db.Column(db.String(255), nullable=True, index=True)
    resource_name = db.Column(db.String(255), nullable=True)
    
    # Action details
    action = db.Column(db.String(50), nullable=False)  # create, read, update, delete, execute
    description = db.Column(db.Text, nullable=True)
    
    # Changes (for update operations)
    old_values = db.Column(db.JSON, nullable=True)
    new_values = db.Column(db.JSON, nullable=True)
    
    # Additional context
    context = db.Column(db.JSON, nullable=True)  # Additional metadata
    
    # Status
    status = db.Column(db.String(20), default='success')  # success, failure
    error_message = db.Column(db.Text, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    # Device information
    device_id = db.Column(db.String(100), nullable=True, index=True)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'event_type': self.event_type,
            'severity': self.severity,
            'actor_id': self.actor_id,
            'actor_email': self.actor_email,
            'actor_ip': self.actor_ip,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'resource_name': self.resource_name,
            'action': self.action,
            'description': self.description,
            'old_values': self.old_values,
            'new_values': self.new_values,
            'context': self.context,
            'status': self.status,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'device_id': self.device_id
        }
    
    def __repr__(self):
        return f'<AuditLog {self.event_type} - {self.resource_type} - {self.status}>'
