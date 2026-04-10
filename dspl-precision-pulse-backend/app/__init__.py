from flask import Flask, request
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_migrate import Migrate
from config.config import Config
from app.models import db, migrate as _migrate_instance
from app.middleware.rate_limit_middleware import create_limiter
from app.models.user import User
from app.models.parameter import Parameter
from app.models.telemetry import Telemetry
from app.models.parameter_stream import ParameterStream
from app.models.system_config import SystemConfig
from app.models.alert_event import AlertEvent
from app.models.push_subscription import PushSubscription
# NOTE: telemetry, telemetry_buffer, roles, report_template tables are intentionally
# not imported — they are legacy/unused and will be dropped on next migration.
from app.routes.auth_routes import auth_bp
from app.routes.user_routes import user_bp
from app.routes.parameter_routes import parameter_bp
from app.routes.sync_routes import sync_bp
from app.routes.internal_routes import internal_bp
from app.routes.telemetry_routes import telemetry_bp
from app.routes.buffer_routes import buffer_bp
from app.routes.parameter_stream_routes import parameter_stream_bp
from app.routes.mqtt_bridge_routes import mqtt_bridge_bp
from app.routes.remote_commands_routes import remote_commands_bp
from app.routes.mqtt_status_routes import mqtt_status_bp
from app.routes.config_routes import config_bp
from app.routes.audit_log_routes import audit_log_bp
from app.routes.audit_routes import audit_bp
from app.routes.report_routes import report_bp
from app.routes.conflict_routes import conflict_bp
from app.routes.permission_routes import permission_bp
from app.routes.telemetry_report_routes import report_bp as telemetry_report_bp
from app.routes.alert_routes import alert_bp
from app.routes.alert_event_routes import alert_events_bp
from app.routes.push_routes import push_bp
from app.routes.security_routes import security_bp
from app.routes.history_export_routes import history_export_bp
from app.services.data_freshness_monitor import DataFreshnessMonitor
from app.services.config_manager import init_config_manager
import threading
import logging
import time

logger = logging.getLogger(__name__)

# Module-level singletons — written once by create_app(), read-only afterwards.
# Access via get_socketio() / get_limiter() to avoid direct global mutation.
_socketio: SocketIO = None  # type: ignore[assignment]
_limiter = None

# ── Blueprints registered in order ───────────────────────────────────────────
_BLUEPRINTS = [
    auth_bp, user_bp, parameter_bp, sync_bp, internal_bp,
    telemetry_bp, buffer_bp, parameter_stream_bp, mqtt_bridge_bp,
    remote_commands_bp, mqtt_status_bp, config_bp, audit_log_bp,
    audit_bp, report_bp, conflict_bp, permission_bp,
    telemetry_report_bp, alert_bp, alert_events_bp, push_bp, security_bp, history_export_bp,
]


# ── Private helpers ───────────────────────────────────────────────────────────

def _init_session(app: Flask) -> None:
    """Configure filesystem-based server-side sessions."""
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_FILE_DIR'] = 'flask_session_data'
    try:
        from flask_session import Session
        Session(app)
        logger.info("[SESSION] Filesystem session store initialized")
    except Exception as exc:
        logger.warning("[SESSION] flask_session unavailable (%s), using default cookie sessions", exc)


def _init_cors(app: Flask) -> None:
    """Apply CORS policy."""
    CORS(
        app,
        origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5000"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["Content-Type", "Authorization"],
        supports_credentials=True,
        max_age=3600,
    )



def _init_security_headers(app: Flask) -> None:
    """Add security headers to every response."""
    @app.after_request
    def _add_headers(response):
        response.headers['X-Content-Type-Options']    = 'nosniff'
        response.headers['X-Frame-Options']           = 'DENY'
        response.headers['X-XSS-Protection']          = '1; mode=block'
        response.headers['Referrer-Policy']           = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy']        = 'geolocation=(), microphone=(), camera=()'
        # Only set HSTS in production to avoid breaking local HTTP dev
        if app.config.get('ENV') == 'production' or app.config.get('FLASK_ENV') == 'production':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response


