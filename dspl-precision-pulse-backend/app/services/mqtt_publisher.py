"""
Enhanced MQTT Publisher for user, role, and permission changes with verification and retry logic
"""

import json
import hmac
import hashlib
import os
import paho.mqtt.client as mqtt
from datetime import datetime
import time
import uuid
from app.services.config_manager import get_config_manager
from app.services.sync_verification_service import get_sync_verification_service
from config.config import Config
import logging

logger = logging.getLogger(__name__)

_LOG_EMIT_ERROR = "[MQTT_PUB] Error emitting status: %s"

class MQTTPublisher:
    """Publish user, role, and permission changes to MQTT topics with verification"""
    
    def __init__(self):
        self.client = None
        self.connected = False
        self.socketio = None
        self.sync_verifier = get_sync_verification_service()
        # Broker settings — overridden by init_mqtt_publisher() from env/config
        self._broker = None
        self._port = None
        self._use_tls = None
        self._ca_certs = None
    
    def initialize(self):
        """Initialize MQTT connection with a short delay so Mosquitto is ready."""
        if self.client is None:
            import threading
            threading.Thread(
                target=self._connect_with_retry, daemon=True
            ).start()

    def _connect_with_retry(self):
        """Retry connecting until the broker accepts the connection."""
        import time
        for attempt in range(10):
            self._connect()
            # Give paho's loop time to fire _on_connect
            time.sleep(3)
            if self.connected:
                logger.info("[MQTT_PUB] Connected on attempt %d", attempt + 1)
                return
            logger.warning("[MQTT_PUB] Not connected after attempt %d — retrying", attempt + 1)
            # Tear down the failed client so _connect() creates a fresh one
            if self.client:
                try:
                    self.client.loop_stop()
                    self.client.disconnect()
                except Exception:
                    pass
                self.client = None
        logger.error("[MQTT_PUB] All retry attempts exhausted")
    
    def set_socketio(self, socketio):
        """Set Socket.IO instance for broadcasting status"""
        self.socketio = socketio
    
    def _connect(self):
        """Connect to MQTT broker."""
        try:
            broker   = self._broker   or os.environ.get('MQTT_BROKER',   Config.MQTT_BROKER)
            port     = self._port     or int(os.environ.get('MQTT_PORT',  Config.MQTT_PORT))
            use_tls  = self._use_tls  if self._use_tls is not None else Config.MQTT_USE_TLS
            ca_certs = self._ca_certs or Config.MQTT_CA_CERTS
            keepalive = 60
            
            try:
                # Try new API (paho-mqtt 2.0+)
                self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            except AttributeError:
                # Fall back to old API (paho-mqtt 1.x)
                self.client = mqtt.Client()
            
            if use_tls:
                import ssl
                self.client.tls_set(
                    ca_certs=ca_certs,
                    cert_reqs=ssl.CERT_NONE
                )
                self.client.tls_insecure_set(True)
            
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_publish = self._on_publish
            
            self.client.connect(broker, port, keepalive)
            self.client.loop_start()
            logger.info(f"[MQTT_PUB] Connecting to {broker}:{port} (keepalive={keepalive}s)")
        except Exception as e:
            logger.error(f"[MQTT_PUB] Connection error: {e}")
    
    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback on connect"""
        if rc == 0:
            self.connected = True
            logger.info("[MQTT_PUB] Connected to broker")
            if self.socketio:
                try:
                    logger.info("[MQTT_PUB] Emitting online status to all clients")
                    self.socketio.emit('mqtt_status', {'status': 'online'}, namespace='/')
                    self.socketio.emit('mqtt_connected', {'timestamp': datetime.now().isoformat()}, namespace='/')
                    logger.info("[MQTT_PUB] Emitted online status successfully")
                    self._auto_flush_buffer()
                except Exception as e:
                    logger.error(_LOG_EMIT_ERROR, e)
            else:
                logger.warning("[MQTT_PUB] SocketIO not set, cannot emit status")
        else:
            self.connected = False
            logger.error("[MQTT_PUB] Connection failed (rc=%s)", rc)
            if self.socketio:
                try:
                    self.socketio.emit('mqtt_status', {'status': 'offline'}, namespace='/')
                    self.socketio.emit('mqtt_disconnected', {'reason': f'Connection failed (rc={rc})', 'error': f'rc={rc}'}, namespace='/')
                except Exception as e:
                    logger.error(_LOG_EMIT_ERROR, e)
    
    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        """Callback on disconnect"""
        self.connected = False
        logger.warning("[MQTT_PUB] Disconnected (rc=%s)", rc)
        if self.socketio:
            try:
                logger.info("[MQTT_PUB] Emitting offline status to all clients")
                self.socketio.emit('mqtt_status', {'status': 'offline'}, namespace='/')
                self.socketio.emit('mqtt_disconnected', {'reason': f'Disconnected (rc={rc})', 'error': f'rc={rc}'}, namespace='/')
                logger.info("[MQTT_PUB] Emitted offline status successfully")
            except Exception as e:
                logger.error(_LOG_EMIT_ERROR, e)
    
    def _on_publish(self, client, userdata, mid):
        """Callback on publish"""
        logger.debug(f"[MQTT_PUB] Message {mid} published")
    
    def publish_user_created(self, user_data: dict):
        """Publish user creation event with encrypted credential payload"""
        msg_id = str(uuid.uuid4())
        payload = {
            'type': 'user_created',
            'msg_id': msg_id,
            'timestamp': datetime.now().isoformat(),
            'user': {
                'id': user_data.get('id'),
                'email': user_data.get('email'),
                'name': user_data.get('name'),
                'role': user_data.get('role'),
                'is_active': user_data.get('is_active', True),
                'password_hash': user_data.get('password_hash', '')
            }
        }
        # Encrypt sensitive credential data
        try:
            from app.utils.encryption import encrypt_payload
            encrypted = {'_enc': encrypt_payload(payload), 'type': 'user_created', 'msg_id': msg_id}
            return self._publish_with_verification('precisionpulse/sync/users/created', encrypted, msg_id)
        except Exception:
            return self._publish_with_verification('precisionpulse/sync/users/created', payload, msg_id)

    def publish_user_updated(self, user_data: dict):
        """Publish user update event with encrypted credential payload"""
        msg_id = str(uuid.uuid4())
        payload = {
            'type': 'user_updated',
            'msg_id': msg_id,
            'timestamp': datetime.now().isoformat(),
            'user': {
                'id': user_data.get('id'),
                'email': user_data.get('email'),
                'name': user_data.get('name'),
                'role': user_data.get('role'),
                'is_active': user_data.get('is_active', True),
                'password_hash': user_data.get('password_hash', '')
            }
        }
        try:
            from app.utils.encryption import encrypt_payload
            encrypted = {'_enc': encrypt_payload(payload), 'type': 'user_updated', 'msg_id': msg_id}
            return self._publish_with_verification('precisionpulse/sync/users/updated', encrypted, msg_id)
        except Exception:
            return self._publish_with_verification('precisionpulse/sync/users/updated', payload, msg_id)
    
    def publish_user_deleted(self, user_id: int, email: str):
        """Publish user deletion event"""
        msg_id = str(uuid.uuid4())
        payload = {
            'type': 'user_deleted',
            'msg_id': msg_id,
            'timestamp': datetime.now().isoformat(),
            'user': {
                'id': user_id,
                'email': email
            }
        }
        return self._publish_with_verification('precisionpulse/sync/users/deleted', payload, msg_id)
    
    def publish_role_changed(self, user_id: int, email: str, old_role: str, new_role: str):
        """Publish role change event"""
        msg_id = str(uuid.uuid4())
        payload = {
            'type': 'role_changed',
            'msg_id': msg_id,
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'email': email,
            'old_role': old_role,
            'new_role': new_role
        }
        return self._publish_with_verification('precisionpulse/sync/roles/changed', payload, msg_id)
    
    def publish_permission_changed(self, role: str, permissions: list):
        """Publish permission change event"""
        msg_id = str(uuid.uuid4())
        payload = {
            'type': 'permission_changed',
            'msg_id': msg_id,
            'timestamp': datetime.now().isoformat(),
            'role': role,
            'permissions': permissions
        }
        return self._publish_with_verification('precisionpulse/sync/permissions/changed', payload, msg_id)
    
    def _sign_payload(self, payload: dict) -> dict:
        """Sign MQTT payload with HMAC-SHA256 for integrity verification"""
        secret = os.environ.get('MQTT_SIGNING_SECRET', 'precisionpulse-default-secret')
        payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
        signature = hmac.new(secret.encode('utf-8'), payload_bytes, hashlib.sha256).hexdigest()
        signed = dict(payload)
        signed['_sig'] = signature
        return signed

    def _publish_with_verification(self, topic: str, payload: dict, msg_id: str):
        """Publish message with verification tracking"""
        # Track message for verification
        self.sync_verifier.track_message(msg_id, topic, payload)

        # Sign payload before publishing
        payload = self._sign_payload(payload)

        # Attempt to publish
        success = self._publish(topic, payload)
        
        if success:
            self.sync_verifier.mark_delivered(msg_id)
            logger.info(f"[MQTT_PUB] Message {msg_id} published to {topic}")
        else:
            logger.warning(f"[MQTT_PUB] Message {msg_id} publish failed, will retry")
        
        return msg_id
    
    def _publish(self, topic: str, payload: dict, max_retries: int = 3):
        """Publish message to MQTT topic with exponential backoff retry."""
        if not self.connected:
            logger.warning(f"[MQTT_PUB] Not connected, cannot publish to {topic}")
            return False

        for attempt in range(max_retries):
            try:
                result = self.client.publish(topic, json.dumps(payload), qos=1)
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    logger.info(f"[MQTT_PUB] Published to {topic}")
                    return True
                logger.warning(f"[MQTT_PUB] Publish rc={result.rc} (attempt {attempt+1}/{max_retries})")
            except Exception as e:
                logger.error(f"[MQTT_PUB] Publish error (attempt {attempt+1}): {e}")

            if attempt < max_retries - 1:
                delay = 2 ** attempt
                logger.info(f"[MQTT_PUB] Retrying in {delay}s...")
                time.sleep(delay)

        logger.error(f"[MQTT_PUB] All {max_retries} publish attempts failed for {topic}")
        return False
    
    def disconnect(self):
        """Disconnect from broker"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
    
    def _auto_flush_buffer(self):
        """Auto-flush buffered data when MQTT reconnects"""
        import threading
        
        def flush_after_delay():
            time.sleep(2)
            try:
                from app.services.buffer_service import buffer_service
                count = buffer_service.flush_user_changes()
                logger.info(f"[MQTT_PUB] Auto-flushed {count} buffered user changes")
            except Exception as e:
                logger.error(f"[MQTT_PUB] Auto-flush error: {e}")
        
        flush_thread = threading.Thread(target=flush_after_delay, daemon=True)
        flush_thread.start()


