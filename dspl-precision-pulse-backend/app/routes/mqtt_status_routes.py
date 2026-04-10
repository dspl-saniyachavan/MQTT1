from flask import Blueprint, jsonify
from app.services.mqtt_publisher import get_mqtt_publisher
import logging

logger = logging.getLogger(__name__)
mqtt_status_bp = Blueprint('mqtt_status', __name__, url_prefix='/api/mqtt')

# Subscriber instance is stored here by the background thread so the
# status endpoint can read its .connected flag directly.
_subscriber = None

def set_subscriber(subscriber):
    """Called by the MQTT subscriber thread once connected."""
    global _subscriber
    _subscriber = subscriber


def get_subscriber():
    """Return the subscriber instance (may be None before first connect)."""
    return _subscriber


@mqtt_status_bp.route('/status', methods=['GET'])
def get_mqtt_status():
    """Get current MQTT connection status.
    Uses the subscriber's connected state as the authoritative source;
    falls back to the publisher if the subscriber is not yet available.
    """
    try:
        # Subscriber is the authoritative source — it connects reliably.
        # Publisher may fail its initial connect if Mosquitto isn't ready yet.
        connected = (_subscriber is not None and _subscriber.connected)
        if not connected:
            publisher = get_mqtt_publisher()
            connected = bool(publisher and publisher.connected)

        status = 'online' if connected else 'offline'
        logger.info("MQTT status requested: %s", status)

        from app import get_socketio
        socketio = get_socketio()
        if socketio:
            socketio.emit('mqtt_status', {'status': status, 'connected': connected}, namespace='/')

        return jsonify({'status': status, 'connected': connected}), 200
    except Exception as e:
        logger.error("Error getting MQTT status: %s", e)
        return jsonify({'status': 'offline', 'connected': False, 'error': str(e)}), 500


@mqtt_status_bp.route('/online-users', methods=['GET'])
def get_online_users():
    """Return the set of currently online user emails."""
    try:
        from app.services.online_users_service import get_online_emails
        return jsonify({'online_emails': list(get_online_emails())}), 200
    except Exception as e:
        return jsonify({'online_emails': [], 'error': str(e)}), 500