def _init_socketio(app: Flask) -> SocketIO:
    """Create and attach the Socket.IO instance."""
    sio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode="threading",
        ping_timeout=60,
        ping_interval=25,
        manage_session=False,
        path="/socket.io",
        allow_upgrades=True,
        logger=False,
        engineio_logger=False,
    )
    app.socketio = sio
    return sio

def _run_db_migrations(app: Flask) -> None:
    """Ensure config_versions table and buffer column migrations are applied."""
    from sqlalchemy import text

    with app.app_context():
        db.create_all()
        _ensure_config_versions_table()
        init_config_manager(app)
        _migrate_buffer_columns()


def _ensure_config_versions_table() -> None:
    from sqlalchemy import text
    try:
        with db.engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS config_versions (
                    id SERIAL PRIMARY KEY,
                    config_id INTEGER NOT NULL REFERENCES system_config(id) ON DELETE CASCADE,
                    version_number INTEGER NOT NULL,
                    config_data JSONB NOT NULL DEFAULT '{}',
                    changed_by VARCHAR(120),
                    change_description TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.commit()
    except Exception as exc:
        logger.warning("[INIT] config_versions table: %s", exc)


# Pre-defined safe DDL statements — column names and types are constants,
# never derived from user input, so there is no SQL injection risk.
_BUFFER_COL_MIGRATIONS = [
    ("config_change_buffer", "status",      "VARCHAR(50) DEFAULT 'pending'"),
    ("config_change_buffer", "retry_count", "INTEGER DEFAULT 0"),
    ("config_change_buffer", "synced_at",   "TIMESTAMP NULL"),
    ("user_sync_buffer",     "email",       "VARCHAR(255)"),
    ("parameters",           "alert_min",   "FLOAT NULL"),
    ("parameters",           "alert_max",   "FLOAT NULL"),
    ("parameters",           "warn_min",    "FLOAT NULL"),
    ("parameters",           "warn_max",    "FLOAT NULL"),
    ("alert_events",         "peak_value",  "FLOAT NULL"),
    ("alert_events",         "severity",    "VARCHAR(20) DEFAULT 'warning'"),
]

_DEDUP_INDEX_SQL = """
    CREATE INDEX IF NOT EXISTS idx_parameter_stream_param_ts
    ON parameter_stream (parameter_id, timestamp);
"""


def _migrate_buffer_columns() -> None:
    from sqlalchemy import text
    try:
        with db.engine.connect() as conn:
            # Drop legacy unused tables
            for tbl in ['telemetry', 'telemetry_buffer', 'roles', 'report_templates']:
                try:
                    conn.execute(text(f'DROP TABLE IF EXISTS {tbl} CASCADE'))
                    logger.info('[INIT] Dropped legacy table: %s', tbl)
                except Exception:
                    pass
            for table, col, definition in _BUFFER_COL_MIGRATIONS:
                stmt = f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {definition}"
                try:
                    conn.execute(text(stmt))
                except Exception as col_exc:  # column already exists on older Postgres
                    logger.debug("[INIT] Skipping column %s.%s: %s", table, col, col_exc)
            conn.commit()
        logger.info("[INIT] Buffer table migration complete")
    except Exception as exc:
        logger.warning("[INIT] Buffer table migration warning: %s", exc)

    # Ensure composite dedup index exists
    try:
        with db.engine.connect() as conn:
            conn.execute(text(_DEDUP_INDEX_SQL))
            conn.commit()
        logger.info("[INIT] parameter_stream dedup index ensured")
    except Exception as exc:
        logger.debug("[INIT] Dedup index: %s", exc)


def _init_default_permissions(app: Flask) -> None:
    with app.app_context():
        try:
            from app.models.permission import init_default_permissions
            init_default_permissions()
            logger.info("[PERMISSION] Default permissions initialized")
        except Exception as exc:
            logger.error("[PERMISSION] Error initializing default permissions: %s", exc)



def _register_socketio_events(sio: SocketIO) -> None:
    """Wire all Socket.IO event handlers."""

    @sio.on("connect")
    def handle_connect():
        client_id = request.sid
        logger.info("[SOCKETIO] Client connected: %s", client_id)
        sio.emit("connection_response", {"data": "Connected to server", "sid": client_id}, room=client_id)
        _send_mqtt_status_to_client(sio, client_id)

    @sio.on("disconnect")
    def handle_disconnect():
        logger.info("[SOCKETIO] Client disconnected: %s", request.sid)

    @sio.on("authenticate")
    def handle_authenticate(data):
        logger.info("[SOCKETIO] Client authenticated as user %s", data.get("user_id"))
        sio.emit("auth_response", {"status": "authenticated"})

    @sio.on("internet_status")
    def handle_internet_status(data):
        connected = data.get("connected", False)
        logger.info("[SOCKETIO] Internet status: %s", "connected" if connected else "disconnected")
        sio.emit("internet_status", data, namespace="/")

    @sio.on("mqtt_status")
    def handle_mqtt_status_from_desktop(data):
        # Status is now derived from MQTT heartbeat via DataFreshnessMonitor.
        # Forward to frontend so existing indicators still work.
        connected = data.get("connected", False)
        logger.info("[SOCKETIO] mqtt_status forwarded: %s", connected)
        sio.emit("mqtt_status", {"status": "online" if connected else "offline", "connected": connected}, namespace="/")

    @sio.on("ping")
    def handle_ping():
        logger.debug("[SOCKETIO] Ping received from %s", request.sid)
        sio.emit("pong", {"timestamp": time.time()}, room=request.sid)


def _send_mqtt_status_to_client(sio: SocketIO, client_id: str) -> None:
    try:
        from app.services.mqtt_publisher import get_mqtt_publisher
        publisher = get_mqtt_publisher()
        status = "online" if publisher and publisher.connected else "offline"
        sio.emit("mqtt_status", {"status": status}, room=client_id)
        logger.info("[SOCKETIO] Sent MQTT status '%s' to client %s", status, client_id)
    except Exception as exc:
        logger.error("[SOCKETIO] Error sending MQTT status: %s", exc)


def _start_background_threads(app: Flask, sio: SocketIO) -> None:
    """Start all daemon background threads."""
    _set_buffer_app_context(app)

    for target, name in [
        (_make_mqtt_subscriber_target(app, sio), "MQTT subscriber"),
        (_make_status_broadcast_target(app, sio), "MQTT status broadcast"),
        (_make_log_retention_target(app), "log retention"),
    ]:
        try:
            threading.Thread(target=target, daemon=True).start()
            logger.info("[THREAD] %s thread started", name)
        except Exception as exc:
            logger.error("[THREAD] Error starting %s thread: %s", name, exc)


def _set_buffer_app_context(app: Flask) -> None:
    try:
        from app.services.buffer_service import buffer_service as _buf_svc
        _buf_svc.set_app(app)
        logger.info("[BUFFER] App context set on buffer_service")
    except Exception as exc:
        logger.error("[BUFFER] Error setting app on buffer_service: %s", exc)


def _make_mqtt_subscriber_target(app: Flask, sio: SocketIO):
    def _run():
        time.sleep(2)
        try:
            from app.services.mqtt_subscriber import MQTTSubscriber
            from app.services.mqtt_publisher import init_mqtt_publisher
            from app.services.permission_sync_service import permission_sync_service
            from app.routes.mqtt_status_routes import set_subscriber

            init_mqtt_publisher(
                sio,
                broker=Config.MQTT_BROKER,
                port=Config.MQTT_PORT,
                use_tls=Config.MQTT_USE_TLS,
                ca_certs=Config.MQTT_CA_CERTS,
            )
            subscriber = MQTTSubscriber(
                broker=Config.MQTT_BROKER,
                port=Config.MQTT_PORT,
                use_tls=Config.MQTT_USE_TLS,
                ca_certs=Config.MQTT_CA_CERTS,
                app=app,
            )
            subscriber.set_socketio(sio)
            subscriber.set_app(app)
            # Register subscriber so /api/mqtt/status can read its .connected flag
            set_subscriber(subscriber)
            subscriber.connect()
            time.sleep(1)
            permission_sync_service.sync_all_permissions()
        except Exception as exc:
            logger.error("[MQTT] Error in subscriber thread: %s", exc, exc_info=True)
    return _run


def _make_status_broadcast_target(app: Flask, sio: SocketIO):
    def _run():
        time.sleep(3)
        prev_status = None
        while True:
            prev_status = _broadcast_once(app, sio, prev_status)
            time.sleep(5)
    return _run



def _broadcast_once(app: Flask, sio: SocketIO, prev_status) -> str:
    try:
        with app.app_context():
            from app.services.buffer_service import buffer_service

            # Derive online status from MQTT subscriber connection flag.
            # The subscriber sets self.connected=True on _on_connect and
            # False on _on_disconnect, so this reflects the actual broker link.
            from app.routes.mqtt_status_routes import get_subscriber
            subscriber = get_subscriber()
            is_online = bool(subscriber and subscriber.connected)
            status = "online" if is_online else "offline"

            sio.emit("mqtt_status", {"status": status, "connected": is_online}, namespace="/")
            _handle_status_transition(sio, prev_status, status)

            if is_online:
                _flush_buffers(buffer_service)

            return status
    except Exception as exc:
        logger.error("[MQTT] Error broadcasting MQTT status: %s", exc)
        return prev_status


def _handle_status_transition(sio: SocketIO, prev_status: str, status: str) -> None:
    if prev_status == "offline" and status == "online":
        _emit_reconnect_sync_status(sio)
    elif prev_status == "online" and status == "offline":
        sio.emit("sync_status", {"status": "disconnected"}, namespace="/")


def _emit_reconnect_sync_status(sio: SocketIO) -> None:
    try:
        from app.models.parameter_stream import ParameterStream
        from app.models import db
        total  = db.session.query(ParameterStream).count()
        synced = db.session.query(ParameterStream).filter(ParameterStream.synced.is_(True)).count()
        sio.emit("sync_status", {
            "status": "reconnected", "total": total,
            "synced": synced, "unsynced": total - synced,
        }, namespace="/")
        logger.info("[SYNC] Broadcast sync_status on reconnect: total=%d", total)
    except Exception as exc:
        logger.error("[SYNC] sync_status error: %s", exc)


def _flush_buffers(buffer_service) -> None:
    user_flushed   = buffer_service.flush_user_changes()
    config_flushed = buffer_service.flush_config_changes()
    if user_flushed > 0 or config_flushed > 0:
        logger.info("[BUFFER] Auto-flushed %d user + %d config changes", user_flushed, config_flushed)


def _make_log_retention_target(app: Flask):
    def _run():
        time.sleep(10)
        while True:
            try:
                with app.app_context():
                    from app.services.log_retention_service import get_log_retention_service
                    result = get_log_retention_service().cleanup_expired_logs()
                    logger.info("[RETENTION] Scheduled cleanup: deleted %d logs", result.get("deleted_count", 0))
            except Exception as exc:
                logger.error("[RETENTION] Scheduled cleanup error: %s", exc)
            time.sleep(86400)
    return _run


# ── Public factory ────────────────────────────────────────────────────────────

def create_app() -> Flask:
    global _socketio, _limiter

    app = Flask(__name__)
    app.config.from_object(Config)

    _init_session(app)

    db.init_app(app)
    _migrate_instance.init_app(app, db)

    _limiter = create_limiter()
    _limiter.init_app(app)

    _init_cors(app)
    _init_security_headers(app)

    _socketio = _init_socketio(app)

    app.data_freshness_monitor = DataFreshnessMonitor(_socketio, stale_threshold_seconds=15)

    _run_db_migrations(app)

    for bp in _BLUEPRINTS:
        app.register_blueprint(bp)

    _register_socketio_events(_socketio)
    _init_default_permissions(app)
    _start_background_threads(app, _socketio)

    return app


def get_socketio() -> SocketIO:
    """Return the global Socket.IO instance."""
    return _socketio


def get_limiter():
    """Return the global rate-limiter instance."""
    return _limiter
