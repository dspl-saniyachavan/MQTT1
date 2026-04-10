"""
Parameter streaming data models for telemetry
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Any
from datetime import datetime


@dataclass
class ParameterStreamingData:
    """Individual parameter streaming data"""
    parameter_id: int
    name: str
    value: float
    unit: str
    timestamp: str
    device_id: str
    
    @classmethod
    def from_parameter(cls, param: Dict, device_id: str, timestamp: str) -> 'ParameterStreamingData':
        """Create from parameter dict"""
        return cls(
            parameter_id=param.get('id'),
            name=param.get('name'),
            value=param.get('value', 0),
            unit=param.get('unit', ''),
            timestamp=timestamp,
            device_id=device_id
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class ParameterStreamingPayload:
    """Telemetry payload containing multiple parameters"""
    client_id: str
    timestamp: str
    parameters: List[ParameterStreamingData]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'client_id': self.client_id,
            'timestamp': self.timestamp,
            'parameters': [p.to_dict() for p in self.parameters]
        }
