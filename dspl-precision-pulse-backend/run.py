import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app


def _start_mosquitto():
    """Start Mosquitto MQTT broker if not already running on port 18883."""
    import socket
    import subprocess
    import logging
    logger = logging.getLogger(__name__)

    # Check if port 18883 is already in use
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        already_running = s.connect_ex(('127.0.0.1', 18883)) == 0

    if already_running:
        logger.info('[MQTT] Mosquitto already running on port 18883')
        return

    conf = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        '..', 'mosquitto-local.conf')
    conf = os.path.normpath(conf)

    if not os.path.exists(conf):
        logger.warning('[MQTT] mosquitto-local.conf not found at %s — skipping auto-start', conf)
        return

    os.makedirs('/tmp/mosquitto-data', exist_ok=True)
    subprocess.Popen(
        ['mosquitto', '-v', '-c', conf],
        stdout=open('/tmp/mosquitto.log', 'w'),
        stderr=subprocess.STDOUT,
    )
    logger.info('[MQTT] Mosquitto started on port 18883 (config: %s)', conf)


app = create_app()

if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO)
    _start_mosquitto()
    debug = os.getenv('FLASK_ENV', 'production') != 'production'
    app.socketio.run(
        app,
        debug=debug,
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5000)),
        allow_unsafe_werkzeug=True
    )
