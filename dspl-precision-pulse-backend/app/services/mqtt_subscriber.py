"""
MQTT Subscriber for backend to receive telemetry and sync messages
"""

import paho.mqtt.client as mqtt
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class MQTTSubscriber:
    """MQTT subscriber for backend"""
    
    def __init__(self, broker='localhost', port=1883, use_tls=False, ca_certs=None, app=None):
        self.broker = broker
        self.port = port
        self.use_tls = use_tls
        self.ca_certs = ca_certs
        self.app = app
        try:
            # clean_session=True ensures the broker discards old subscriptions on
            # every reconnect, preventing duplicate message delivery.
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, clean_session=True)
        except AttributeError:
            self.client = mqtt.Client(clean_session=True)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.connected = False
        self.socketio = None
    
    def set_socketio(self, socketio):
        """Set Socket.IO instance for broadcasting status"""
        self.socketio = socketio
    
    def set_app(self, app):
        """Set Flask app for database operations"""
        self.app = app
    
    def connect(self):
        """Connect to MQTT broker with automatic reconnect loop."""
        if self.use_tls:
            import ssl
            self.client.tls_set(
                ca_certs=self.ca_certs,
                certfile=None,
                keyfile=None,
                cert_reqs=ssl.CERT_NONE,
                tls_version=ssl.PROTOCOL_TLSv1_2
            )
            self.client.tls_insecure_set(True)

        # Let paho handle reconnects automatically
        self.client.reconnect_delay_set(min_delay=2, max_delay=30)

        import time
        while True:
            try:
                logger.info(f"Connecting to MQTT broker at {self.broker}:{self.port} (TLS: {self.use_tls})")
                self.client.connect(self.broker, self.port, 60)
                self.client.loop_forever(retry_first_connection=True)
            except Exception as e:
                logger.error(f"MQTT connection error: {e} — retrying in 5s")
            # loop_forever returned (broker went away) — wait then reconnect
            time.sleep(5)
    
    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Handle connection"""
        if rc == 0:
            self.connected = True
            logger.info("MQTT subscriber connected")
            # Subscribe all topics in one call — atomic and avoids duplicate
            # subscriptions if _on_connect fires more than once.
            client.subscribe([
                ("precisionpulse/+/telemetry",        1),
                ("precisionpulse/+/parameter/edit",   1),
                ("precisionpulse/presence/#",          1),
                ("telemetry/stream",                   1),
                ("precisionpulse/sync/#",              1),
                ("precisionpulse/config/update",       1),
                ("precisionpulse/config/bulk-update",  1),
                ("precisionpulse/commands/ack/#",      1),
                ("precisionpulse/commands/broadcast/#",1),
                ("precisionpulse/+/heartbeat",         1),
            ])
            if self.socketio:
                try:
                    self.socketio.emit('mqtt_status',    {'status': 'online', 'connected': True},  namespace='/')
                    self.socketio.emit('mqtt_connected', {'status': 'online', 'connected': True},  namespace='/')
                    logger.info("Emitted MQTT online status")
                except Exception as e:
                    logger.error(f"Error emitting status: {e}")
            # Emit sync_status so frontend can show buffered-data count
            if self.socketio and self.app:
                try:
                    with self.app.app_context():
                        from app.models.parameter_stream import ParameterStream
                        from app.models import db
                        total   = db.session.query(ParameterStream).count()
                        synced  = db.session.query(ParameterStream).filter(
                            ParameterStream.synced == True).count()
                        self.socketio.emit('sync_status', {
                            'status':   'reconnected',
                            'total':    total,
                            'synced':   synced,
                            'unsynced': total - synced,
                        }, namespace='/')
                        logger.info(f"[SYNC] Emitted sync_status: total={total} synced={synced}")
                except Exception as e:
                    logger.error(f"[SYNC] Error emitting sync_status: {e}")
        else:
            self.connected = False
            logger.error(f"MQTT connection failed: {rc}")
            if self.socketio:
                try:
                    self.socketio.emit('mqtt_status',       {'status': 'offline', 'connected': False}, namespace='/')
                    self.socketio.emit('mqtt_disconnected', {'status': 'offline', 'connected': False}, namespace='/')
                except Exception as e:
                    logger.error(f"Error emitting status: {e}")
    
    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        """Handle disconnection"""
        self.connected = False
        logger.warning(f"MQTT subscriber disconnected (rc={rc})")
        if self.socketio:
            try:
                self.socketio.emit('mqtt_status',       {'status': 'offline', 'connected': False}, namespace='/')
                self.socketio.emit('mqtt_disconnected', {'status': 'offline', 'connected': False}, namespace='/')
                self.socketio.emit('sync_status',       {'status': 'disconnected'}, namespace='/')
                logger.info("Emitted MQTT offline + sync_status:disconnected")
            except Exception as e:
                logger.error(f"Error emitting disconnect status: {e}")
        else:
            logger.warning("SocketIO not set, cannot emit status")
    
    def _on_message(self, client, userdata, msg):
        """Handle incoming messages"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            logger.info(f"MQTT message received on {topic}")

            if "heartbeat" in topic:
                self._handle_heartbeat(topic, payload)
            elif "presence" in topic:
                self._handle_presence(payload)
            elif "parameter/edit" in topic:
                self._handle_parameter_edit(topic, payload)
            elif "telemetry" in topic:
                self._handle_telemetry(payload)
            elif "commands/ack" in topic:
                self._handle_command_ack(payload)
            elif "sync" in topic:
                self._handle_sync(payload)
            elif "config" in topic:
                self._handle_config(payload)
        except Exception as e:
            logger.error(f"Message handling error: {e}")

    def _handle_parameter_edit(self, topic: str, payload: dict):
        """Handle admin parameter edit published by desktop via MQTT.
        Writes to PostgreSQL and emits parameter_value_updated to frontend.
        """
        try:
            param_id = payload.get('parameter_id')
            value    = payload.get('value')
            ts_str   = payload.get('timestamp')
            if param_id is None or value is None:
                return
            if not self.app:
                return
            with self.app.app_context():
                from app.models.parameter_stream import ParameterStream
                from app.models import db
                from datetime import datetime, timezone
                try:
                    ts = datetime.fromisoformat(ts_str) if ts_str else datetime.now(timezone.utc)
                    if ts.tzinfo is not None:
                        ts = ts.replace(tzinfo=None)
                except Exception:
                    ts = datetime.utcnow()
                record = ParameterStream(
                    parameter_id=int(param_id),
                    value=float(value),
                    timestamp=ts,
                    synced=True
                )
                db.session.add(record)
                db.session.commit()
                logger.info("[PARAM_EDIT] Saved param %s = %s from desktop", param_id, value)
                if self.socketio:
                    self.socketio.emit(
                        'parameter_value_updated',
                        {'parameter_id': param_id, 'value': float(value),
                         'timestamp': ts.isoformat(), 'source': 'admin'},
                        namespace='/'
                    )
        except Exception as e:
            logger.error("[PARAM_EDIT] Error: %s", e)

    def _handle_presence(self, payload: dict):
        """Broadcast user online/offline status to frontend via Socket.IO."""
        email  = payload.get('email')
        status = payload.get('status', 'online')
        if not email:
            return
        if self.socketio:
            self.socketio.emit('user_presence',
                               {'email': email, 'status': status},
                               namespace='/')
            logger.info('[PRESENCE] %s is %s', email, status)

    def _handle_heartbeat(self, topic: str, payload: dict):
        """Track heartbeat and detect device timeout via DataFreshnessMonitor."""
        device_id = payload.get('client_id') or topic.split('/')[1]
        logger.info(f"[HEARTBEAT] Received from {device_id}")
        if self.app and hasattr(self.app, 'data_freshness_monitor'):
            self.app.data_freshness_monitor.record_data(device_id)
    
    def _handle_telemetry(self, payload):
        """Receive telemetry from desktop via MQTT, save to PostgreSQL, emit to frontend."""
        try:
            client_id  = payload.get('client_id')
            timestamp_str = payload.get('timestamp')
            parameters = payload.get('parameters', [])

            if not parameters:
                if not self.socketio:
                    logger.warning("[TELEMETRY] No Flask app context or socketio — cannot process telemetry")
                return

            logger.info("MQTT telemetry from %s: %d params", client_id, len(parameters))

            try:
                from datetime import datetime, timezone
                ts = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now(timezone.utc)
                if ts.tzinfo is not None:
                    ts = ts.replace(tzinfo=None)
            except Exception:
                from datetime import datetime
                ts = datetime.utcnow()

            if not self.app:
                logger.warning("[TELEMETRY] No Flask app context")
                return

            with self.app.app_context():
                from app.models.parameter_stream import ParameterStream
                from app.models import db
                from app.models.parameter import Parameter

                saved = []
                for p in parameters:
                    param_id = p.get('parameter_id') or p.get('id')
                    value    = p.get('value')
                    if param_id is None or value is None:
                        continue
                    try:
                        int_param_id = int(param_id)
                    except (ValueError, TypeError):
                        logger.debug("[TELEMETRY] Skipping DB write for non-integer param_id=%s", param_id)
                        saved.append(p)
                        continue
                    try:
                                # Dedup guard: skip if a row for this parameter already exists
                        # within a 3-second window of the incoming timestamp.
                        # 3s matches the desktop send interval so we never swallow
                        # a real next tick, but always catch same-tick duplicates
                        # from concurrent MQTT + HTTP paths.
                        from datetime import timedelta
                        window_start = ts - timedelta(seconds=3)
                        window_end   = ts + timedelta(seconds=3)
                        exists = db.session.query(ParameterStream.id).filter(
                            ParameterStream.parameter_id == int_param_id,
                            ParameterStream.timestamp    >= window_start,
                            ParameterStream.timestamp    <= window_end,
                        ).first()
                        if exists:
                            logger.debug(
                                "[TELEMETRY] Skipping duplicate param_id=%s ts=%s",
                                param_id, ts
                            )
                            continue
                        record = ParameterStream(
                            parameter_id=int_param_id,
                            value=float(value),
                            timestamp=ts,
                            synced=True
                        )
                        db.session.add(record)
                        saved.append(p)
                    except Exception as rec_err:
                        logger.warning("[TELEMETRY] Skipping param %s: %s", param_id, rec_err)
                        db.session.rollback()

                if saved:
                    db.session.commit()

                    try:
                        from app.services.alert_service import check_range_alert
                        for p in saved:
                            param_id = p.get('parameter_id') or p.get('id')
                            value    = p.get('value')
                            if param_id is None or value is None:
                                continue
                            try:
                                param_obj = Parameter.query.get(int(param_id))
                            except Exception:
                                continue
                            # Skip alert check for disabled parameters
                            if param_obj and param_obj.enabled:
                                check_range_alert(
                                    parameter_id=int(param_id),
                                    parameter_name=param_obj.name,
                                    current_value=float(value),
                                    alert_min=param_obj.alert_min,
                                    alert_max=param_obj.alert_max,
                                    warn_min=param_obj.warn_min,
                                    warn_max=param_obj.warn_max,
                                )
                    except Exception as alert_err:
                        logger.warning("[TELEMETRY] Alert check error: %s", alert_err)

                    # Emit to frontend via Socket.IO
                    if self.socketio:
                        normalized = [
                            {
                                'parameter_id': p.get('parameter_id') or p.get('id'),
                                'id':           p.get('parameter_id') or p.get('id'),
                                'name':         p.get('name', ''),
                                'value':        float(p.get('value', 0)),
                                'unit':         p.get('unit', ''),
                            }
                            for p in saved
                        ]
                        self.socketio.emit(
                            'telemetry',
                            {
                                'client_id':  client_id,
                                'timestamp':  ts.isoformat(),
                                'data': {'parameters': normalized}
                            },
                            namespace='/'
                        )
                        self.socketio.emit(
                            'parameter_stream_update',
                            {
                                'client_id':  client_id,
                                'timestamp':  ts.isoformat(),
                                'data': {'parameters': normalized}
                            },
                            namespace='/'
                        )
                        logger.info("[TELEMETRY] Emitted %d params to frontend", len(saved))

                    # Record data freshness
                    if self.app and hasattr(self.app, 'data_freshness_monitor'):
                        self.app.data_freshness_monitor.record_data(client_id)

        except Exception as e:
            logger.error("[TELEMETRY] Error handling telemetry: %s", e, exc_info=True)
    
    def _handle_command_ack(self, payload):
        """Handle command acknowledgment from desktop — updates command_executions and command_acknowledgments."""
        try:
            command_id = payload.get('command_id')
            device_id  = payload.get('device_id')
            ack_type   = payload.get('ack_type')
            status     = payload.get('status')
            message    = payload.get('message')
            result_data = payload.get('result_data')

            if not all([command_id, device_id, ack_type, status]):
                logger.warning(f"[ACK] Incomplete ack payload: {payload}")
                return

            if not self.app:
                logger.warning("[ACK] No Flask app context — cannot write to DB")
                return

            with self.app.app_context():
                from app.services.remote_commands_service import remote_commands_service
                remote_commands_service.handle_command_acknowledgment(
                    command_id=command_id,
                    device_id=device_id,
                    ack_type=ack_type,
                    status=status,
                    message=message,
                    result_data=result_data
                )
                logger.info(f"[ACK] Recorded {ack_type}/{status} for command {command_id} from {device_id}")

                # Broadcast updated status to frontend via Socket.IO
                if self.socketio:
                    self.socketio.emit('command_ack', {
                        'command_id': command_id,
                        'device_id': device_id,
                        'ack_type': ack_type,
                        'status': status,
                        'message': message,
                    }, namespace='/')
        except Exception as e:
            logger.error(f"[ACK] Error handling command ack: {e}")
            import traceback
            traceback.print_exc()

    def _handle_sync(self, payload):
        """Handle sync messages — user CRUD from desktop goes to PostgreSQL then Socket.IO."""
        try:
            msg_type = payload.get('type')
            # Decrypt if needed
            if '_enc' in payload:
                try:
                    from app.utils.encryption import decrypt_payload
                    payload = decrypt_payload(payload['_enc'])
                    msg_type = payload.get('type')
                except Exception as dec_err:
                    logger.error('[SYNC] Decryption failed: %s', dec_err)
                    return

            if not self.app:
                return

            if msg_type == 'auth_request':
                self._handle_auth_request(payload)

            elif msg_type in ('user_created', 'user_updated'):
                user_data = payload.get('user', {})
                email = user_data.get('email')
                if not email:
                    return
                with self.app.app_context():
                    from app.models.user import User
                    from app.models import db
                    user = User.query.filter_by(email=email).first()
                    if user:
                        user.name = user_data.get('name', user.name)
                        user.role = user_data.get('role', user.role)
                        user.is_active = user_data.get('is_active', user.is_active)
                        event = 'user_updated'
                    else:
                        import bcrypt as _bcrypt, secrets
                        user = User(
                            email=email,
                            name=user_data.get('name', email.split('@')[0]),
                            role=user_data.get('role', 'user'),
                            is_active=user_data.get('is_active', True)
                        )
                        ph = user_data.get('password_hash')
                        user.password_hash = ph if ph else _bcrypt.hashpw(
                            secrets.token_bytes(32), _bcrypt.gensalt()).decode('utf-8')
                        db.session.add(user)
                        event = 'user_created'
                    db.session.commit()
                    logger.info('[SYNC] %s: %s', event, email)
                    if self.socketio:
                        self.socketio.emit(event, {'user': {
                            'id': user.id, 'email': user.email,
                            'name': user.name, 'role': user.role,
                            'is_active': user.is_active
                        }}, namespace='/')

            elif msg_type == 'user_deleted':
                user_data = payload.get('user', {})
                email = user_data.get('email')
                if not email:
                    return
                with self.app.app_context():
                    from app.models.user import User
                    from app.models import db
                    user = User.query.filter_by(email=email).first()
                    if user:
                        user_id = user.id
                        db.session.delete(user)
                        db.session.commit()
                        logger.info('[SYNC] user_deleted: %s', email)
                        if self.socketio:
                            self.socketio.emit('user_deleted',
                                               {'user_id': user_id, 'email': email},
                                               namespace='/')

            elif msg_type == 'role_changed':
                email    = payload.get('email')
                new_role = payload.get('new_role')
                if not email or not new_role:
                    return
                with self.app.app_context():
                    from app.models.user import User
                    from app.models import db
                    user = User.query.filter_by(email=email).first()
                    if user:
                        old_role = user.role
                        user.role = new_role
                        db.session.commit()
                        logger.info('[SYNC] role_changed: %s %s->%s', email, old_role, new_role)
                        if self.socketio:
                            self.socketio.emit('user_updated', {'user': {
                                'id': user.id, 'email': user.email,
                                'name': user.name, 'role': user.role,
                                'is_active': user.is_active
                            }}, namespace='/')
            elif msg_type == 'user_password_changed':
                self._handle_password_change(payload)

            elif msg_type in ('parameter_created', 'parameter_updated', 'parameter_deleted'):
                self._handle_parameter_sync(payload)

            else:
                logger.info('[SYNC] Unhandled sync type: %s', msg_type)
        except Exception as e:
            logger.error('[SYNC] Error handling sync: %s', e)
    
    def _handle_auth_request(self, payload: dict):
        """Verify desktop login credentials against PostgreSQL and respond via MQTT."""
        request_id = payload.get('request_id')
        email      = payload.get('email')
        password   = payload.get('password')
        if not all([request_id, email, password]):
            return
        try:
            with self.app.app_context():
                from app.models.user import User
                from app.utils.encryption import encrypt_payload
                import json
                user = User.query.filter_by(email=email, is_active=True).first()
                if user and user.check_password(password):
                    resp = {
                        'type': 'auth_response',
                        'request_id': request_id,
                        'success': True,
                        'user': {
                            'id': user.id, 'email': user.email,
                            'name': user.name, 'role': user.role,
                            'is_active': user.is_active,
                        }
                    }
                    logger.info('[SYNC] auth_request success for %s', email)
                else:
                    resp = {'type': 'auth_response', 'request_id': request_id, 'success': False}
                    logger.warning('[SYNC] auth_request failed for %s', email)
                try:
                    encrypted = {'_enc': encrypt_payload(resp), 'type': 'auth_response'}
                except Exception:
                    encrypted = resp
                self.client.publish(
                    'precisionpulse/sync/users/auth-response',
                    json.dumps(encrypted), qos=1
                )
        except Exception as e:
            logger.error('[SYNC] _handle_auth_request error: %s', e)

    def _handle_password_change(self, payload: dict):
        """Verify current password then update hash in PostgreSQL."""
        email            = payload.get('email')
        password_hash    = payload.get('password_hash')
        current_password = payload.get('current_password')
        if not all([email, password_hash, current_password]):
            return
        try:
            with self.app.app_context():
                from app.models.user import User
                from app.models import db
                user = User.query.filter_by(email=email).first()
                if not user:
                    logger.warning('[SYNC] password_change: user not found %s', email)
                    return
                if not user.check_password(current_password):
                    logger.warning('[SYNC] password_change: wrong current password for %s', email)
                    return
                user.password_hash = password_hash
                db.session.commit()
                logger.info('[SYNC] password updated for %s', email)
                if self.socketio:
                    self.socketio.emit('user_updated', {'user': {
                        'id': user.id, 'email': user.email,
                        'name': user.name, 'role': user.role,
                    }}, namespace='/')
        except Exception as e:
            logger.error('[SYNC] _handle_password_change error: %s', e)

    def _handle_parameter_sync(self, payload: dict):
        """Create / update / delete a parameter in PostgreSQL from desktop MQTT message."""
        msg_type = payload.get('type')
        param_data = payload.get('parameter', {})
        if not param_data:
            return
        try:
            with self.app.app_context():
                from app.models.parameter import Parameter
                from app.models import db
                if msg_type == 'parameter_created':
                    p = Parameter(
                        name=param_data['name'],
                        unit=param_data.get('unit', ''),
                        description=param_data.get('description', ''),
                        enabled=param_data.get('enabled', True),
                    )
                    db.session.add(p)
                    db.session.commit()
                    logger.info('[SYNC] parameter_created: %s', p.name)
                    if self.socketio:
                        self.socketio.emit('parameter_created', {'parameter': p.to_dict()}, namespace='/')

                elif msg_type == 'parameter_updated':
                    p = Parameter.query.get(param_data.get('id'))
                    if p:
                        for k, v in param_data.items():
                            if k != 'id' and hasattr(p, k):
                                setattr(p, k, v)
                        db.session.commit()
                        logger.info('[SYNC] parameter_updated: id=%s', param_data.get('id'))
                        if self.socketio:
                            self.socketio.emit('parameter_updated', {'parameter': p.to_dict()}, namespace='/')

                elif msg_type == 'parameter_deleted':
                    p = Parameter.query.get(param_data.get('id'))
                    if p:
                        db.session.delete(p)
                        db.session.commit()
                        logger.info('[SYNC] parameter_deleted: id=%s', param_data.get('id'))
                        if self.socketio:
                            self.socketio.emit('parameter_deleted',
                                               {'parameter_id': param_data.get('id')}, namespace='/')
        except Exception as e:
            logger.error('[SYNC] _handle_parameter_sync error: %s', e)

    def _handle_config(self, payload):
        """Handle configuration update messages"""
        try:
            action = payload.get('action')
            logger.info(f"Config update received: {action}")
        except Exception as e:
            logger.error(f"Error handling config: {e}")
