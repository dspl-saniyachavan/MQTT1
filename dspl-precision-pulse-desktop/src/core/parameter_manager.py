"""
Parameter Manager for shared parameter state
"""

from PySide6.QtCore import QObject, Signal
from typing import List, Dict


class ParameterManager(QObject):
    """Manages shared parameter state across the application"""
    
    parameters_changed = Signal(list)
    
    def __init__(self):
        super().__init__()
        self._parameters = self._get_default_parameters()
    
    def _get_default_parameters(self) -> List[Dict]:
        """Get default parameters"""
        return [
            {'id': 'temp', 'name': 'Temperature', 'unit': '°C', 'enabled': True, 'description': 'Ambient temperature sensor'},
            {'id': 'pressure', 'name': 'Pressure', 'unit': 'kPa', 'enabled': True, 'description': 'System pressure measurement'},
            {'id': 'flow', 'name': 'Flow Rate', 'unit': 'L/s', 'enabled': False, 'description': 'Liquid flow rate'},
            {'id': 'humidity', 'name': 'Humidity', 'unit': '%', 'enabled': True, 'description': 'Relative humidity'},
            {'id': 'voltage', 'name': 'Voltage', 'unit': 'V', 'enabled': True, 'description': 'System voltage'},
            {'id': 'custom', 'name': 'custom', 'unit': 'l/s', 'enabled': True, 'description': 'd'},
        ]
    
    def get_parameters(self) -> List[Dict]:
        """Get all parameters"""
        return self._parameters
    
    def get_enabled_parameters(self) -> List[Dict]:
        """Get only enabled parameters"""
        return [p for p in self._parameters if p['enabled']]
    
    def update_parameters(self, parameters: List[Dict]):
        """Update parameters and emit signal"""
        self._parameters = parameters
        self.parameters_changed.emit(self._parameters)
    
    def toggle_parameter(self, index: int):
        """Toggle parameter enabled state"""
        if 0 <= index < len(self._parameters):
            self._parameters[index]['enabled'] = not self._parameters[index]['enabled']
            self.parameters_changed.emit(self._parameters)
    
    def add_parameter(self, param: Dict):
        """Add new parameter"""
        self._parameters.append(param)
        self.parameters_changed.emit(self._parameters)
    
    def remove_parameter(self, index: int):
        """Remove parameter"""
        if 0 <= index < len(self._parameters):
            self._parameters.pop(index)
            self.parameters_changed.emit(self._parameters)
