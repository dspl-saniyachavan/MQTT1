"""
Unit tests for telemetry generation, timestamping, and buffering logic
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestTelemetryGeneration(unittest.TestCase):
    """Test telemetry data generation"""
    
    def setUp(self):
        """Setup test fixtures"""
        self.mock_mqtt = Mock()
        self.mock_mqtt.device_id = "test_device_001"
        self.mock_mqtt.client = Mock()
        self.mock_mqtt.client.is_connected.return_value = True
        self.mock_mqtt.connected = Mock()
        self.mock_mqtt.disconnected = Mock()
        self.mock_mqtt.parameter_update_received = Mock()
        self.mock_mqtt.config_update_received = Mock()
        
        self.mock_db = Mock()
        self.mock_db.get_enabled_parameters.return_value = [
            {'id': 'param_1', 'name': 'Temperature', 'unit': '°C', 'min': 0, 'max': 100, 'value': 50},
            {'id': 'param_2', 'name': 'Pressure', 'unit': 'kPa', 'min': 0, 'max': 200, 'value': 100}
        ]
        
        from src.services.telemetry_service import TelemetryService
        self.telemetry_service = TelemetryService(self.mock_mqtt, self.mock_db)
    
    def test_parameters_initialization(self):
        """Test parameters are initialized correctly"""
        self.assertEqual(len(self.telemetry_service.parameters), 2)
        self.assertIn('param_1', self.telemetry_service.parameters)
        self.assertIn('param_2', self.telemetry_service.parameters)
    
    def test_parameter_values_within_bounds(self):
        """Test generated parameter values stay within min/max bounds"""
        for _ in range(10):
            self.telemetry_service._generate_data()
            for param in self.telemetry_service.parameters.values():
                self.assertGreaterEqual(param['value'], param['min'])
                self.assertLessEqual(param['value'], param['max'])
    
    def test_parameter_value_variation(self):
        """Test parameter values change over time"""
        initial_values = {pid: p['value'] for pid, p in self.telemetry_service.parameters.items()}
        
        for _ in range(5):
            self.telemetry_service._generate_data()
        
        final_values = {pid: p['value'] for pid, p in self.telemetry_service.parameters.items()}
        
        # At least one parameter should have changed
        changed = any(initial_values[pid] != final_values[pid] for pid in initial_values)
        self.assertTrue(changed)
    
    def test_parameter_structure(self):
        """Test parameter structure is correct"""
        for param in self.telemetry_service.parameters.values():
            self.assertIn('id', param)
            self.assertIn('name', param)
            self.assertIn('value', param)
            self.assertIn('unit', param)
            self.assertIn('min', param)
            self.assertIn('max', param)
            self.assertIn('color', param)


class TestTimestamping(unittest.TestCase):
    """Test timestamping functionality"""
    
    def test_timestamp_format_iso8601(self):
        """Test timestamps are in ISO8601 format"""
        timestamp = datetime.now().isoformat()
        parsed = datetime.fromisoformat(timestamp)
        self.assertIsInstance(parsed, datetime)
    
    def test_streaming_data_timestamp(self):
        """Test ParameterStreamingData includes timestamp"""
        from src.services.parameter_streaming_data import ParameterStreamingData
        
        param = {
            'id': 'param_1',
            'name': 'Temperature',
            'value': 25.5,
            'unit': '°C'
        }
        timestamp = datetime.now().isoformat()
        
        streaming_data = ParameterStreamingData.from_parameter(param, 'device_001', timestamp)
        
        self.assertEqual(streaming_data.timestamp, timestamp)
        self.assertEqual(streaming_data.device_id, 'device_001')
        self.assertEqual(streaming_data.value, 25.5)
    
    def test_payload_timestamp_consistency(self):
        """Test all parameters in payload have same timestamp"""
        from src.services.parameter_streaming_data import ParameterStreamingData, ParameterStreamingPayload
        
        params = [
            {'id': 'p1', 'name': 'Temp', 'value': 25, 'unit': '°C'},
            {'id': 'p2', 'name': 'Press', 'value': 100, 'unit': 'kPa'}
        ]
        timestamp = datetime.now().isoformat()
        
        streaming_params = [
            ParameterStreamingData.from_parameter(p, 'device_001', timestamp)
            for p in params
        ]
        
        payload = ParameterStreamingPayload(
            client_id='device_001',
            timestamp=timestamp,
            parameters=streaming_params
        )
        
        self.assertEqual(payload.timestamp, timestamp)
        for param in payload.parameters:
            self.assertEqual(param.timestamp, timestamp)


class TestBuffering(unittest.TestCase):
    """Test data buffering logic"""
    
    def setUp(self):
        """Setup test fixtures with integer param IDs (as used by real DB)"""
        self.mock_mqtt = Mock()
        self.mock_mqtt.device_id = "test_device_001"
        self.mock_mqtt.client = Mock()
        self.mock_mqtt.client.is_connected.return_value = False
        self.mock_mqtt.connected = Mock()
        self.mock_mqtt.disconnected = Mock()
        self.mock_mqtt.parameter_update_received = Mock()
        self.mock_mqtt.config_update_received = Mock()
        
        self.mock_db = Mock()
        # Use integer IDs — _push_data calls int(param.parameter_id)
        self.mock_db.get_enabled_parameters.return_value = [
            {'id': 1, 'name': 'Temperature', 'unit': '°C', 'min': 0, 'max': 100, 'value': 50}
        ]
        self.mock_db.buffer_telemetry = Mock()
        self.mock_db.get_buffered_data = Mock(return_value=[])
        self.mock_db.store_parameter_stream = Mock(return_value=1)
        
        from src.services.telemetry_service import TelemetryService
        self.telemetry_service = TelemetryService(self.mock_mqtt, self.mock_db)
    
    def test_data_buffered_when_disconnected(self):
        """Test data is buffered when MQTT is disconnected"""
        self.mock_mqtt.client.is_connected.return_value = False
        self.telemetry_service.is_connected = False

        self.telemetry_service._generate_data()
        self.telemetry_service._push_data()

        self.mock_db.buffer_telemetry.assert_called()

    def test_buffer_contains_parameter_data(self):
        """Test buffered data contains correct parameter information"""
        self.mock_mqtt.client.is_connected.return_value = False
        self.telemetry_service.is_connected = False

        self.telemetry_service._generate_data()
        self.telemetry_service._push_data()

        call_args = self.mock_db.buffer_telemetry.call_args_list
        self.assertGreater(len(call_args), 0)
        first_call = call_args[0]
        self.assertIn('parameter_id', first_call.kwargs)
        self.assertIn('value', first_call.kwargs)
    
    def test_flush_buffered_data(self):
        """Test flushing buffered data"""
        buffered_data = [
            {'id': 1, 'parameter_id': 'p1', 'value': 25.5, 'timestamp': '2024-01-01T00:00:00'},
            {'id': 2, 'parameter_id': 'p2', 'value': 100.0, 'timestamp': '2024-01-01T00:00:00'}
        ]
        self.mock_db.get_buffered_data.return_value = buffered_data
        self.mock_db.mark_data_synced = Mock()
        self.mock_db.delete_buffered_data = Mock()

        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            self.telemetry_service._flush_buffered_data()

        self.mock_db.delete_buffered_data.assert_called_once()

    def test_delete_buffered_data_after_sync(self):
        """Test buffered data is deleted after successful sync"""
        buffered_data = [
            {'id': 1, 'parameter_id': 'p1', 'value': 25.5, 'timestamp': '2024-01-01T00:00:00'},
            {'id': 2, 'parameter_id': 'p2', 'value': 100.0, 'timestamp': '2024-01-01T00:00:00'}
        ]
        self.mock_db.get_buffered_data.return_value = buffered_data
        self.mock_db.mark_data_synced = Mock()
        self.mock_db.delete_buffered_data = Mock()

        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            self.telemetry_service._flush_buffered_data()

        self.mock_db.delete_buffered_data.assert_called_once()
        call_args = self.mock_db.delete_buffered_data.call_args[0][0]
        self.assertEqual(call_args, [1, 2])


class TestMQTTTelemetrySender(unittest.TestCase):
    """Test MQTT telemetry sender"""
    
    def setUp(self):
        """Setup test fixtures"""
        self.mock_mqtt = Mock()
        self.mock_mqtt.device_id = "test_device_001"
        self.mock_mqtt.is_connected = True
        self.mock_mqtt.telemetry_topic = "telemetry/data"
        self.mock_mqtt.client = Mock()
        
        self.mock_telemetry = Mock()
        self.mock_telemetry.get_parameters.return_value = {
            1: {'id': 1, 'name': 'Temperature', 'value': 25.5, 'unit': '°C'}
        }

        self.mock_db = Mock()
        self.mock_db.store_parameter_stream = Mock(return_value=1)
        
        from src.services.mqtt_telemetry_sender import MQTTTelemetrySender
        self.sender = MQTTTelemetrySender(self.mock_mqtt, self.mock_telemetry, self.mock_db)
    
    def test_mqtt_payload_structure(self):
        """Test MQTT payload has correct structure"""
        self.mock_mqtt.client.publish = Mock(return_value=True)
        
        self.sender._send_mqtt_telemetry()
        
        call_args = self.mock_mqtt.client.publish.call_args
        payload_str = call_args[0][1]
        payload = json.loads(payload_str)
        
        self.assertIn('client_id', payload)
        self.assertIn('timestamp', payload)
        self.assertIn('parameters', payload)
        self.assertEqual(payload['client_id'], 'test_device_001')
    
    def test_mqtt_payload_timestamp_format(self):
        """Test MQTT payload timestamp is ISO8601"""
        self.mock_mqtt.client.publish = Mock(return_value=True)
        
        self.sender._send_mqtt_telemetry()
        
        call_args = self.mock_mqtt.client.publish.call_args
        payload_str = call_args[0][1]
        payload = json.loads(payload_str)
        
        timestamp = payload['timestamp']
        parsed = datetime.fromisoformat(timestamp)
        self.assertIsInstance(parsed, datetime)
    
    def test_mqtt_parameters_in_payload(self):
        """Test parameters are included in MQTT payload"""
        self.mock_mqtt.client.publish = Mock(return_value=True)
        
        self.sender._send_mqtt_telemetry()
        
        call_args = self.mock_mqtt.client.publish.call_args
        payload_str = call_args[0][1]
        payload = json.loads(payload_str)
        
        self.assertEqual(len(payload['parameters']), 1)
        param = payload['parameters'][0]
        self.assertEqual(param['id'], 1)
        self.assertEqual(param['name'], 'Temperature')
        self.assertEqual(param['value'], 25.5)
        self.assertEqual(param['unit'], '°C')


class TestParameterStreamingData(unittest.TestCase):
    """Test ParameterStreamingData class"""
    
    def test_from_parameter_conversion(self):
        """Test converting parameter dict to ParameterStreamingData"""
        from src.services.parameter_streaming_data import ParameterStreamingData
        
        param = {
            'id': 'param_1',
            'name': 'Temperature',
            'value': 25.5,
            'unit': '°C'
        }
        timestamp = datetime.now().isoformat()
        
        streaming_data = ParameterStreamingData.from_parameter(param, 'device_001', timestamp)
        
        self.assertEqual(streaming_data.parameter_id, 'param_1')
        self.assertEqual(streaming_data.name, 'Temperature')
        self.assertEqual(streaming_data.value, 25.5)
        self.assertEqual(streaming_data.unit, '°C')
        self.assertEqual(streaming_data.device_id, 'device_001')
        self.assertEqual(streaming_data.timestamp, timestamp)
    
    def test_to_dict_conversion(self):
        """Test converting ParameterStreamingData to dict"""
        from src.services.parameter_streaming_data import ParameterStreamingData
        
        param = {
            'id': 'param_1',
            'name': 'Temperature',
            'value': 25.5,
            'unit': '°C'
        }
        timestamp = datetime.now().isoformat()
        
        streaming_data = ParameterStreamingData.from_parameter(param, 'device_001', timestamp)
        data_dict = streaming_data.to_dict()
        
        self.assertIsInstance(data_dict, dict)
        self.assertEqual(data_dict['parameter_id'], 'param_1')
        self.assertEqual(data_dict['value'], 25.5)


class TestParameterStreamingPayload(unittest.TestCase):
    """Test ParameterStreamingPayload class"""
    
    def test_payload_creation(self):
        """Test creating ParameterStreamingPayload"""
        from src.services.parameter_streaming_data import ParameterStreamingData, ParameterStreamingPayload
        
        params = [
            ParameterStreamingData(
                parameter_id='p1',
                name='Temp',
                value=25.5,
                unit='°C',
                device_id='device_001',
                timestamp=datetime.now().isoformat()
            )
        ]
        
        payload = ParameterStreamingPayload(
            client_id='device_001',
            timestamp=datetime.now().isoformat(),
            parameters=params
        )
        
        self.assertEqual(payload.client_id, 'device_001')
        self.assertEqual(len(payload.parameters), 1)
    
    def test_payload_to_dict(self):
        """Test converting payload to dict"""
        from src.services.parameter_streaming_data import ParameterStreamingData, ParameterStreamingPayload
        
        timestamp = datetime.now().isoformat()
        params = [
            ParameterStreamingData(
                parameter_id='p1',
                name='Temp',
                value=25.5,
                unit='°C',
                device_id='device_001',
                timestamp=timestamp
            )
        ]
        
        payload = ParameterStreamingPayload(
            client_id='device_001',
            timestamp=timestamp,
            parameters=params
        )
        
        payload_dict = payload.to_dict()
        
        self.assertIn('client_id', payload_dict)
        self.assertIn('timestamp', payload_dict)
        self.assertIn('parameters', payload_dict)
        self.assertEqual(len(payload_dict['parameters']), 1)


if __name__ == '__main__':
    unittest.main()
