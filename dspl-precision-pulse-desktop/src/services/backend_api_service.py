"""
BackendAPIService — all mutations now go through MQTT.
Read-only operations (get_parameters, get_parameter_stream_latest) still
use HTTP since they need an immediate response.
"""

import json
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Optional
from src.core.config import Config

logger = logging.getLogger(__name__)


class BackendAPIService:
    """Service to communicate with backend — mutations via MQTT, reads via HTTP."""

    def __init__(self, token: Optional[str] = None, mqtt_service=None):
        self.token = token
        self.base_url = Config.BACKEND_URL
        self.mqtt_service = mqtt_service
        self.headers = {'Content-Type': 'application/json'}
        if token:
            self.headers['Authorization'] = f'Bearer {token}'

    def set_token(self, token: str):
        self.token = token
        self.headers['Authorization'] = f'Bearer {token}'

    def set_mqtt_service(self, mqtt_service):
        self.mqtt_service = mqtt_service

    # ── MQTT publish helper ───────────────────────────────────────────────────

    def _publish(self, topic: str, payload: dict) -> bool:
        """Publish payload to MQTT broker."""
        if self.mqtt_service and self.mqtt_service.is_connected:
            try:
                self.mqtt_service.client.publish(topic, json.dumps(payload), qos=1)
                logger.info('[API] MQTT publish to %s', topic)
                return True
            except Exception as e:
                logger.error('[API] MQTT publish error: %s', e)
        logger.warning('[API] MQTT not connected — cannot publish to %s', topic)
        return False

    # ── Parameters (mutations via MQTT) ───────────────────────────────────────

    def get_parameters(self) -> Optional[List[Dict]]:
        """Fetch all parameters from backend via HTTP (read-only)."""
        try:
            import requests
            url = f"{self.base_url}/api/parameters"
            response = requests.get(url, headers=self.headers, timeout=5)
            if response.status_code == 200:
                return response.json()
            logger.error('[API] get_parameters HTTP %s', response.status_code)
            return None
        except Exception as e:
            logger.error('[API] get_parameters error: %s', e)
            return None

    def add_parameter(self, name: str, unit: str, description: str) -> bool:
        """Add new parameter via MQTT."""
        return self._publish('precisionpulse/sync/parameters', {
            'type': 'parameter_created', 'action': 'create',
            'msg_id': str(uuid.uuid4()),
            'timestamp': datetime.now().isoformat(),
            'source': 'desktop',
            'parameter': {'name': name, 'unit': unit, 'description': description, 'enabled': True},
        })

    def update_parameter(self, param_id: int, **kwargs) -> bool:
        """Update parameter via MQTT."""
        return self._publish('precisionpulse/sync/parameters', {
            'type': 'parameter_updated', 'action': 'update',
            'msg_id': str(uuid.uuid4()),
            'timestamp': datetime.now().isoformat(),
            'source': 'desktop',
            'parameter': {'id': param_id, **kwargs},
        })

    def delete_parameter(self, param_id: int) -> bool:
        """Delete parameter via MQTT."""
        return self._publish('precisionpulse/sync/parameters', {
            'type': 'parameter_deleted', 'action': 'delete',
            'msg_id': str(uuid.uuid4()),
            'timestamp': datetime.now().isoformat(),
            'source': 'desktop',
            'parameter': {'id': param_id},
        })

    # ── Parameter stream (reads via HTTP, value edit via MQTT) ────────────────

    def get_parameter_stream_latest(self, token: Optional[str] = None) -> Optional[Dict]:
        """Get latest parameter stream values via HTTP (read-only)."""
        try:
            import requests
            url = f"{self.base_url}/api/parameter-stream/latest"
            headers = self.headers.copy()
            if token:
                headers['Authorization'] = f'Bearer {token}'
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error('[API] get_parameter_stream_latest error: %s', e)
            return None

    def update_parameter_value(self, param_id: int, value: float) -> bool:
        """Publish admin parameter value edit via MQTT."""
        return self._publish(f'precisionpulse/desktop/parameter/edit', {
            'type': 'parameter_value_updated',
            'parameter_id': param_id,
            'value': value,
            'timestamp': datetime.now().isoformat(),
            'source': 'desktop',
        })
