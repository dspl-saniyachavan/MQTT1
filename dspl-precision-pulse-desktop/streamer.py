"""
Headless telemetry streamer for Docker deployment.
Generates simulated sensor data and publishes it via MQTT (TLS).
No Qt / GUI dependencies.
"""

import json
import logging
import os
import random
import signal
import sqlite3
import ssl
import sys
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [STREAMER] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
BACKEND_URL       = os.getenv("BACKEND_URL",    "http://localhost:5000")
MQTT_BROKER       = os.getenv("MQTT_BROKER",    "localhost")
MQTT_PORT         = int(os.getenv("MQTT_PORT",  "18883"))
MQTT_USE_TLS      = os.getenv("MQTT_USE_TLS",   "true").lower() == "true"
MQTT_CA_CERTS     = os.getenv("MQTT_CA_CERTS",  "config/ca.crt")
DEVICE_ID         = os.getenv("DEVICE_ID",      "desktop-001")
TELEMETRY_INTERVAL = int(os.getenv("TELEMETRY_INTERVAL", "3"))

_running = True


def _sigterm(signum, frame):
    global _running
    logger.info("Received signal %s — shutting down", signum)
    _running = False


signal.signal(signal.SIGTERM, _sigterm)
signal.signal(signal.SIGINT,  _sigterm)


# ── Parameter fetch ───────────────────────────────────────────────────────────

def _fetch_parameters() -> list[dict]:
    """Return enabled parameters from the backend, retrying until available."""
    # Use auth-free internal endpoint so no token is needed
    url = f"{BACKEND_URL}/api/internal/parameters"
    for attempt in range(60):  # up to 3 minutes
        try:
            import requests as _req
            resp = _req.get(url, timeout=5)
            if resp.ok:
                data = resp.json()
                params = data.get("parameters", data) if isinstance(data, dict) else data
                enabled = [p for p in params if p.get("enabled", True)]
                if enabled:
                    logger.info("Fetched %d enabled parameters from backend", len(enabled))
                    return enabled
        except Exception as exc:
            logger.warning("Backend not ready (attempt %d): %s", attempt + 1, exc)
        time.sleep(3)
    logger.error("Could not fetch parameters after 60 attempts — using fallback")
    return [
        {"id": 1, "name": "Temperature", "unit": "C",   "min_value": 15,  "max_value": 45},
        {"id": 2, "name": "Wind Speed",  "unit": "km/h","min_value": 0,   "max_value": 30},
        {"id": 3, "name": "Humidity",    "unit": "%",   "min_value": 30,  "max_value": 90},
        {"id": 4, "name": "Pressure",    "unit": "hPa", "min_value": 950, "max_value": 1050},
    ]


# ── Value simulation ──────────────────────────────────────────────────────────

_prev: dict[int, float] = {}

def _simulate(param: dict) -> float:
    pid  = param["id"]
    lo   = float(param.get("min_value") or 0)
    hi   = float(param.get("max_value") or 100)
    mid  = (lo + hi) / 2
    rng  = (hi - lo) * 0.05          # ±5 % drift per tick
    prev = _prev.get(pid, mid)
    val  = max(lo, min(hi, prev + random.uniform(-rng, rng)))
    _prev[pid] = val
    return round(val, 2)


# ── MQTT client ───────────────────────────────────────────────────────────────

