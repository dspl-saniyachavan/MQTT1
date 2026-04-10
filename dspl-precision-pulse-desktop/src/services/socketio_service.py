"""
Socket.IO service for desktop with offline mode and local queuing
"""
import socketio
import threading
import time
import sqlite3
import json
from datetime import datetime
from typing import Callable, Optional
import logging

logger = logging.getLogger(__name__)

class DesktopSocketIOService:
    def __init__(self, db_path: str = None):
        import os
        if db_path is None:
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'precision_pulse.db')
        self.sio = socketio.Client(
            reconnection=True,
            reconnection_delay=1,
            reconnection_delay_max=5,
            reconnection_attempts=0  # unlimited retries
        )
        self.db_path = db_path
        self.is_connected = False
        self.is_syncing = False
        self.callbacks = {}
        self._pending_writes: list = []  # queue for edits received before connect
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup Socket.IO event handlers"""
        @self.sio.on('connect')
        def on_connect():
            self.is_connected = True
            logger.info('[Socket.IO] Connected to server')
            self._emit_callback('connection_status', {'connected': True})
            self._flush_pending_writes()
            self.sync_buffer()
        
        @self.sio.on('disconnect')
        def on_disconnect():
            self.is_connected = False
            logger.info('[Socket.IO] Disconnected from server')
            self._emit_callback('connection_status', {'connected': False})
        
        @self.sio.on('error')
        def on_error(error):
            logger.error(f'[Socket.IO] Error: {error}')
            self._emit_callback('connection_error', {'error': str(error)})
        
        @self.sio.on('parameter_value_updated')
        def on_parameter_value_updated(data):
            """Handle parameter value updates from backend (web admin edits)."""
            logger.info(f'[Socket.IO] Parameter value updated: {data}')
            try:
                param_id = data.get('parameter_id')
                value = data.get('value')
                timestamp = data.get('timestamp')

                if param_id is None or value is None:
                    return

                # ALWAYS write to SQLite — regardless of source or connection state
                self._store_parameter_value(param_id, value, timestamp)

                # Always update in-memory / UI via callback
                self._emit_callback('parameter_value_updated', data)
            except Exception as e:
                logger.error(f'[Socket.IO] Error handling parameter update: {e}')

        @self.sio.on('user_updated')
        def on_user_updated(data):
            """Handle user profile updates from backend (web profile edits)."""
            logger.info(f'[Socket.IO] User updated: {data}')
            self._emit_callback('user_updated', data)

        @self.sio.on('user_created')
        def on_user_created(data):
            logger.info(f'[Socket.IO] User created: {data}')
            self._emit_callback('user_created', data)

        @self.sio.on('user_deleted')
        def on_user_deleted(data):
            logger.info(f'[Socket.IO] User deleted: {data}')
            self._emit_callback('user_deleted', data)

        # Pre-register config events so they are wired to sio BEFORE connect() is called.
        # setup_config_handlers() adds its callbacks via on() after construction,
        # but sio.on() must be registered before the socket connects or events are dropped.
        @self.sio.on('config_update')
        def on_config_update(data):
            self._emit_callback('config_update', data)

        @self.sio.on('config_bulk_update')
        def on_config_bulk_update(data):
            self._emit_callback('config_bulk_update', data)

        @self.sio.on('remote_command')
        def on_remote_command(data):
            self._emit_callback('remote_command', data)
    
    def _flush_pending_writes(self):
        """Write any queued parameter edits to SQLite after reconnect."""
        if not self._pending_writes:
            return
        logger.info(f'[Socket.IO] Flushing {len(self._pending_writes)} pending writes')
        for param_id, value, timestamp in self._pending_writes:
            self._store_parameter_value(param_id, value, timestamp)
        self._pending_writes.clear()
    
    def _store_parameter_value(self, param_id: int, value: float, timestamp: str = None):
        """Store admin-edited parameter value in local SQLite parameter_stream table."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            if timestamp:
                cursor.execute(
                    'INSERT INTO parameter_stream (parameter_id, value, timestamp, synced) VALUES (?, ?, ?, 0)',
                    (int(param_id), float(value), timestamp)
                )
            else:
                cursor.execute(
                    "INSERT INTO parameter_stream (parameter_id, value, timestamp, synced) VALUES (?, ?, datetime('now', 'localtime'), 0)",
                    (int(param_id), float(value))
                )
            conn.commit()
            conn.close()
            logger.info(f'[Socket.IO] ✓ Admin edit stored in SQLite parameter_stream: param {param_id} = {value}')
        except Exception as e:
            logger.error(f'[Socket.IO] Error storing parameter value in parameter_stream: {e}')
    
    def connect(self, url: str = 'http://localhost:5000'):
        """Connect to Socket.IO server using polling transport only (Werkzeug dev server)"""
        try:
            self.sio.connect(url, transports=['polling'])
            logger.info(f'[Socket.IO] Connecting to {url}')
        except Exception as e:
            logger.error(f'[Socket.IO] Connection failed: {e}')
            self.is_connected = False
    
    def disconnect(self):
        """Disconnect from Socket.IO server"""
        if self.sio.connected:
            self.sio.disconnect()
            self.is_connected = False
    
    def emit_telemetry(self, telemetry_data: dict):
        """Emit telemetry data - queue if offline"""
        if self.is_connected:
            try:
                self.sio.emit('telemetry_stream', telemetry_data)
                logger.debug('[Socket.IO] Emitted telemetry')
            except Exception as e:
                logger.error(f'[Socket.IO] Emit failed: {e}')
                self._queue_to_buffer(telemetry_data)
        else:
            logger.info('[Socket.IO] Offline - queuing telemetry to buffer')
            self._queue_to_buffer(telemetry_data)
    
    def _queue_to_buffer(self, telemetry_data: dict):
        """Queue telemetry to local SQLite buffer"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS telemetry_buffer (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    data TEXT NOT NULL,
                    synced BOOLEAN DEFAULT 0
                )
            ''')
            
            cursor.execute(
                'INSERT INTO telemetry_buffer (data, synced) VALUES (?, ?)',
                (json.dumps(telemetry_data), 0)
            )
            conn.commit()
            conn.close()
            logger.info('[Buffer] Queued telemetry to buffer')
        except Exception as e:
            logger.error(f'[Buffer] Queue failed: {e}')
    
    def sync_buffer(self):
        """Sync buffered telemetry when connection restored"""
        if self.is_syncing or not self.is_connected:
            return
        
        self.is_syncing = True
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT id, data FROM telemetry_buffer WHERE synced = 0 LIMIT 100')
            rows = cursor.fetchall()
            
            if rows:
                logger.info(f'[Buffer] Syncing {len(rows)} buffered records')
                for row_id, data in rows:
                    try:
                        telemetry_data = json.loads(data)
                        self.sio.emit('telemetry_stream', telemetry_data)
                        cursor.execute('UPDATE telemetry_buffer SET synced = 1 WHERE id = ?', (row_id,))
                    except Exception as e:
                        logger.error(f'[Buffer] Sync record failed: {e}')
                
                conn.commit()
                logger.info('[Buffer] Sync completed')
            
            conn.close()
        except Exception as e:
            logger.error(f'[Buffer] Sync failed: {e}')
        finally:
            self.is_syncing = False

    def on(self, event: str, callback: Callable):
        """Register a callback for a Socket.IO event.
        config_update and config_bulk_update are pre-wired in setup_handlers.
        All other events are wired to self.sio on first registration.
        """
        _PRE_REGISTERED = {'connect', 'disconnect', 'error', 'parameter_value_updated',
                           'config_update', 'config_bulk_update', 'remote_command'}
        if event not in self.callbacks:
            self.callbacks[event] = []
            if event not in _PRE_REGISTERED:
                _event = event
                self.sio.on(_event, lambda data: self._emit_callback(_event, data))
                logger.info(f'[Socket.IO] Registered sio handler for event: {event}')
        self.callbacks[event].append(callback)

    def _emit_callback(self, event: str, data: dict):
        """Emit callback to registered listeners"""
        if event in self.callbacks:
            for callback in self.callbacks[event]:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f'[Callback] Error: {e}')
    
    def get_connection_status(self) -> bool:
        """Get current connection status"""
        return self.is_connected
    
    def get_buffer_count(self) -> int:
        """Get count of buffered records"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM telemetry_buffer WHERE synced = 0')
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0
