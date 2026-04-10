"""
Data Freshness Monitor - Tracks when telemetry data becomes stale
"""

from datetime import datetime, timezone, timedelta
from threading import Timer
import json

class DataFreshnessMonitor:
    """Monitors telemetry data freshness and emits events when data becomes stale"""
    
    def __init__(self, socketio, stale_threshold_seconds=10):
        """
        Initialize monitor
        
        Args:
            socketio: Flask-SocketIO instance
            stale_threshold_seconds: Time in seconds before data is considered stale
        """
        self.socketio = socketio
        self.stale_threshold = stale_threshold_seconds
        self.last_data_time = {}  # device_id -> last_timestamp
        self.stale_status = {}    # device_id -> is_stale
        self.check_timers = {}    # device_id -> Timer
    
    def record_data(self, device_id: str):
        """Record that data was received from a device"""
        self.last_data_time[device_id] = datetime.now(timezone.utc)
        
        # If data was stale, it's now fresh again
        if self.stale_status.get(device_id, False):
            print(f"[FRESHNESS] Data from {device_id} is fresh again")
            self.stale_status[device_id] = False
            self._emit_data_fresh(device_id)
        
        # Cancel existing timer
        if device_id in self.check_timers:
            self.check_timers[device_id].cancel()
        
        # Schedule stale check
        timer = Timer(self.stale_threshold, self._check_stale, args=[device_id])
        timer.daemon = True
        timer.start()
        self.check_timers[device_id] = timer
    
    def _check_stale(self, device_id: str):
        """Check if data from device is stale"""
        if device_id not in self.last_data_time:
            return
        
        time_since_last = (datetime.now(timezone.utc) - self.last_data_time[device_id]).total_seconds()
        
        if time_since_last > self.stale_threshold:
            if not self.stale_status.get(device_id, False):
                print(f"[FRESHNESS] Data from {device_id} is STALE (no data for {time_since_last:.1f}s)")
                self.stale_status[device_id] = True
                self._emit_data_stale(device_id)
            
            # Schedule another check
            timer = Timer(self.stale_threshold, self._check_stale, args=[device_id])
            timer.daemon = True
            timer.start()
            self.check_timers[device_id] = timer
    
    def _emit_data_stale(self, device_id: str):
        """Emit data_stale only when MQTT is online — staleness while offline is expected.
        Also closes any open alert events so timers don't run forever after desktop stops.
        """
        try:
            from app import _desktop_mqtt_online
            if not _desktop_mqtt_online:
                print(f"[FRESHNESS] Suppressing data_stale for {device_id} — MQTT is offline")
                # Still close stale alert events even when MQTT is offline
                self._close_stale_alerts()
                return
        except Exception:
            pass
        try:
            self.socketio.emit(
                'data_stale',
                {
                    'device_id': device_id,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'message': f'No data received from {device_id} for {self.stale_threshold} seconds'
                },
                namespace='/'
            )
            print(f"[FRESHNESS] Emitted data_stale event for {device_id}")
        except Exception as e:
            print(f"[FRESHNESS] Error emitting data_stale: {e}")
        # Close open alert events — desktop is no longer sending data
        self._close_stale_alerts()

    def _close_stale_alerts(self):
        """Close open AlertEvent episodes when desktop goes stale/offline."""
        try:
            from app.services.alert_service import close_stale_open_events
            closed = close_stale_open_events(stale_threshold_minutes=0)
            if closed:
                print(f"[FRESHNESS] Force-closed {closed} open alert events (desktop offline)")
        except Exception as e:
            print(f"[FRESHNESS] Error closing stale alerts: {e}")
    
    def _emit_data_fresh(self, device_id: str):
        """Emit data_fresh event to frontend"""
        try:
            self.socketio.emit(
                'data_fresh',
                {
                    'device_id': device_id,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'message': f'Data resumed from {device_id}'
                },
                namespace='/'
            )
            print(f"[FRESHNESS] Emitted data_fresh event for {device_id}")
        except Exception as e:
            print(f"[FRESHNESS] Error emitting data_fresh: {e}")
    
    def get_status(self, device_id: str = None) -> dict:
        """Get freshness status for device(s)"""
        if device_id:
            return {
                'device_id': device_id,
                'is_stale': self.stale_status.get(device_id, False),
                'last_data_time': self.last_data_time.get(device_id).isoformat() if device_id in self.last_data_time else None
            }
        else:
            return {
                'devices': {
                    dev_id: {
                        'is_stale': self.stale_status.get(dev_id, False),
                        'last_data_time': self.last_data_time.get(dev_id).isoformat() if dev_id in self.last_data_time else None
                    }
                    for dev_id in self.last_data_time.keys()
                }
            }
    
    def cleanup(self, device_id: str):
        """Clean up timers for a device"""
        if device_id in self.check_timers:
            self.check_timers[device_id].cancel()
            del self.check_timers[device_id]
        if device_id in self.last_data_time:
            del self.last_data_time[device_id]
        if device_id in self.stale_status:
            del self.stale_status[device_id]
