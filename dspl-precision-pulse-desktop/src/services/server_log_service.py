"""
Server log service for tracking all changes and records
"""

from typing import List, Dict, Optional
from datetime import datetime
from src.core.database import DatabaseManager


class ServerLogService:
    """Service for managing server logs"""
    
    def __init__(self, database_manager: DatabaseManager):
        self.db = database_manager
    
    def log_telemetry_received(self, parameter_id: int, value: float, device_id: str = None):
        """Log telemetry data received"""
        self.db.log_server_event(
            event_type='TELEMETRY',
            resource_type='parameter',
            resource_id=str(parameter_id),
            action='received',
            new_value=str(value),
            device_id=device_id
        )
    
    def log_data_synced(self, count: int, device_id: str = None):
        """Log data sync event"""
        self.db.log_server_event(
            event_type='SYNC',
            resource_type='buffer',
            action='synced',
            new_value=str(count),
            status='success',
            device_id=device_id
        )
    
    def log_sync_failed(self, error: str, device_id: str = None):
        """Log sync failure"""
        self.db.log_server_event(
            event_type='SYNC',
            resource_type='buffer',
            action='sync_failed',
            status='failed',
            error_message=error,
            device_id=device_id
        )
    
    def log_mqtt_connected(self, device_id: str = None):
        """Log MQTT connection"""
        self.db.log_server_event(
            event_type='MQTT',
            resource_type='connection',
            action='connected',
            status='success',
            device_id=device_id
        )
    
    def log_mqtt_disconnected(self, device_id: str = None):
        """Log MQTT disconnection"""
        self.db.log_server_event(
            event_type='MQTT',
            resource_type='connection',
            action='disconnected',
            status='success',
            device_id=device_id
        )
    
    def log_mqtt_error(self, error: str, device_id: str = None):
        """Log MQTT error"""
        self.db.log_server_event(
            event_type='MQTT',
            resource_type='connection',
            action='error',
            status='failed',
            error_message=error,
            device_id=device_id
        )
    
    def log_user_login(self, email: str, device_id: str = None):
        """Log user login"""
        self.db.log_server_event(
            event_type='AUTH',
            resource_type='user',
            action='login',
            status='success',
            user_email=email,
            device_id=device_id
        )
    
    def log_user_logout(self, email: str, device_id: str = None):
        """Log user logout"""
        self.db.log_server_event(
            event_type='AUTH',
            resource_type='user',
            action='logout',
            status='success',
            user_email=email,
            device_id=device_id
        )
    
    def log_login_failed(self, email: str, error: str, device_id: str = None):
        """Log failed login"""
        self.db.log_server_event(
            event_type='AUTH',
            resource_type='user',
            action='login_failed',
            status='failed',
            error_message=error,
            user_email=email,
            device_id=device_id
        )
    
    def log_config_changed(self, old_value: str, new_value: str, device_id: str = None):
        """Log configuration change"""
        self.db.log_server_event(
            event_type='CONFIG',
            resource_type='configuration',
            action='changed',
            old_value=old_value,
            new_value=new_value,
            status='success',
            device_id=device_id
        )
    
    def log_parameter_added(self, parameter_id: int, parameter_name: str, device_id: str = None):
        """Log parameter added"""
        self.db.log_server_event(
            event_type='PARAMETER',
            resource_type='parameter',
            resource_id=str(parameter_id),
            action='added',
            new_value=parameter_name,
            status='success',
            device_id=device_id
        )
    
    def log_parameter_removed(self, parameter_id: int, parameter_name: str, device_id: str = None):
        """Log parameter removed"""
        self.db.log_server_event(
            event_type='PARAMETER',
            resource_type='parameter',
            resource_id=str(parameter_id),
            action='removed',
            old_value=parameter_name,
            status='success',
            device_id=device_id
        )
    
    def log_user_created(self, email: str, role: str, device_id: str = None):
        """Log user creation"""
        self.db.log_server_event(
            event_type='USER_MANAGEMENT',
            resource_type='user',
            resource_id=email,
            action='created',
            new_value=role,
            status='success',
            device_id=device_id
        )
    
    def log_user_deleted(self, email: str, device_id: str = None):
        """Log user deletion"""
        self.db.log_server_event(
            event_type='USER_MANAGEMENT',
            resource_type='user',
            resource_id=email,
            action='deleted',
            status='success',
            device_id=device_id
        )
    
    def log_permission_changed(self, role: str, resource: str, action: str, 
                              allowed: bool, device_id: str = None):
        """Log permission change"""
        self.db.log_server_event(
            event_type='PERMISSION',
            resource_type='permission',
            resource_id=f"{role}:{resource}:{action}",
            action='changed',
            new_value=str(allowed),
            status='success',
            device_id=device_id
        )
    
    def get_logs(self, limit: int = 100, event_type: Optional[str] = None) -> List[Dict]:
        """Get server logs"""
        return self.db.get_server_logs(limit=limit, event_type=event_type)
    
    def get_logs_by_event_type(self, event_type: str, limit: int = 100) -> List[Dict]:
        """Get logs filtered by event type"""
        return self.db.get_server_logs(limit=limit, event_type=event_type)
    
    def get_recent_logs(self, limit: int = 50) -> List[Dict]:
        """Get recent logs"""
        return self.db.get_server_logs(limit=limit)
    
    def get_error_logs(self, limit: int = 100) -> List[Dict]:
        """Get error logs"""
        logs = self.db.get_server_logs(limit=limit)
        return [log for log in logs if log['status'] == 'failed']
    
    def get_telemetry_logs(self, limit: int = 100) -> List[Dict]:
        """Get telemetry logs"""
        return self.db.get_server_logs(limit=limit, event_type='TELEMETRY')
    
    def get_sync_logs(self, limit: int = 100) -> List[Dict]:
        """Get sync logs"""
        return self.db.get_server_logs(limit=limit, event_type='SYNC')
    
    def get_auth_logs(self, limit: int = 100) -> List[Dict]:
        """Get authentication logs"""
        return self.db.get_server_logs(limit=limit, event_type='AUTH')
    
    def get_mqtt_logs(self, limit: int = 100) -> List[Dict]:
        """Get MQTT logs"""
        return self.db.get_server_logs(limit=limit, event_type='MQTT')
