"""
Parameter Stream Sync Service — flushes offline-buffered data to backend via MQTT only.
Called by TelemetryService._flush_buffered_data() when MQTT reconnects.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

_MIN_AGE_SECONDS = 5


class ParameterStreamSyncService:
    """Sync parameter_stream data from desktop SQLite to backend via MQTT (offline flush)."""

    def __init__(self, db_manager, backend_url: str = "http://localhost:5000"):
        self.db_manager = db_manager
        # backend_url kept for API compatibility but unused — all sync is via MQTT
        self.token = None
        logger.info("[PARAM_STREAM_SYNC] Service initialized (MQTT-only)")

    def set_auth_token(self, token: str):
        self.token = token

    def get_unsynced_parameter_stream(self) -> List[Dict]:
        try:
            cutoff = (datetime.now() - timedelta(seconds=_MIN_AGE_SECONDS)).isoformat()
            with sqlite3.connect(self.db_manager.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, parameter_id, value, timestamp
                    FROM parameter_stream
                    WHERE synced = 0
                      AND timestamp <= ?
                    ORDER BY timestamp ASC
                ''', (cutoff,))
                return [
                    {'id': row[0], 'parameter_id': row[1],
                     'value': row[2], 'timestamp': row[3]}
                    for row in cursor.fetchall()
                ]
        except Exception as e:
            logger.error("[PARAM_STREAM_SYNC] Error fetching unsynced records: %s", e)
            return []

    def sync_parameter_stream_to_backend(self, mqtt_service=None) -> bool:
        """Flush unsynced offline-buffered rows to backend via MQTT publish_buffered_data."""
        unsynced = self.get_unsynced_parameter_stream()
        if not unsynced:
            return True

        if not mqtt_service or not mqtt_service.is_connected:
            logger.warning("[PARAM_STREAM_SYNC] MQTT not connected — cannot flush")
            return False

        records = [
            {'parameter_id': r['parameter_id'], 'value': r['value'], 'timestamp': r['timestamp']}
            for r in unsynced
        ]
        logger.info("[PARAM_STREAM_SYNC] Flushing %d offline records via MQTT", len(records))
        success = mqtt_service.publish_buffered_data(records)
        if success:
            self.mark_synced(unsynced)
        return success

    def mark_synced(self, records: List[Dict]):
        try:
            ids = [r['id'] for r in records]
            self.db_manager.mark_parameter_stream_synced(ids)
            logger.info("[PARAM_STREAM_SYNC] Marked %d records as synced", len(ids))
        except Exception as e:
            logger.error("[PARAM_STREAM_SYNC] Error marking synced: %s", e)

    def get_sync_status(self) -> Dict:
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM parameter_stream WHERE synced = 0')
                unsynced = cursor.fetchone()[0]
                cursor.execute('SELECT COUNT(*) FROM parameter_stream')
                total = cursor.fetchone()[0]
                return {
                    'unsynced_count': unsynced,
                    'total_count': total,
                    'sync_percentage': (total - unsynced) / total * 100 if total > 0 else 0,
                }
        except Exception as e:
            logger.error("[PARAM_STREAM_SYNC] Error getting sync status: %s", e)
            return {'unsynced_count': 0, 'total_count': 0, 'sync_percentage': 0}
