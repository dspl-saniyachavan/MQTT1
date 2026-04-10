"""
Audit Logging Service for tracking all critical system events
"""

import json
from datetime import datetime
from typing import Dict, Optional, Any, List
from app.models import db
from app.models.audit_log import AuditLog, AuditEventType, AuditSeverity


class AuditLoggingService:
    """Service for logging audit events"""
    
    def __init__(self):
        self.event_handlers = {}
    
    def log_event(
        self,
        event_type: str,
        action: str,
        resource_type: str = None,
        resource_id: str = None,
        resource_name: str = None,
        actor_id: int = None,
        actor_email: str = None,
        actor_ip: str = None,
        device_id: str = None,
        old_values: Dict = None,
        new_values: Dict = None,
        context: Dict = None,
        description: str = None,
        status: str = 'success',
        error_message: str = None,
        severity: str = 'info'
    ) -> Optional[AuditLog]:
        """
        Log an audit event
        
        Args:
            event_type: Type of event (from AuditEventType)
            action: Action performed (create, read, update, delete, execute)
            resource_type: Type of resource affected
            resource_id: ID of resource affected
            resource_name: Name of resource affected
            actor_id: ID of user performing action
            actor_email: Email of user performing action
            actor_ip: IP address of actor
            device_id: Device ID if applicable
            old_values: Previous values (for updates)
            new_values: New values (for updates)
            context: Additional context data
            description: Human-readable description
            status: success or failure
            error_message: Error message if failed
            severity: info, warning, error, critical
        
        Returns:
            Created AuditLog object or None if error
        """
        try:
            # Sanitize sensitive data
            old_values = self._sanitize_values(old_values)
            new_values = self._sanitize_values(new_values)
            context = self._sanitize_values(context)
            
            # Create audit log entry
            audit_log = AuditLog(
                event_type=event_type,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                resource_name=resource_name,
                actor_id=actor_id,
                actor_email=actor_email,
                actor_ip=actor_ip,
                device_id=device_id,
                old_values=old_values,
                new_values=new_values,
                context=context,
                description=description,
                status=status,
                error_message=error_message,
                severity=severity
            )
            
            db.session.add(audit_log)
            db.session.commit()
            
            print(f"[AUDIT] {event_type} - {action} - {resource_type}:{resource_id} - {status}")
            
            # Call event handlers
            self._call_handlers(event_type, audit_log)
            
            return audit_log
        
        except Exception as e:
            print(f"[AUDIT] Error logging event: {e}")
            db.session.rollback()
            return None
    
    def log_telemetry_received(
        self,
        device_id: str,
        parameter_count: int,
        context: Dict = None
    ) -> Optional[AuditLog]:
        """Log telemetry received event"""
        return self.log_event(
            event_type=AuditEventType.TELEMETRY_RECEIVED.value,
            action='receive',
            resource_type='telemetry',
            resource_id=device_id,
            device_id=device_id,
            context={
                'parameter_count': parameter_count,
                **(context or {})
            },
            description=f'Telemetry received from {device_id} with {parameter_count} parameters'
        )
    
    def log_telemetry_buffered(
        self,
        device_id: str,
        record_count: int,
        context: Dict = None
    ) -> Optional[AuditLog]:
        """Log telemetry buffered event"""
        return self.log_event(
            event_type=AuditEventType.TELEMETRY_BUFFERED.value,
            action='buffer',
            resource_type='telemetry',
            resource_id=device_id,
            device_id=device_id,
            context={
                'record_count': record_count,
                **(context or {})
            },
            description=f'{record_count} telemetry records buffered for {device_id}'
        )
    
    def log_telemetry_flushed(
        self,
        device_id: str,
        record_count: int,
        context: Dict = None
    ) -> Optional[AuditLog]:
        """Log telemetry flushed event"""
        return self.log_event(
            event_type=AuditEventType.TELEMETRY_FLUSHED.value,
            action='flush',
            resource_type='telemetry',
            resource_id=device_id,
            device_id=device_id,
            context={
                'record_count': record_count,
                **(context or {})
            },
            description=f'{record_count} telemetry records flushed for {device_id}'
        )
    
    def log_command_sent(
        self,
        command_id: str,
        command_type: str,
        device_id: str,
        actor_email: str = None,
        context: Dict = None
    ) -> Optional[AuditLog]:
        """Log command sent event"""
        return self.log_event(
            event_type=AuditEventType.COMMAND_SENT.value,
            action='send',
            resource_type='command',
            resource_id=command_id,
            resource_name=command_type,
            actor_email=actor_email,
            device_id=device_id,
            context={
                'command_type': command_type,
                **(context or {})
            },
            description=f'Command {command_type} sent to {device_id}'
        )
    
    def log_command_delivered(
        self,
        command_id: str,
        device_id: str,
        context: Dict = None
    ) -> Optional[AuditLog]:
        """Log command delivered event"""
        return self.log_event(
            event_type=AuditEventType.COMMAND_DELIVERED.value,
            action='deliver',
            resource_type='command',
            resource_id=command_id,
            device_id=device_id,
            context=context,
            description=f'Command {command_id} delivered to {device_id}'
        )
    
    def log_command_executed(
        self,
        command_id: str,
        device_id: str,
        result_data: Dict = None,
        context: Dict = None
    ) -> Optional[AuditLog]:
        """Log command executed event"""
        return self.log_event(
            event_type=AuditEventType.COMMAND_EXECUTED.value,
            action='execute',
            resource_type='command',
            resource_id=command_id,
            device_id=device_id,
            context={
                'result': result_data,
                **(context or {})
            },
            description=f'Command {command_id} executed on {device_id}'
        )
    
    def log_command_failed(
        self,
        command_id: str,
        device_id: str,
        error_message: str,
        context: Dict = None
    ) -> Optional[AuditLog]:
        """Log command failed event"""
        return self.log_event(
            event_type=AuditEventType.COMMAND_FAILED.value,
            action='execute',
            resource_type='command',
            resource_id=command_id,
            device_id=device_id,
            status='failure',
            error_message=error_message,
            severity='error',
            context=context,
            description=f'Command {command_id} failed on {device_id}'
        )
    
    def log_config_created(
        self,
        config_id: str,
        config_name: str,
        new_values: Dict,
        actor_email: str = None,
        context: Dict = None
    ) -> Optional[AuditLog]:
        """Log configuration created event"""
        return self.log_event(
            event_type=AuditEventType.CONFIG_CREATED.value,
            action='create',
            resource_type='config',
            resource_id=config_id,
            resource_name=config_name,
            actor_email=actor_email,
            new_values=new_values,
            context=context,
            description=f'Configuration {config_name} created'
        )
    
    def log_config_updated(
        self,
        config_id: str,
        config_name: str,
        old_values: Dict,
        new_values: Dict,
        actor_email: str = None,
        context: Dict = None
    ) -> Optional[AuditLog]:
        """Log configuration updated event"""
        return self.log_event(
            event_type=AuditEventType.CONFIG_UPDATED.value,
            action='update',
            resource_type='config',
            resource_id=config_id,
            resource_name=config_name,
            actor_email=actor_email,
            old_values=old_values,
            new_values=new_values,
            context=context,
            description=f'Configuration {config_name} updated'
        )
    
    def log_config_deleted(
        self,
        config_id: str,
        config_name: str,
        actor_email: str = None,
        context: Dict = None
    ) -> Optional[AuditLog]:
        """Log configuration deleted event"""
        return self.log_event(
            event_type=AuditEventType.CONFIG_DELETED.value,
            action='delete',
            resource_type='config',
            resource_id=config_id,
            resource_name=config_name,
            actor_email=actor_email,
            context=context,
            description=f'Configuration {config_name} deleted'
        )
    
    def log_user_created(
        self,
        user_id: int,
        user_email: str,
        new_values: Dict,
        actor_email: str = None,
        context: Dict = None
    ) -> Optional[AuditLog]:
        """Log user created event"""
        return self.log_event(
            event_type=AuditEventType.USER_CREATED.value,
            action='create',
            resource_type='user',
            resource_id=str(user_id),
            resource_name=user_email,
            actor_email=actor_email,
            new_values=new_values,
            context=context,
            description=f'User {user_email} created'
        )
    
    def log_user_updated(
        self,
        user_id: int,
        user_email: str,
        old_values: Dict,
        new_values: Dict,
        actor_email: str = None,
        context: Dict = None
    ) -> Optional[AuditLog]:
        """Log user updated event"""
        return self.log_event(
            event_type=AuditEventType.USER_UPDATED.value,
            action='update',
            resource_type='user',
            resource_id=str(user_id),
            resource_name=user_email,
            actor_email=actor_email,
            old_values=old_values,
            new_values=new_values,
            context=context,
            description=f'User {user_email} updated'
        )
    
    def log_user_deleted(
        self,
        user_id: int,
        user_email: str,
        actor_email: str = None,
        context: Dict = None
    ) -> Optional[AuditLog]:
        """Log user deleted event"""
        return self.log_event(
            event_type=AuditEventType.USER_DELETED.value,
            action='delete',
            resource_type='user',
            resource_id=str(user_id),
            resource_name=user_email,
            actor_email=actor_email,
            context=context,
            description=f'User {user_email} deleted'
        )
    
    def log_user_password_changed(
        self,
        user_id: int,
        user_email: str,
        actor_email: str = None,
        context: Dict = None
    ) -> Optional[AuditLog]:
        """Log user password changed event"""
        return self.log_event(
            event_type=AuditEventType.USER_PASSWORD_CHANGED.value,
            action='update',
            resource_type='user',
            resource_id=str(user_id),
            resource_name=user_email,
            actor_email=actor_email,
            context=context,
            description=f'Password changed for user {user_email}'
        )
    
    def log_user_role_changed(
        self,
        user_id: int,
        user_email: str,
        old_role: str,
        new_role: str,
        actor_email: str = None,
        context: Dict = None
    ) -> Optional[AuditLog]:
        """Log user role changed event"""
        return self.log_event(
            event_type=AuditEventType.USER_ROLE_CHANGED.value,
            action='update',
            resource_type='user',
            resource_id=str(user_id),
            resource_name=user_email,
            actor_email=actor_email,
            old_values={'role': old_role},
            new_values={'role': new_role},
            context=context,
            description=f'Role changed for user {user_email} from {old_role} to {new_role}'
        )
    
    def log_login_success(
        self,
        user_id: int,
        user_email: str,
        actor_ip: str = None,
        context: Dict = None
    ) -> Optional[AuditLog]:
        """Log successful login event"""
        return self.log_event(
            event_type=AuditEventType.LOGIN_SUCCESS.value,
            action='login',
            resource_type='user',
            resource_id=str(user_id),
            resource_name=user_email,
            actor_email=user_email,
            actor_ip=actor_ip,
            context=context,
            description=f'User {user_email} logged in successfully'
        )
    
    def log_login_failed(
        self,
        user_email: str,
        actor_ip: str = None,
        error_message: str = None,
        context: Dict = None
    ) -> Optional[AuditLog]:
        """Log failed login event"""
        return self.log_event(
            event_type=AuditEventType.LOGIN_FAILED.value,
            action='login',
            resource_type='user',
            resource_name=user_email,
            actor_email=user_email,
            actor_ip=actor_ip,
            status='failure',
            error_message=error_message or 'Invalid credentials',
            severity='warning',
            context=context,
            description=f'Login failed for user {user_email}'
        )
    
    def log_security_violation(
        self,
        violation_type: str,
        description: str,
        actor_ip: str = None,
        context: Dict = None
    ) -> Optional[AuditLog]:
        """Log security violation event"""
        return self.log_event(
            event_type=AuditEventType.SECURITY_VIOLATION.value,
            action='detect',
            resource_type='security',
            resource_name=violation_type,
            actor_ip=actor_ip,
            status='failure',
            severity='critical',
            context=context,
            description=description
        )
    
    def log_replay_attack_detected(
        self,
        nonce: str,
        actor_ip: str = None,
        context: Dict = None
    ) -> Optional[AuditLog]:
        """Log replay attack detection"""
        return self.log_event(
            event_type=AuditEventType.REPLAY_ATTACK_DETECTED.value,
            action='detect',
            resource_type='security',
            resource_id=nonce,
            actor_ip=actor_ip,
            status='failure',
            severity='critical',
            context=context,
            description=f'Replay attack detected with nonce {nonce[:8]}...'
        )
    
    def get_audit_logs(
        self,
        event_type: str = None,
        resource_type: str = None,
        actor_email: str = None,
        device_id: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        limit: int = 100,
        offset: int = 0
    ) -> tuple:
        """
        Query audit logs with filters
        
        Returns:
            Tuple of (logs, total_count)
        """
        try:
            query = AuditLog.query
            
            if event_type:
                query = query.filter_by(event_type=event_type)
            if resource_type:
                query = query.filter_by(resource_type=resource_type)
            if actor_email:
                query = query.filter_by(actor_email=actor_email)
            if device_id:
                query = query.filter_by(device_id=device_id)
            if start_date:
                query = query.filter(AuditLog.created_at >= start_date)
            if end_date:
                query = query.filter(AuditLog.created_at <= end_date)
            
            total_count = query.count()
            
            logs = query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset).all()
            
            return logs, total_count
        
        except Exception as e:
            print(f"[AUDIT] Error querying logs: {e}")
            return [], 0
    
    def get_user_activity(
        self,
        user_email: str,
        limit: int = 50
    ) -> List[AuditLog]:
        """Get activity log for a specific user"""
        try:
            return AuditLog.query.filter_by(actor_email=user_email).order_by(
                AuditLog.created_at.desc()
            ).limit(limit).all()
        except Exception as e:
            print(f"[AUDIT] Error getting user activity: {e}")
            return []
    
    def get_resource_history(
        self,
        resource_type: str,
        resource_id: str
    ) -> List[AuditLog]:
        """Get change history for a specific resource"""
        try:
            return AuditLog.query.filter_by(
                resource_type=resource_type,
                resource_id=resource_id
            ).order_by(AuditLog.created_at.desc()).all()
        except Exception as e:
            print(f"[AUDIT] Error getting resource history: {e}")
            return []
    
    def register_event_handler(self, event_type: str, handler):
        """Register a handler for specific event type"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    def _call_handlers(self, event_type: str, audit_log: AuditLog):
        """Call registered handlers for event"""
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    handler(audit_log)
                except Exception as e:
                    print(f"[AUDIT] Error calling handler: {e}")
    
    def _sanitize_values(self, values: Dict) -> Optional[Dict]:
        """Sanitize sensitive data from values"""
        if not values:
            return None
        
        sanitized = values.copy()
        
        # List of sensitive fields to redact
        sensitive_fields = [
            'password', 'password_hash', 'token', 'secret', 'api_key',
            'private_key', 'signing_key', 'access_token', 'refresh_token'
        ]
        
        for field in sensitive_fields:
            if field in sanitized:
                sanitized[field] = '***REDACTED***'
        
        return sanitized


# Global instance
_audit_service = None


def get_audit_logging_service() -> AuditLoggingService:
    """Get or create audit logging service instance"""
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditLoggingService()
    return _audit_service
