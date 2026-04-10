"""
Telemetry Service for parameter management and synchronization
"""

import random
from typing import Dict, List
from PySide6.QtCore import QObject, QTimer, Signal, Qt
from src.core.config import Config, ConfigManager
from telemetry_config import TELEMETRY_INTERVAL_SECONDS, TELEMETRY_INTERVAL_MS


class TelemetryService(QObject):
    """Service for managing telemetry data and synchronization"""
    
    # Signals
    parameters_updated = Signal()
    parameter_changed = Signal(str, float)
    connection_status_changed = Signal(bool)
    buffered_data_synced = Signal(int)
    
    def __init__(self, mqtt_service, database_manager, parameter_sync_service=None, config_service=None):
        super().__init__()
        self.mqtt_service = mqtt_service
        self.db = database_manager
        self.parameter_sync_service = parameter_sync_service
        self.config_service = config_service
        self.config_manager = ConfigManager()
        self.parameters = self._initialize_parameters()
        self.previous_values = {}
        self.last_print_time = 0
        self.push_timer = QTimer()
        self.heartbeat_timer = QTimer()
        self.refresh_timer = QTimer()
        self.flush_timer = QTimer()
        self.resume_timer = QTimer()
        self.stream_sync_timer = QTimer()  # periodic SQLite → PostgreSQL sync
        self.is_streaming = False
        self.is_connected = False
        self.is_flushing = False
        self.param_stream_sync = None  # kept for API compat, unused
        
        # Connect MQTT signals
        self.mqtt_service.connected.connect(self._on_mqtt_connected)
        self.mqtt_service.disconnected.connect(self._on_mqtt_disconnected)
        self.mqtt_service.parameter_update_received.connect(self._on_parameter_update)
        self.mqtt_service.config_update_received.connect(self._on_config_update)
        
        # Connect config manager signals
        self.config_manager.config_updated.connect(self._apply_config_update)
        
        # Register callbacks with configuration service if provided
        if self.config_service:
            self.config_service.register_callback('TELEMETRY_INTERVAL', self._on_telemetry_interval_changed)
            self.config_service.register_callback('HEARTBEAT_INTERVAL', self._on_heartbeat_interval_changed)
            self.config_service.register_callback('ENABLE_TELEMETRY', self._on_telemetry_enabled_changed)
            self.config_service.register_callback('MQTT_BROKER', self._on_mqtt_broker_changed)
            self.config_service.register_callback('MQTT_KEEP_ALIVE', self._on_mqtt_keep_alive_changed)
            self.config_service.register_callback('TELEMETRY_FETCH_INTERVAL_MS', self._on_fetch_interval_ms_changed)
            self.config_service.register_callback('MAX_CHART_DATA_POINTS', self._on_max_chart_points_changed)
            self.config_service.register_callback('TELEMETRY_RETENTION_DAYS', self._on_retention_days_changed)
            print("[TELEMETRY] Registered config callbacks")
        
        # Connect parameter sync service if provided
        if self.parameter_sync_service:
            self.parameter_sync_service.parameters_fetched.connect(self._on_parameters_fetched)
        
        self.refresh_timer.timeout.connect(self._refresh_telemetry_from_backend)
        self.flush_timer.timeout.connect(self._flush_buffered_data)
        self.resume_timer.timeout.connect(self._resume_streaming)
        self.stream_sync_timer.timeout.connect(self._flush_buffered_data)

        # Flush offline buffer via MQTT every 30 s when connected
        self.stream_sync_timer.start(30000)
        
    def _initialize_parameters(self) -> Dict:
        """Initialize parameters from database or parameter sync service"""
        if self.parameter_sync_service:
            synced_params = self.parameter_sync_service.get_enabled_parameters()
            if synced_params:
                print(f"[INIT] Got {len(synced_params)} parameters from sync service")
                return self._build_parameters_dict(synced_params)
        
        enabled_params = self.db.get_enabled_parameters()
        if enabled_params:
            print(f"[INIT] Got {len(enabled_params)} parameters from database")
            return self._build_parameters_dict(enabled_params)
        
        print("[INIT] No parameters found")
        return {}
    
    # Realistic operating ranges keyed by lowercase name fragment or unit
    _PARAM_RANGES = {
        'temperature':   (15.0,  45.0),
        'temp':          (15.0,  45.0),
        'humidity':      (30.0,  90.0),
        'humid':         (30.0,  90.0),
        'pressure':      (950.0, 1050.0),
        'wind':          (0.5,   75.0),
        'wind speed':    (0.5,   75.0),
        'speed':         (0.5,   75.0),
        'voltage':       (210.0, 240.0),
        'current':       (0.5,   15.0),
        'power':         (50.0,  500.0),
        'flow':          (1.0,   50.0),
        'level':         (10.0,  90.0),
        'vibration':     (0.1,   5.0),
        'rpm':           (500.0, 3000.0),
        'co2':           (400.0, 2000.0),
        'ph':            (6.0,   8.5),
        'light':         (100.0, 1000.0),
        'lux':           (100.0, 1000.0),
        'noise':         (30.0,  90.0),
        'db':            (30.0,  90.0),
    }

    @classmethod
    def _get_range(cls, name: str, unit: str) -> tuple:
        """Return (min, max) for a parameter based on its name or unit."""
        key = name.lower()
        for fragment, rng in cls._PARAM_RANGES.items():
            if fragment in key:
                return rng
        unit_key = unit.lower()
        for fragment, rng in cls._PARAM_RANGES.items():
            if fragment in unit_key:
                return rng
        # Generic fallback: 10–100 (never includes 0)
        return (10.0, 100.0)

    def _build_parameters_dict(self, params: List[Dict]) -> Dict:
        """Build parameters dictionary from list, preserving live values on refresh"""
        parameters = {}
        colors = ["#64a8fc", "#7f58f5", '#c084fc', '#f472b6', '#fb923c', '#34d399', '#fbbf24', '#f87171']
        existing = getattr(self, 'parameters', {})

        for i, param in enumerate(params):
            param_id = param.get('id') or param.get('parameter_id')
            name = param.get('name', 'Unknown')
            unit = param.get('unit', '')

            lo, hi = self._get_range(name, unit)
            # Override with explicit min/max from param only if they are non-zero and sensible
            p_min = param.get('min')
            p_max = param.get('max')
            if p_min is not None and p_max is not None and p_max > p_min and p_min >= 0:
                lo, hi = float(p_min), float(p_max)

            # Preserve live value AND admin_edited flag across refreshes
            existing_value = existing.get(param_id, {}).get('value')
            existing_admin_edited = existing.get(param_id, {}).get('_admin_edited', False)
            if existing_value is not None:
                initial_value = existing_value
            else:
                initial_value = round(lo + (hi - lo) * 0.5 + random.uniform(-(hi - lo) * 0.05, (hi - lo) * 0.05), 2)

            parameters[param_id] = {
                'id': param_id,
                'name': name,
                'value': initial_value,
                'unit': unit,
                'min': lo,
                'max': hi,
                'alert_min': param.get('alert_min'),
                'alert_max': param.get('alert_max'),
                'warn_min':  param.get('warn_min'),
                'warn_max':  param.get('warn_max'),
                'color': colors[i % len(colors)]
            }
            if existing_admin_edited:
                parameters[param_id]['_admin_edited'] = True

        return parameters
    
    def start_streaming(self, interval: int = None):
        """Start streaming telemetry data. Called from _on_mqtt_connected so
        is_connected is already True when _push_data first runs."""
        interval_ms = self._current_interval_ms()
        print(f"[TELEMETRY] Starting streaming (interval: {interval_ms}ms)")
        self.is_streaming = True

        if self.parameter_sync_service:
            self.parameter_sync_service._sync_parameters()
            self.parameter_sync_service.start_sync(30)

        if not self.parameters:
            self.refresh_parameters()

        self.push_timer.timeout.connect(self._generate_and_push, Qt.UniqueConnection)
        self.push_timer.start(interval_ms)
        self.heartbeat_timer.timeout.connect(self._send_heartbeat, Qt.UniqueConnection)
        self.heartbeat_timer.start(Config.HEARTBEAT_INTERVAL * 1000)
        print(f"[TELEMETRY] Streaming started with {len(self.parameters)} parameters")
        
    def stop_streaming(self):
        """Stop streaming telemetry data"""
        self.is_streaming = False
        self.push_timer.stop()
        self.heartbeat_timer.stop()
        self.refresh_timer.stop()
        
    def _generate_data(self):
        """Generate sensor data with realistic random drift."""
        for param_id, param in self.parameters.items():
            lo, hi = param['min'], param['max']
            variation = (hi - lo) * 0.02
            new_value = param['value'] + random.uniform(-variation, variation)
            new_value = max(lo, min(hi, new_value))
            param['value'] = round(new_value, 2)
            # Clear admin_edited flag so normal drift resumes from the set value
            param.pop('_admin_edited', None)
    
    def _generate_and_push(self):
        """Generate data every tick regardless of MQTT connection state.
        ONLINE  → generate → write SQLite → publish MQTT → PostgreSQL
        OFFLINE → generate → write SQLite → buffer to local_buffer (flushed on reconnect)
        The push_timer NEVER stops due to MQTT state — only stop_streaming() stops it.
        """
        self._generate_data()
        self.parameters_updated.emit()  # update desktop UI on main thread
        import threading
        threading.Thread(target=self._push_data, daemon=True).start()
            
    def _push_data(self):
        """Correct data flow:
        1. Write to SQLite parameter_stream (synced=0)
        2a. ONLINE  → publish via MQTT → backend writes to PostgreSQL
                    → mark SQLite record synced=1
        2b. OFFLINE → write to local_buffer; SQLite record stays synced=0
                    → flushed to backend via HTTP on reconnect
        PostgreSQL only ever receives data that originated from SQLite.
        """
        if not self.parameters:
            return

        from datetime import datetime
        from .parameter_streaming_data import ParameterStreamingData

        current_timestamp = datetime.now().isoformat()

        streaming_params = [
            ParameterStreamingData.from_parameter(p, self.mqtt_service.device_id, current_timestamp)
            for p in self.parameters.values()
        ]

        # ── Step 1: write to SQLite first (synced=0) ──────────────────────────
        sqlite_ids = []
        for param in streaming_params:
            param_id = int(param.parameter_id) if param.parameter_id is not None else None
            value    = float(param.value)       if param.value       is not None else None
            if param_id is None or value is None:
                continue
            row_id = self.db.store_parameter_stream(
                parameter_id=param_id,
                value=value,
                timestamp=current_timestamp
            )
            if row_id:
                sqlite_ids.append((row_id, current_timestamp))

        if not sqlite_ids:
            return

        # ── Step 2a: ONLINE — publish SQLite rows via MQTT ────────────────────
        if self.is_connected:
            success = self.mqtt_service.publish_telemetry(
                [p.to_dict() for p in streaming_params]
            )
            if success:
                # Mark the SQLite rows we just wrote as synced
                self.db.mark_parameter_stream_synced_by_timestamp(current_timestamp)
                print(f"[TELEMETRY] SQLite→MQTT→PostgreSQL: {len(streaming_params)} params")
            else:
                # Publish failed — move to local_buffer so flush can retry
                print("[TELEMETRY] MQTT publish failed — moving to local_buffer")
                for param in streaming_params:
                    val = float(param.value) if param.value is not None else None
                    if val is not None:
                        self.db.buffer_telemetry(
                            parameter_id=int(param.parameter_id) if param.parameter_id is not None else 0,
                            value=val
                        )
        else:
            # ── Step 2b: OFFLINE — buffer for later flush ─────────────────────
            for param in streaming_params:
                val = float(param.value) if param.value is not None else None
                if val is not None:
                    self.db.buffer_telemetry(
                        parameter_id=int(param.parameter_id) if param.parameter_id is not None else 0,
                        value=val
                    )
            print(f"[TELEMETRY] Offline — {len(streaming_params)} params buffered (SQLite synced=0)")

    
    def _on_mqtt_connected(self):
        """MQTT connected — start streaming if not already running, flush buffer."""
        self.is_connected = True
        self.connection_status_changed.emit(True)
        print("[MQTT] CONNECTED — starting/resuming data streaming")

        if self.is_streaming:
            # Already streaming (e.g. reconnect) — restart timers if stopped
            if not self.push_timer.isActive():
                interval_ms = self._current_interval_ms()
                self.push_timer.start(interval_ms)
                print(f"[MQTT] push_timer restarted at {interval_ms}ms")
            if not self.heartbeat_timer.isActive():
                self.heartbeat_timer.start(Config.HEARTBEAT_INTERVAL * 1000)
        else:
            # First connect after login — start streaming now
            self.start_streaming()

        self._flush_buffered_data()
        self.refresh_parameters()
        if self.parameter_sync_service:
            self.parameter_sync_service._sync_parameters()

    def _current_interval_ms(self) -> int:
        """Return the current telemetry interval in ms from config or default."""
        if self.config_service:
            try:
                return int(self.config_service.get_config(
                    'TELEMETRY_FETCH_INTERVAL_MS', TELEMETRY_INTERVAL_MS))
            except Exception:
                pass
        return TELEMETRY_INTERVAL_MS
    
    def _resume_streaming(self):
        """Resume live streaming after buffered data flush"""
        self.resume_timer.stop()
        if self.is_streaming:
            self.is_flushing = False
            # Use live config value if available, else fall back to telemetry_config
            interval_ms = TELEMETRY_INTERVAL_MS
            if self.config_service:
                try:
                    interval_ms = int(self.config_service.get_config('TELEMETRY_FETCH_INTERVAL_MS', TELEMETRY_INTERVAL_MS))
                except Exception:
                    pass
            self.push_timer.start(interval_ms)
            print(f"[FLUSH] Resumed live streaming at {interval_ms}ms")
    
    def _on_mqtt_disconnected(self):
        """MQTT disconnected — keep generating data, route to local_buffer.
        push_timer keeps running so data generation continues uninterrupted.
        Only heartbeat stops (broker is unreachable).
        On reconnect, local_buffer is flushed to backend automatically.
        """
        self.is_connected = False
        self.connection_status_changed.emit(False)
        print("[MQTT] DISCONNECTED — data generation continues, routing to local_buffer")

        # Stop heartbeat only — push_timer keeps running so _generate_and_push
        # continues to fire. _push_data sees is_connected=False and writes to
        # local_buffer instead of publishing via MQTT.
        self.heartbeat_timer.stop()

        # Ensure push_timer is running (it should be, but restart if somehow stopped)
        if self.is_streaming and not self.push_timer.isActive():
            interval_ms = TELEMETRY_INTERVAL_MS
            if self.config_service:
                try:
                    interval_ms = int(self.config_service.get_config(
                        'TELEMETRY_FETCH_INTERVAL_MS', TELEMETRY_INTERVAL_MS))
                except Exception:
                    pass
            self.push_timer.start(interval_ms)
            print(f"[MQTT] push_timer restarted at {interval_ms}ms for offline buffering")
    
    def _flush_buffered_data(self):
        """Flush local_buffer to backend via MQTT only."""
        if not self.is_connected:
            return
        try:
            buffered = self.db.get_buffered_data()
            if not buffered:
                return
            print(f"[FLUSH] Flushing {len(buffered)} buffered records via MQTT")
            success = self.mqtt_service.publish_buffered_data(buffered)
            if success:
                buffer_ids = [rec['id'] for rec in buffered]
                self.db.mark_data_synced(buffer_ids)
                self.db.delete_buffered_data(buffer_ids)
                self.buffered_data_synced.emit(len(buffered))
                print(f"[FLUSH] Flushed {len(buffered)} records via MQTT")
        except Exception as e:
            print(f"[FLUSH] Error: {e}")
    
    def _delete_buffered_data(self, buffer_ids: List[int]):
        """Delete buffered data after successful sync"""
        try:
            self.db.delete_buffered_data(buffer_ids)
            print(f"[FLUSH] Deleted {len(buffer_ids)} buffered records from local_buffer table")
        except Exception as e:
            print(f"[FLUSH] Error deleting buffered data: {e}")
    
    def _on_parameter_update(self, param_id: str, new_value: float):
        """Handle parameter update from web"""
        if param_id in self.parameters:
            self.parameters[param_id]['value'] = float(new_value)
            self.parameter_changed.emit(param_id, float(new_value))
    
    def _send_heartbeat(self):
        """Send heartbeat to indicate device is alive"""
        if self.mqtt_service.client.is_connected:
            self.mqtt_service._send_heartbeat()
                        
    def refresh_parameters(self):
        """Refresh parameters from database or API"""
        old_params = set(self.parameters.keys())
        
        if self.parameter_sync_service:
            self.parameter_sync_service._sync_parameters()
            synced_params = self.parameter_sync_service.get_enabled_parameters()
            if synced_params:
                self.parameters = self._build_parameters_dict(synced_params)
            else:
                self.parameters = self._initialize_parameters()
        else:
            self.parameters = self._initialize_parameters()
        
        new_params = set(self.parameters.keys())
        
        added = new_params - old_params
        for param_id in added:
            print(f"[PARAM] Added: {self.parameters[param_id]['name']}")
        
        removed = old_params - new_params
        for param_id in removed:
            print(f"[PARAM] Removed: {param_id}")
        
        self.parameters_updated.emit()
        print(f"[PARAM] Refreshed {len(self.parameters)} parameters")
    
    def get_parameters(self) -> Dict:
        """Get current parameters"""
        return self.parameters
    
    def get_parameter(self, param_id: str) -> Dict:
        """Get specific parameter"""
        return self.parameters.get(param_id)
    
    def set_parameter_value(self, param_id: str, value: float):
        """Manually set parameter value"""
        if param_id in self.parameters:
            self.parameters[param_id]['value'] = value
            self.parameter_changed.emit(param_id, value)
    
    def _on_config_update(self, config_data: dict):
        """Handle configuration update from remote command"""
        self.config_manager.update_config(config_data)
    
    def _on_parameters_fetched(self, parameters: list):
        """Handle parameters fetched from sync service — only stream enabled ones."""
        enabled = [p for p in parameters if p.get('enabled', True)]
        if enabled:
            print(f"[PARAM_SYNC] Updating parameters: {len(enabled)} enabled of {len(parameters)} total")
            self.parameters = self._build_parameters_dict(enabled)
            self.parameters_updated.emit()
    
    def _apply_config_update(self, key: str, value: str):
        """Apply configuration update to running service"""
        if key == 'TELEMETRY_INTERVAL':
            new_interval = int(value)
            if self.is_streaming:
                self.push_timer.stop()
                self.push_timer.start(new_interval * 1000)
        
        elif key == 'HEARTBEAT_INTERVAL':
            new_interval = int(value)
            if self.is_streaming:
                self.heartbeat_timer.stop()
                self.heartbeat_timer.start(new_interval * 1000)
    
    def _on_telemetry_interval_changed(self, key: str, new_value: str, old_value: str):
        """Handle telemetry interval change from system config"""
        try:
            new_interval = int(new_value)
            old_interval = int(old_value) if old_value else TELEMETRY_INTERVAL_SECONDS
            
            if self.is_streaming and new_interval != old_interval:
                print(f"[TELEMETRY] Interval changed: {old_interval}s -> {new_interval}s")
                self.push_timer.stop()
                self.push_timer.start(new_interval * 1000)
                print(f"[TELEMETRY] Updated push timer to {new_interval}s")
        except (ValueError, TypeError) as e:
            print(f"[TELEMETRY] Error parsing interval: {e}")
    
    def _on_heartbeat_interval_changed(self, key: str, new_value: str, old_value: str):
        """Handle heartbeat interval change from system config"""
        try:
            new_interval = int(new_value)
            old_interval = int(old_value) if old_value else 30
            
            if self.is_streaming and new_interval != old_interval:
                print(f"[TELEMETRY] Heartbeat interval changed: {old_interval}s -> {new_interval}s")
                self.heartbeat_timer.stop()
                self.heartbeat_timer.start(new_interval * 1000)
                print(f"[TELEMETRY] Updated heartbeat timer to {new_interval}s")
        except (ValueError, TypeError) as e:
            print(f"[TELEMETRY] Error parsing heartbeat interval: {e}")
    
    def _on_telemetry_enabled_changed(self, key: str, new_value: str, old_value: str):
        """Handle telemetry enable/disable from system config"""
        try:
            is_enabled = new_value.lower() in ('true', '1', 'yes')
            was_enabled = old_value and old_value.lower() in ('true', '1', 'yes')
            
            if is_enabled != was_enabled:
                if is_enabled and not self.is_streaming:
                    print("[TELEMETRY] Telemetry enabled via config")
                    self.start_streaming()
                elif not is_enabled and self.is_streaming:
                    print("[TELEMETRY] Telemetry disabled via config")
                    self.stop_streaming()
        except Exception as e:
            print(f"[TELEMETRY] Error handling telemetry enable/disable: {e}")

    def _on_mqtt_broker_changed(self, key: str, new_value: str, old_value: str):
        """Reconnect MQTT when broker address changes."""
        if new_value == old_value:
            return
        print(f"[TELEMETRY] MQTT_BROKER changed: {old_value} -> {new_value}")
        from src.core.config import Config
        Config.MQTT_BROKER = new_value
        try:
            self.mqtt_service.disconnect()
            self.mqtt_service.connect()
            print(f"[TELEMETRY] Reconnected MQTT to {new_value}")
        except Exception as e:
            print(f"[TELEMETRY] Error reconnecting MQTT: {e}")

    def _on_mqtt_keep_alive_changed(self, key: str, new_value: str, old_value: str):
        """Update MQTT keepalive and reconnect."""
        try:
            ka = int(new_value)
            from src.core.config import Config
            Config.MQTT_KEEPALIVE = ka
            print(f"[TELEMETRY] MQTT_KEEP_ALIVE -> {ka}s (reconnect required)")
            self.mqtt_service.disconnect()
            self.mqtt_service.connect()
        except Exception as e:
            print(f"[TELEMETRY] Error applying MQTT_KEEP_ALIVE: {e}")

    def _on_fetch_interval_ms_changed(self, key: str, new_value: str, old_value: str):
        """Update the push timer interval (desktop sends at this rate)."""
        try:
            ms = int(new_value)
            print(f"[TELEMETRY] TELEMETRY_FETCH_INTERVAL_MS -> {ms}ms")
            if self.is_streaming:
                self.push_timer.stop()
                self.push_timer.start(ms)
        except Exception as e:
            print(f"[TELEMETRY] Error applying TELEMETRY_FETCH_INTERVAL_MS: {e}")

    def _on_max_chart_points_changed(self, key: str, new_value: str, old_value: str):
        """Resize all line chart deques to the new max."""
        try:
            pts = int(new_value)
            print(f"[TELEMETRY] MAX_CHART_DATA_POINTS -> {pts}")
            # Notify telemetry widget via parameters_updated so it can resize charts
            self.parameters_updated.emit()
        except Exception as e:
            print(f"[TELEMETRY] Error applying MAX_CHART_DATA_POINTS: {e}")

    def _on_retention_days_changed(self, key: str, new_value: str, old_value: str):
        """Log retention change — backend enforces this on queries."""
        try:
            days = int(new_value)
            print(f"[TELEMETRY] TELEMETRY_RETENTION_DAYS -> {days} days")
        except Exception as e:
            print(f"[TELEMETRY] Error applying TELEMETRY_RETENTION_DAYS: {e}")
    
    def _refresh_telemetry_from_backend(self):
        """No-op: telemetry values arrive via MQTT only."""
        pass

    def _on_admin_parameter_value_updated(self, data: dict):
        """Called by Socket.IO when admin edits a value.
        Locks the parameter value so _generate_data does not overwrite it.
        """
        param_id = data.get('parameter_id')
        value = data.get('value')
        if param_id is None or value is None:
            return

        # Try both str and int keys — the dict key type depends on the data source
        key = None
        if str(param_id) in self.parameters:
            key = str(param_id)
        elif param_id in self.parameters:
            key = param_id
        elif int(param_id) in self.parameters:
            key = int(param_id)

        if key is not None:
            self.parameters[key]['value'] = float(value)
            self.parameter_changed.emit(str(key), float(value))
            self.parameters_updated.emit()
            print(f"[ADMIN_UPDATE] Parameter {param_id} → {value}")
        else:
            print(f"[ADMIN_UPDATE] Parameter {param_id} not found in parameters dict")

    def handle_admin_parameter_update(self, param_id: int, value: float, timestamp: str):
        """Legacy method kept for compatibility."""
        self._on_admin_parameter_value_updated({'parameter_id': param_id, 'value': value, 'timestamp': timestamp})
