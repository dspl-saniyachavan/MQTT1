"""
Log Retention and Cleanup Service for managing audit log lifecycle
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any
from app.models import db
from app.models.audit_log import AuditLog
from sqlalchemy import func


class LogRetentionService:
    """Service for managing log retention and cleanup"""
    
    # Default retention policies (in days)
    DEFAULT_RETENTION_POLICIES = {
        'info': 30,           # Info logs: 30 days
        'warning': 60,        # Warning logs: 60 days
        'error': 90,          # Error logs: 90 days
        'critical': 365       # Critical logs: 1 year
    }
    
    # Event-specific retention (in days)
    EVENT_RETENTION_POLICIES = {
        'telemetry_received': 7,
        'telemetry_buffered': 7,
        'telemetry_flushed': 7,
        'command_sent': 30,
        'command_executed': 30,
        'command_failed': 90,
        'config_updated': 90,
        'config_synced': 30,
        'login_success': 30,
        'login_failed': 60,
        'security_violation': 365,
        'replay_attack_detected': 365,
        'signature_verification_failed': 365
    }
    
    def __init__(self):
        self.retention_policies = self.DEFAULT_RETENTION_POLICIES.copy()
        self.event_policies = self.EVENT_RETENTION_POLICIES.copy()
    
    def set_retention_policy(self, severity: str, days: int):
        """Set retention policy for severity level"""
        if severity in self.retention_policies:
            self.retention_policies[severity] = days
            print(f"[RETENTION] Set {severity} retention to {days} days")
    
    def set_event_retention_policy(self, event_type: str, days: int):
        """Set retention policy for specific event type"""
        self.event_policies[event_type] = days
        print(f"[RETENTION] Set {event_type} retention to {days} days")
    
    def get_retention_days(self, log: AuditLog) -> int:
        """
        Get retention days for a specific log entry
        
        Uses event-specific policy if available, otherwise uses severity-based policy
        """
        # Check event-specific policy first
        if log.event_type in self.event_policies:
            return self.event_policies[log.event_type]
        
        # Fall back to severity-based policy
        return self.retention_policies.get(log.severity, 30)
    
    def cleanup_expired_logs(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Clean up expired logs based on retention policies
        
        Args:
            dry_run: If True, only report what would be deleted without deleting
        
        Returns:
            Cleanup statistics
        """
        try:
            now = datetime.now(timezone.utc)
            deleted_count = 0
            deleted_by_severity = {}
            deleted_by_event = {}
            
            # Get all logs
            all_logs = AuditLog.query.all()
            logs_to_delete = []
            
            for log in all_logs:
                retention_days = self.get_retention_days(log)
                expiration_date = log.created_at + timedelta(days=retention_days)
                
                if now > expiration_date:
                    logs_to_delete.append(log)
                    deleted_count += 1
                    
                    # Track by severity
                    severity = log.severity
                    deleted_by_severity[severity] = deleted_by_severity.get(severity, 0) + 1
                    
                    # Track by event type
                    event_type = log.event_type
                    deleted_by_event[event_type] = deleted_by_event.get(event_type, 0) + 1
            
            # Perform deletion if not dry run
            if not dry_run and logs_to_delete:
                for log in logs_to_delete:
                    db.session.delete(log)
                db.session.commit()
                print(f"[RETENTION] Deleted {deleted_count} expired logs")
            elif dry_run:
                print(f"[RETENTION] DRY RUN: Would delete {deleted_count} expired logs")
            
            return {
                'success': True,
                'deleted_count': deleted_count,
                'deleted_by_severity': deleted_by_severity,
                'deleted_by_event': deleted_by_event,
                'dry_run': dry_run,
                'timestamp': now.isoformat()
            }
        
        except Exception as e:
            print(f"[RETENTION] Error during cleanup: {e}")
            db.session.rollback()
            return {
                'success': False,
                'error': str(e)
            }
    
    def cleanup_by_severity(self, severity: str, dry_run: bool = False) -> Dict[str, Any]:
        """Clean up logs by severity level"""
        try:
            now = datetime.now(timezone.utc)
            retention_days = self.retention_policies.get(severity, 30)
            cutoff_date = now - timedelta(days=retention_days)
            
            query = AuditLog.query.filter(
                AuditLog.severity == severity,
                AuditLog.created_at < cutoff_date
            )
            
            deleted_count = query.count()
            
            if not dry_run:
                query.delete()
                db.session.commit()
                print(f"[RETENTION] Deleted {deleted_count} {severity} logs")
            
            return {
                'success': True,
                'severity': severity,
                'deleted_count': deleted_count,
                'cutoff_date': cutoff_date.isoformat(),
                'dry_run': dry_run
            }
        
        except Exception as e:
            print(f"[RETENTION] Error cleaning up {severity} logs: {e}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    def cleanup_by_event_type(self, event_type: str, dry_run: bool = False) -> Dict[str, Any]:
        """Clean up logs by event type"""
        try:
            now = datetime.now(timezone.utc)
            retention_days = self.event_policies.get(event_type, 30)
            cutoff_date = now - timedelta(days=retention_days)
            
            query = AuditLog.query.filter(
                AuditLog.event_type == event_type,
                AuditLog.created_at < cutoff_date
            )
            
            deleted_count = query.count()
            
            if not dry_run:
                query.delete()
                db.session.commit()
                print(f"[RETENTION] Deleted {deleted_count} {event_type} logs")
            
            return {
                'success': True,
                'event_type': event_type,
                'deleted_count': deleted_count,
                'cutoff_date': cutoff_date.isoformat(),
                'dry_run': dry_run
            }
        
        except Exception as e:
            print(f"[RETENTION] Error cleaning up {event_type} logs: {e}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    def cleanup_old_logs(self, days: int, dry_run: bool = False) -> Dict[str, Any]:
        """Clean up all logs older than specified days"""
        try:
            now = datetime.now(timezone.utc)
            cutoff_date = now - timedelta(days=days)
            
            query = AuditLog.query.filter(AuditLog.created_at < cutoff_date)
            deleted_count = query.count()
            
            if not dry_run:
                query.delete()
                db.session.commit()
                print(f"[RETENTION] Deleted {deleted_count} logs older than {days} days")
            
            return {
                'success': True,
                'days': days,
                'deleted_count': deleted_count,
                'cutoff_date': cutoff_date.isoformat(),
                'dry_run': dry_run
            }
        
        except Exception as e:
            print(f"[RETENTION] Error cleaning up old logs: {e}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    def get_retention_statistics(self) -> Dict[str, Any]:
        """Get statistics about log retention"""
        try:
            now = datetime.now(timezone.utc)
            
            # Total logs
            total_logs = AuditLog.query.count()
            
            # Logs by severity
            severity_counts = AuditLog.query.with_entities(
                AuditLog.severity,
                func.count(AuditLog.id).label('count')
            ).group_by(AuditLog.severity).all()
            
            # Logs by age
            age_distribution = {
                '0-7_days': AuditLog.query.filter(
                    AuditLog.created_at >= now - timedelta(days=7)
                ).count(),
                '7-30_days': AuditLog.query.filter(
                    AuditLog.created_at >= now - timedelta(days=30),
                    AuditLog.created_at < now - timedelta(days=7)
                ).count(),
                '30-90_days': AuditLog.query.filter(
                    AuditLog.created_at >= now - timedelta(days=90),
                    AuditLog.created_at < now - timedelta(days=30)
                ).count(),
                '90+_days': AuditLog.query.filter(
                    AuditLog.created_at < now - timedelta(days=90)
                ).count()
            }
            
            # Logs expiring soon (within 7 days)
            expiring_soon = 0
            for log in AuditLog.query.all():
                retention_days = self.get_retention_days(log)
                expiration_date = log.created_at + timedelta(days=retention_days)
                if now <= expiration_date <= now + timedelta(days=7):
                    expiring_soon += 1
            
            # Expired logs
            expired_logs = 0
            for log in AuditLog.query.all():
                retention_days = self.get_retention_days(log)
                expiration_date = log.created_at + timedelta(days=retention_days)
                if now > expiration_date:
                    expired_logs += 1
            
            return {
                'total_logs': total_logs,
                'severity_distribution': [
                    {'severity': s[0], 'count': s[1]} for s in severity_counts
                ],
                'age_distribution': age_distribution,
                'expiring_soon': expiring_soon,
                'expired_logs': expired_logs,
                'retention_policies': self.retention_policies,
                'timestamp': now.isoformat()
            }
        
        except Exception as e:
            print(f"[RETENTION] Error getting statistics: {e}")
            return {'error': str(e)}
    
    def archive_logs(self, days: int, archive_path: str = None) -> Dict[str, Any]:
        """
        Archive logs older than specified days
        
        Args:
            days: Archive logs older than this many days
            archive_path: Path to save archive (optional)
        
        Returns:
            Archive statistics
        """
        try:
            now = datetime.now(timezone.utc)
            cutoff_date = now - timedelta(days=days)
            
            logs_to_archive = AuditLog.query.filter(
                AuditLog.created_at < cutoff_date
            ).all()
            
            archive_data = {
                'archived_at': now.isoformat(),
                'cutoff_date': cutoff_date.isoformat(),
                'log_count': len(logs_to_archive),
                'logs': [log.to_dict() for log in logs_to_archive]
            }
            
            # Save to file if path provided
            if archive_path:
                import json
                with open(archive_path, 'w') as f:
                    json.dump(archive_data, f, indent=2)
                print(f"[RETENTION] Archived {len(logs_to_archive)} logs to {archive_path}")
            
            return {
                'success': True,
                'archived_count': len(logs_to_archive),
                'cutoff_date': cutoff_date.isoformat(),
                'archive_path': archive_path
            }
        
        except Exception as e:
            print(f"[RETENTION] Error archiving logs: {e}")
            return {'success': False, 'error': str(e)}


def get_log_retention_service() -> LogRetentionService:
    """Get or create log retention service instance"""
    return LogRetentionService()
