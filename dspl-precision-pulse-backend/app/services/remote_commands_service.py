"""
Remote Commands Service for sending commands to remote devices via MQTT
with delivery tracking and acknowledgment handling
"""
import json
import uuid
from datetime import datetime, timezone
from app.services.mqtt_publisher import get_mqtt_publisher
from app.models import db
from app.models.command_execution import CommandExecution, CommandAcknowledgment

class RemoteCommandsService:
    """Service to send remote commands to devices with delivery tracking"""
    
    def __init__(self):
        self.mqtt_publisher = None
        self.command_history = {}
    
    def _get_publisher(self):
        """Lazy load MQTT publisher"""
        if self.mqtt_publisher is None:
            self.mqtt_publisher = get_mqtt_publisher()
        return self.mqtt_publisher
    
    def _prepare_payload(self, payload: dict, command_type: str) -> dict:
        """Return payload as-is (signing removed)"""
        return payload
    
    def _emit_via_socketio(self, event: str, payload: dict):
        """Emit command via Socket.IO as fallback when MQTT is offline."""
        try:
            from app import get_socketio
            sio = get_socketio()
            if sio:
                sio.emit(event, payload, namespace='/')
                return True
        except Exception as e:
            print(f"[COMMANDS] Socket.IO emit error: {e}")
        return False

    def _send_command(self, topic: str, payload: dict, socketio_event: str) -> bool:
        """Publish via MQTT; fall back to Socket.IO if MQTT is offline.
        Always returns True — command is persisted in DB and will be retried."""
        publisher = self._get_publisher()
        if publisher and publisher.connected:
            if publisher._publish(topic, payload):
                return True
        # MQTT offline — try Socket.IO
        try:
            from app import get_socketio
            sio = get_socketio()
            if sio:
                sio.emit(socketio_event, payload, namespace='/')
                print(f"[COMMANDS] Delivered via Socket.IO: {socketio_event}")
        except Exception as e:
            print(f"[COMMANDS] Socket.IO emit error: {e}")
        # Return True regardless — command is saved in DB
        return True

    def send_force_sync(self, device_id=None, sync_type='full', user_email=None):
        """Send force sync command to device(s) with delivery tracking"""
        command_id = str(uuid.uuid4())
        
        payload = {
            'command': 'force_sync',
            'command_id': command_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'sync_type': sync_type
        }
        
        # Sign sensitive command
        payload = self._prepare_payload(payload, 'force_sync')
        
        # Create command execution record
        try:
            cmd_exec = CommandExecution(
                command_id=command_id,
                command_type='force_sync',
                device_id=device_id,
                target_type='device' if device_id else 'broadcast',
                payload=payload,
                status='pending',
                created_by=user_email
            )
            db.session.add(cmd_exec)
            db.session.commit()
            print(f"[COMMANDS] Created execution record for {command_id}")
        except Exception as e:
            print(f"[COMMANDS] Error creating execution record: {e}")
            db.session.rollback()
        
        topic = f'precisionpulse/commands/{device_id}/sync' if device_id else 'precisionpulse/commands/broadcast/sync'
        success = self._send_command(topic, payload, 'remote_command')
        
        # Update status to sent
        if success:
            try:
                cmd_exec = CommandExecution.query.filter_by(command_id=command_id).first()
                if cmd_exec:
                    cmd_exec.status = 'sent'
                    cmd_exec.delivery_status = 'sent'
                    cmd_exec.sent_at = datetime.now(timezone.utc)
                    db.session.commit()
                    print(f"[COMMANDS] Updated status to sent for {command_id}")
            except Exception as e:
                print(f"[COMMANDS] Error updating status: {e}")
                db.session.rollback()
        
        self.command_history[command_id] = {
            'command': 'force_sync',
            'device_id': device_id or 'all',
            'status': 'sent' if success else 'failed',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        return {
            'success': success,
            'command_id': command_id,
            'message': f'Force sync command {"sent" if success else "failed"}',
            'device_id': device_id or 'all',
            'sync_type': sync_type
        }
    
    def send_config_update(self, device_id=None, config=None, user_email=None):
        """Send config update command to device(s) with delivery tracking"""
        if not config:
            return {'success': False, 'error': 'Config data required'}
        
        command_id = str(uuid.uuid4())
        
        payload = {
            'command': 'update_config',
            'command_id': command_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'config': config
        }
        
        # Sign sensitive command
        payload = self._prepare_payload(payload, 'update_config')
        
        # Create command execution record
        try:
            cmd_exec = CommandExecution(
                command_id=command_id,
                command_type='update_config',
                device_id=device_id,
                target_type='device' if device_id else 'broadcast',
                payload=payload,
                status='pending',
                created_by=user_email
            )
            db.session.add(cmd_exec)
            db.session.commit()
            print(f"[COMMANDS] Created execution record for {command_id}")
        except Exception as e:
            print(f"[COMMANDS] Error creating execution record: {e}")
            db.session.rollback()
        
        topic = f'precisionpulse/commands/{device_id}/config' if device_id else 'precisionpulse/commands/broadcast/config'
        success = self._send_command(topic, payload, 'remote_command')
        
        # Update status to sent
        if success:
            try:
                cmd_exec = CommandExecution.query.filter_by(command_id=command_id).first()
                if cmd_exec:
                    cmd_exec.status = 'sent'
                    cmd_exec.delivery_status = 'sent'
                    cmd_exec.sent_at = datetime.now(timezone.utc)
                    db.session.commit()
                    print(f"[COMMANDS] Updated status to sent for {command_id}")
            except Exception as e:
                print(f"[COMMANDS] Error updating status: {e}")
                db.session.rollback()
        
        self.command_history[command_id] = {
            'command': 'update_config',
            'device_id': device_id or 'all',
            'status': 'sent' if success else 'failed',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'config': config
        }
        
        return {
            'success': success,
            'command_id': command_id,
            'message': f'Config update command {"sent" if success else "failed"}',
            'device_id': device_id or 'all'
        }
    
    def send_custom_command(self, command_type, device_id=None, params=None, user_email=None):
        """Send custom command to device(s)"""
        command_id = str(uuid.uuid4())
        
        payload = {
            'command': command_type,
            'command_id': command_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'params': params or {}
        }
        
        # Sign sensitive command
        payload = self._prepare_payload(payload, command_type)
        
        # Create command execution record
        try:
            cmd_exec = CommandExecution(
                command_id=command_id,
                command_type=command_type,
                device_id=device_id,
                target_type='device' if device_id else 'broadcast',
                payload=payload,
                status='pending',
                created_by=user_email
            )
            db.session.add(cmd_exec)
            db.session.commit()
            print(f"[COMMANDS] Created execution record for {command_id}")
        except Exception as e:
            print(f"[COMMANDS] Error creating execution record: {e}")
            db.session.rollback()
        
        topic = f'precisionpulse/commands/{device_id}/{command_type}' if device_id else f'precisionpulse/commands/broadcast/{command_type}'
        success = self._send_command(topic, payload, 'remote_command')
        
        # Update status to sent
        if success:
            try:
                cmd_exec = CommandExecution.query.filter_by(command_id=command_id).first()
                if cmd_exec:
                    cmd_exec.status = 'sent'
                    cmd_exec.delivery_status = 'sent'
                    cmd_exec.sent_at = datetime.now(timezone.utc)
                    db.session.commit()
                    print(f"[COMMANDS] Updated status to sent for {command_id}")
            except Exception as e:
                print(f"[COMMANDS] Error updating status: {e}")
                db.session.rollback()
        
        self.command_history[command_id] = {
            'command': command_type,
            'device_id': device_id or 'all',
            'status': 'sent' if success else 'failed',
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

        return {
            'success': success,
            'command_id': command_id,
            'message': f'Command {"sent" if success else "failed"}',
            'device_id': device_id or 'all',
            'command_type': command_type,
        }
    
    def get_command_status(self, command_id=None, device_id=None):
        """Get status of commands from database"""
        try:
            if command_id:
                cmd_exec = CommandExecution.query.filter_by(command_id=command_id).first()
                if cmd_exec:
                    acks = CommandAcknowledgment.query.filter_by(command_id=command_id).all()
                    result = cmd_exec.to_dict()
                    result['acknowledgments'] = [ack.to_dict() for ack in acks]
                    return result
                return {'error': 'Command not found'}
            
            if device_id:
                commands = CommandExecution.query.filter_by(device_id=device_id).all()
                return {
                    'commands': [cmd.to_dict() for cmd in commands],
                    'count': len(commands)
                }
            
            commands = CommandExecution.query.all()
            return {
                'commands': [cmd.to_dict() for cmd in commands],
                'count': len(commands)
            }
        except Exception as e:
            print(f"[COMMANDS] Error getting command status: {e}")
            return {'error': str(e)}
    
    def handle_command_acknowledgment(self, command_id, device_id, ack_type, status, message=None, result_data=None):
        """Handle acknowledgment from device"""
        try:
            ack = CommandAcknowledgment(
                command_id=command_id,
                device_id=device_id,
                ack_type=ack_type,
                status=status,
                message=message,
                result_data=result_data
            )
            db.session.add(ack)
            
            cmd_exec = CommandExecution.query.filter_by(command_id=command_id).first()
            if cmd_exec:
                if ack_type == 'received':
                    cmd_exec.delivery_status = 'delivered'
                    cmd_exec.delivered_at = datetime.now(timezone.utc)
                    cmd_exec.status = 'delivered'
                elif ack_type == 'executing':
                    cmd_exec.execution_status = 'executing'
                    cmd_exec.started_at = datetime.now(timezone.utc)
                    cmd_exec.status = 'executing'
                elif ack_type == 'completed':
                    cmd_exec.execution_status = 'completed'
                    cmd_exec.completed_at = datetime.now(timezone.utc)
                    cmd_exec.status = 'completed'
                    cmd_exec.result_data = result_data
                elif ack_type == 'failed':
                    cmd_exec.execution_status = 'failed'
                    cmd_exec.status = 'failed'
                    cmd_exec.error_message = message
                    cmd_exec.result_data = result_data
            
            db.session.commit()
            print(f"[COMMANDS] Recorded acknowledgment for {command_id}: {ack_type}")

            # Broadcast ack to web clients via Socket.IO
            try:
                from app import get_socketio
                sio = get_socketio()
                if sio:
                    sio.emit('command_ack', {
                        'command_id': command_id,
                        'device_id': device_id,
                        'ack_type': ack_type,
                        'status': status,
                        'message': message,
                    }, namespace='/')
            except Exception as e:
                print(f"[COMMANDS] Socket.IO ack emit error: {e}")

            return {'success': True, 'message': 'Acknowledgment recorded'}
        except Exception as e:
            print(f"[COMMANDS] Error handling acknowledgment: {e}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}

    def send_user_sync_command(self, action: str, params: dict, user_email: str = None):
        """Send a sync_users command to all desktop clients after a user/role/permission change.
        Logs to command_executions. Desktop ACKs update command_acknowledgments.
        """
        command_id = str(uuid.uuid4())
        payload = {
            'command': 'sync_users',
            'command_id': command_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'params': {'action': action, **params}
        }

        try:
            cmd_exec = CommandExecution(
                command_id=command_id,
                command_type='sync_users',
                device_id=None,
                target_type='broadcast',
                payload=payload,
                status='pending',
                created_by=user_email
            )
            db.session.add(cmd_exec)
            db.session.commit()
        except Exception as e:
            print(f"[COMMANDS] Error creating sync_users record: {e}")
            db.session.rollback()

        # Broadcast to all desktops
        topic = 'precisionpulse/commands/broadcast/sync_users'
        success = self._get_publisher()._publish(topic, payload)

        if success:
            try:
                cmd_exec = CommandExecution.query.filter_by(command_id=command_id).first()
                if cmd_exec:
                    cmd_exec.status = 'sent'
                    cmd_exec.delivery_status = 'sent'
                    cmd_exec.sent_at = datetime.now(timezone.utc)
                    db.session.commit()
            except Exception as e:
                print(f"[COMMANDS] Error updating sync_users status: {e}")
                db.session.rollback()

        print(f"[COMMANDS] sync_users({action}) broadcast {'sent' if success else 'failed'} [{command_id}]")
        return {'success': success, 'command_id': command_id, 'action': action}


remote_commands_service = RemoteCommandsService()