# Global instance
mqtt_publisher = None

def get_mqtt_publisher():
    """Get or create MQTT publisher instance"""
    global mqtt_publisher
    if mqtt_publisher is None:
        mqtt_publisher = MQTTPublisher()
        try:
            mqtt_publisher.initialize()
        except Exception as e:
            logger.error(f"[MQTT_PUB] Failed to initialize publisher: {e}")
    return mqtt_publisher

def init_mqtt_publisher(socketio, broker=None, port=None, use_tls=None, ca_certs=None):
    """Initialize MQTT publisher with Socket.IO instance and broker settings."""
    global mqtt_publisher
    if mqtt_publisher is None:
        mqtt_publisher = MQTTPublisher()
    mqtt_publisher.set_socketio(socketio)
    # Store broker settings so _connect() uses the correct host inside Docker
    if broker:   mqtt_publisher._broker   = broker
    if port:     mqtt_publisher._port     = int(port)
    if use_tls is not None: mqtt_publisher._use_tls = use_tls
    if ca_certs: mqtt_publisher._ca_certs = ca_certs
    try:
        mqtt_publisher.initialize()
        logger.info("[MQTT_PUB] Publisher initialized with Socket.IO")
    except Exception as e:
        logger.error(f"[MQTT_PUB] Failed to initialize publisher with Socket.IO: {e}")
    return mqtt_publisher