class _Client:
    def __init__(self):
        self.connected = False
        try:
            self._c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=DEVICE_ID, clean_session=True)
        except AttributeError:
            self._c = mqtt.Client(client_id=DEVICE_ID, clean_session=True)

        if MQTT_USE_TLS:
            self._c.tls_set(ca_certs=MQTT_CA_CERTS, cert_reqs=ssl.CERT_NONE,
                            tls_version=ssl.PROTOCOL_TLSv1_2)
            self._c.tls_insecure_set(True)

        self._c.on_connect    = self._on_connect
        self._c.on_disconnect = self._on_disconnect
        self._c.reconnect_delay_set(min_delay=2, max_delay=30)

    def _on_connect(self, client, userdata, flags, rc, props=None):
        if rc == 0:
            self.connected = True
            logger.info("MQTT connected to %s:%s", MQTT_BROKER, MQTT_PORT)
        else:
            logger.error("MQTT connect failed rc=%s", rc)

    def _on_disconnect(self, client, userdata, flags, rc, props=None):
        self.connected = False
        logger.warning("MQTT disconnected rc=%s", rc)

    def connect(self):
        logger.info("Connecting to MQTT broker %s:%s (TLS=%s)", MQTT_BROKER, MQTT_PORT, MQTT_USE_TLS)
        self._c.connect_async(MQTT_BROKER, MQTT_PORT, keepalive=60)
        self._c.loop_start()

    def publish(self, topic: str, payload: dict) -> bool:
        if not self.connected:
            return False
        result = self._c.publish(topic, json.dumps(payload), qos=1)
        return result.rc == mqtt.MQTT_ERR_SUCCESS

    def disconnect(self):
        self._c.loop_stop()
        self._c.disconnect()


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    parameters = _fetch_parameters()
    client     = _Client()
    client.connect()

    # Wait for MQTT connection (up to 15 s)
    for _ in range(15):
        if client.connected:
            break
        time.sleep(1)

    _init_buffer()
    topic = f"precisionpulse/{DEVICE_ID}/telemetry"
    logger.info("Streaming to topic '%s' every %ds", topic, TELEMETRY_INTERVAL)

    while _running:
        ts = datetime.now(timezone.utc).isoformat()
        params_payload = [
            {
                "parameter_id": p["id"],
                "id":           p["id"],
                "name":         p["name"],
                "value":        _simulate(p),
                "unit":         p.get("unit", ""),
            }
            for p in parameters
        ]

        payload = {
            "client_id":  DEVICE_ID,
            "timestamp":  ts,
            "parameters": params_payload,
        }

        if client.connected:
            ok = client.publish(topic, payload)
            if ok:
                logger.info("Published %d params at %s", len(params_payload), ts)
                _flush_buffer(client, topic)
            else:
                logger.warning("Publish failed — buffering locally")
                _buffer_params(params_payload, ts)
        else:
            logger.info("MQTT offline — buffering %d params", len(params_payload))
            _buffer_params(params_payload, ts)

        time.sleep(TELEMETRY_INTERVAL)

    client.disconnect()
    logger.info("Streamer stopped")


_BUFFER_DB = os.path.join(os.path.dirname(__file__), "data", "streamer_buffer.db")


def _init_buffer():
    os.makedirs(os.path.dirname(_BUFFER_DB), exist_ok=True)
    with sqlite3.connect(_BUFFER_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS buffer (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payload TEXT NOT NULL,
                ts TEXT NOT NULL
            )
        """)


def _buffer_params(params: list[dict], ts: str):
    with sqlite3.connect(_BUFFER_DB) as conn:
        conn.execute("INSERT INTO buffer (payload, ts) VALUES (?, ?)",
                     (json.dumps(params), ts))


def _flush_buffer(client, topic: str):
    """Publish buffered records via MQTT and delete on success."""
    try:
        with sqlite3.connect(_BUFFER_DB) as conn:
            rows = conn.execute(
                "SELECT id, payload, ts FROM buffer ORDER BY id LIMIT 200"
            ).fetchall()
        if not rows:
            return
        for row_id, payload_str, ts in rows:
            params = json.loads(payload_str)
            ok = client.publish(topic, {
                "client_id": DEVICE_ID, "timestamp": ts,
                "parameters": params, "type": "buffered_sync",
            })
            if ok:
                with sqlite3.connect(_BUFFER_DB) as conn:
                    conn.execute("DELETE FROM buffer WHERE id = ?", (row_id,))
        logger.info("[BUFFER] Flushed %d buffered records via MQTT", len(rows))
    except Exception as exc:
        logger.debug("[BUFFER] Flush error: %s", exc)


if __name__ == "__main__":
    main()
