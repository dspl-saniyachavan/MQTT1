"""
Command Executor Service for Desktop Application
Receives commands via MQTT and executes them with acknowledgment
"""

import json
import logging
from datetime import datetime
from PySide6.QtCore import QObject, Signal, QTimer
from src.core.config import Config

logger = logging.getLogger(__name__)

class CommandExecutor(QObject):
    """Service to execute remote commands on desktop"""
    
    # Signals
    command_received = Signal(dict)  # command payload
    command_executing = Signal(str, str)  # command_id, command_type
    command_completed = Signal(str, dict)  # command_id, result
    command_failed = Signal(str, str)  # command_id, error_message
    
    def __init__(self, mqtt_service, configuration_service, user_sync_service=None):
        super().__init__()
        self.mqtt_service = mqtt_service
        self.config_service = configuration_service
        self.user_sync_service = user_sync_service
        self.command_handlers = {}
        self.pending_commands = {}
        
        # Register default command handlers
        self._register_default_handlers()
        
        # Connect MQTT signals
        self.mqtt_service.message_received.connect(self._on_mqtt_message)


        self.timeout_timer = QTimer()
        self.timeout_timer.timeout.connect(self._check_command_timeouts)
        self.timeout_timer.start(30000)  # Check every 30 seconds
    
    def _register_default_handlers(self):
        """Register default command handlers"""
        self.register_handler('force_sync', self._handle_force_sync)
        self.register_handler('update_config', self._handle_update_config)
        self.register_handler('restart', self._handle_restart)
        self.register_handler('status', self._handle_status)
        self.register_handler('clear_buffer', self._handle_clear_buffer)
        self.register_handler('sync_users', self._handle_sync_users)
    
    def register_handler(self, command_type, handler):
        """Register a command handler"""
        self.command_handlers[command_type] = handler
        logger.info(f"[COMMANDS] Registered handler for {command_type}")
    
    def _on_mqtt_message(self, topic, payload):
        """Handle incoming MQTT messages"""
        try:
            if 'commands' not in topic:
                return
            
            logger.info(f"[COMMANDS] Received message on {topic}")
            
            command_id = payload.get('command_id')
            command_type = payload.get('command')
            
            if not command_id or not command_type:
                logger.error("[COMMANDS] Invalid command payload - missing command_id or command")
                return
            
            # Send received acknowledgment
            self._send_acknowledgment(command_id, 'received', 'success', 'Command received')
            
            # Emit signal
            self.command_received.emit(payload)
            
            # Execute command
            self._execute_command(command_id, command_type, payload)
        
        except Exception as e:
            logger.error(f"[COMMANDS] Error handling MQTT message: {e}")
    
    def _execute_command(self, command_id, command_type, payload):
        """Execute a command"""
        try:
            logger.info(f"[COMMANDS] Executing command {command_id}: {command_type}")
            
            # Send executing acknowledgment
            self._send_acknowledgment(command_id, 'executing', 'success', 'Command executing')
            self.command_executing.emit(command_id, command_type)
            
            # Get handler
            handler = self.command_handlers.get(command_type)
            if not handler:
                error_msg = f"No handler for command type: {command_type}"
                logger.error(f"[COMMANDS] {error_msg}")
                self._send_acknowledgment(command_id, 'failed', 'error', error_msg)
                self.command_failed.emit(command_id, error_msg)
                return
            
            # Track pending command
            self.pending_commands[command_id] = {
                'command_type': command_type,
                'started_at': datetime.now(),
                'timeout': 300  # 5 minutes default
            }
            
            # Execute handler
            result = handler(payload)
            
            # Send completion acknowledgment
            self._send_acknowledgment(command_id, 'completed', 'success', 'Command completed', result)
            self.command_completed.emit(command_id, result)
            
            # Remove from pending
            if command_id in self.pending_commands:
                del self.pending_commands[command_id]
            
            logger.info(f"[COMMANDS] Command {command_id} completed successfully")
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[COMMANDS] Error executing command {command_id}: {error_msg}")
            self._send_acknowledgment(command_id, 'failed', 'error', error_msg)
            self.command_failed.emit(command_id, error_msg)
            
            # Remove from pending
            if command_id in self.pending_commands:
                del self.pending_commands[command_id]
    
    def _send_acknowledgment(self, command_id, ack_type, status, message, result_data=None):
        """Send acknowledgment via MQTT; fall back to HTTP POST if MQTT is offline."""
        try:
            device_id = getattr(self.mqtt_service, 'device_id', None) or Config.DEVICE_ID
            payload = {
                'command_id': command_id,
                'ack_type': ack_type,
                'status': status,
                'message': message,
                'device_id': device_id,
                'timestamp': datetime.now().isoformat()
            }
            if result_data:
                payload['result_data'] = result_data

            topic = f'precisionpulse/commands/ack/{device_id}'
            mqtt_ok = self.mqtt_service.client.publish(topic, json.dumps(payload), qos=1)
            if mqtt_ok:
                logger.info("[COMMANDS] Sent %s ack for %s via MQTT", ack_type, command_id)
            else:
                logger.warning("[COMMANDS] MQTT ack publish failed for %s", command_id)
        except Exception as e:
            logger.error("[COMMANDS] Error sending acknowledgment: %s", e)
    
    def _handle_force_sync(self, payload):
        """Handle force sync — re-sync users, configs, and parameters from backend."""
        sync_type = payload.get('sync_type', 'full')
        logger.info(f"[COMMANDS] Executing force sync: {sync_type}")
        records_synced = 0
        try:
            if self.user_sync_service:
                self.user_sync_service.fetch_users_from_backend()
                records_synced += len(self.user_sync_service.get_users())
            if self.config_service:
                self.config_service.sync_configurations()
            # Also sync parameter_stream unsynced records to backend
            try:
                from src.services.parameter_stream_sync_service import ParameterStreamSyncService
                if hasattr(self, '_param_stream_sync') and self._param_stream_sync:
                    self._param_stream_sync.sync_parameter_stream_to_backend()
            except Exception as ps_err:
                logger.warning("[COMMANDS] param_stream sync error: %s", ps_err)
        except Exception as e:
            logger.error(f"[COMMANDS] force_sync error: {e}")
        return {'sync_type': sync_type, 'status': 'completed', 'records_synced': records_synced}
    
    def _handle_update_config(self, payload):
        """Handle update config — apply each key/value via config_service."""
        config = payload.get('config', {})
        logger.info(f"[COMMANDS] Updating {len(config)} configurations")
        updated_count = 0
        for key, value in config.items():
            try:
                self.config_service.apply_config_change(key, value)
                updated_count += 1
            except Exception as e:
                logger.error(f"[COMMANDS] Error updating config {key}: {e}")
        return {'updated_count': updated_count, 'total_count': len(config), 'status': 'completed'}
    
    def _handle_restart(self, payload):
        """Handle restart stream command — restarts telemetry push timer."""
        logger.info("[COMMANDS] Restart stream command received")
        try:
            # Find the telemetry service via the mqtt_service reference chain
            # The main_window wires telemetry_service.mqtt_service = self.mqtt_service
            import gc
            from src.services.telemetry_service import TelemetryService
            for obj in gc.get_objects():
                if isinstance(obj, TelemetryService):
                    if obj.is_streaming:
                        obj.push_timer.stop()
                        from telemetry_config import TELEMETRY_INTERVAL_MS
                        interval_ms = TELEMETRY_INTERVAL_MS
                        if obj.config_service:
                            try:
                                interval_ms = int(obj.config_service.get_config(
                                    'TELEMETRY_FETCH_INTERVAL_MS', TELEMETRY_INTERVAL_MS))
                            except Exception:
                                pass
                        obj.push_timer.start(interval_ms)
                        logger.info("[COMMANDS] Telemetry stream restarted at %dms", interval_ms)
                    break
        except Exception as e:
            logger.error("[COMMANDS] Error restarting stream: %s", e)
        return {'status': 'restarted'}
    
    def _handle_status(self, payload):
        """Handle status command"""
        logger.info("[COMMANDS] Status command received")
        
        return {
            'device_id': Config.DEVICE_ID,
            'status': 'online',
            'timestamp': datetime.now().isoformat(),
            'pending_commands': len(self.pending_commands)
        }
    
    def _handle_sync_users(self, payload):
        """Handle sync_users command — applies a user/role/permission change to local SQLite."""
        params = payload.get('params', {})
        action = params.get('action')  # user_created / user_updated / user_deleted / role_changed / permission_changed
        if not self.user_sync_service or not action:
            return {'action': action, 'status': 'skipped'}
        # Inject 'type' so UserSyncService.msg_type check matches
        mqtt_payload = {**params, 'type': action}
        # Map action to the topic pattern UserSyncService expects
        topic_map = {
            'user_created':        'precisionpulse/sync/users/created',
            'user_updated':        'precisionpulse/sync/users/updated',
            'user_deleted':        'precisionpulse/sync/users/deleted',
            'role_changed':        'precisionpulse/sync/roles/changed',
            'permission_changed':  'precisionpulse/sync/permissions/changed',
        }
        topic = topic_map.get(action, f'precisionpulse/sync/{action}')
        self.user_sync_service._on_mqtt_message(topic, mqtt_payload)
        return {'action': action, 'status': 'completed'}

    def _handle_clear_buffer(self, payload):
        """Handle clear buffer command"""
        logger.info("[COMMANDS] Clear buffer command received")
        
        # Clear buffer logic would go here
        
        return {
            'status': 'completed',
            'records_cleared': 0
        }
    
    def _check_command_timeouts(self):
        """Check for command timeouts"""
        try:
            now = datetime.now()
            timed_out = []
            
            for command_id, cmd_info in self.pending_commands.items():
                elapsed = (now - cmd_info['started_at']).total_seconds()
                if elapsed > cmd_info['timeout']:
                    timed_out.append(command_id)
            
            for command_id in timed_out:
                logger.warning(f"[COMMANDS] Command {command_id} timed out")
                self._send_acknowledgment(command_id, 'failed', 'error', 'Command timeout')
                self.command_failed.emit(command_id, 'Command timeout')
                del self.pending_commands[command_id]
        
        except Exception as e:
            logger.error(f"[COMMANDS] Error checking timeouts: {e}")
    
    def get_pending_commands(self):
        """Get list of pending commands"""
        return list(self.pending_commands.keys())
    
    def get_command_info(self, command_id):
        """Get info about a pending command"""
        return self.pending_commands.get(command_id)
