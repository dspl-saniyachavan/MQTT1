"""
Parameter synchronization service for desktop application
"""

from typing import List, Dict
from PySide6.QtCore import QObject, Signal, QTimer
import sqlite3


class ParameterSyncService(QObject):
    """Service for syncing parameters from backend via MQTT"""

    parameters_fetched = Signal(list)
    parameter_updated = Signal(dict)
    sync_error = Signal(str)

    def __init__(self, backend_url: str = "http://localhost:5000", mqtt_service=None):
        super().__init__()
        self.mqtt_service = mqtt_service
        self.parameters = []
        self.sync_timer = QTimer()
        self.sync_timer.timeout.connect(self._sync_parameters)
        self._db_path = None  # set by TelemetryService after construction

        if mqtt_service:
            mqtt_service.message_received.connect(self._on_mqtt_message)

    def set_db_path(self, db_path: str):
        self._db_path = db_path

    def start_sync(self, interval: int = 30):
        self.sync_timer.start(interval * 1000)
        self._sync_parameters()

    def stop_sync(self):
        self.sync_timer.stop()

    def _sync_parameters(self):
        """Load all parameters from local SQLite (populated by MQTT subscriber on backend)."""
        if not self._db_path:
            return
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT id, name, unit, enabled, description, alert_min, alert_max, warn_min, warn_max FROM parameters'
                )
                self.parameters = [
                    {'id': row[0], 'name': row[1], 'unit': row[2],
                     'enabled': bool(row[3]), 'description': row[4],
                     'alert_min': row[5], 'alert_max': row[6],
                     'warn_min': row[7], 'warn_max': row[8]}
                    for row in cursor.fetchall()
                ]
            print(f"[PARAM_SYNC] Loaded {len(self.parameters)} parameters from SQLite")
            self.parameters_fetched.emit(self.parameters)
        except Exception as e:
            print(f"[PARAM_SYNC] SQLite load error: {e}")
            self.sync_error.emit(str(e))

    def _on_mqtt_message(self, topic: str, payload: dict):
        """Handle MQTT parameter sync messages from backend."""
        if 'sync/parameters' not in topic:
            return
        # Decrypt if needed
        if '_enc' in payload:
            try:
                from src.core.encryption import decrypt_payload
                payload = decrypt_payload(payload['_enc'])
            except Exception as e:
                print(f'[PARAM_SYNC] Decryption failed: {e}')
                return

        action = payload.get('action') or {
            'parameter_created': 'create',
            'parameter_updated': 'update',
            'parameter_deleted': 'delete',
        }.get(payload.get('type', ''), '')
        param = payload.get('parameter')
        if not param or not action:
            return

        # Update SQLite
        if self._db_path:
            try:
                with sqlite3.connect(self._db_path) as conn:
                    cursor = conn.cursor()
                    if action == 'delete':
                        cursor.execute('DELETE FROM parameters WHERE id=?', (param.get('id'),))
                    elif action == 'create':
                        cursor.execute('''
                            INSERT OR REPLACE INTO parameters
                            (id, name, unit, description, enabled, alert_min, alert_max, warn_min, warn_max)
                            VALUES (?,?,?,?,?,?,?,?,?)
                        ''', (param.get('id'), param.get('name'), param.get('unit'),
                              param.get('description',''), 1 if param.get('enabled', True) else 0,
                              param.get('alert_min'), param.get('alert_max'),
                              param.get('warn_min'), param.get('warn_max')))
                    else:  # update
                        cursor.execute('''
                            INSERT OR REPLACE INTO parameters
                            (id, name, unit, description, enabled, alert_min, alert_max, warn_min, warn_max)
                            VALUES (?,?,?,?,?,?,?,?,?)
                        ''', (param.get('id'), param.get('name'), param.get('unit'),
                              param.get('description',''), 1 if param.get('enabled', True) else 0,
                              param.get('alert_min'), param.get('alert_max'),
                              param.get('warn_min'), param.get('warn_max')))
                    conn.commit()
            except Exception as e:
                print(f'[PARAM_SYNC] SQLite write error: {e}')

        # Update in-memory list
        if action == 'delete':
            self.parameters = [p for p in self.parameters if p.get('id') != param.get('id')]
        elif action == 'create':
            if not any(p.get('id') == param.get('id') for p in self.parameters):
                self.parameters.append(param)
        else:
            for i, p in enumerate(self.parameters):
                if p.get('id') == param.get('id'):
                    self.parameters[i] = param
                    break
            else:
                self.parameters.append(param)

        self.parameter_updated.emit(param)
        self.parameters_fetched.emit(self.parameters)
        print(f'[PARAM_SYNC] MQTT {action}: {param.get("name")}')

    def get_enabled_parameters(self) -> List[Dict]:
        return [p for p in self.parameters if p.get('enabled', False)]

    def get_all_parameters(self) -> List[Dict]:
        return self.parameters
