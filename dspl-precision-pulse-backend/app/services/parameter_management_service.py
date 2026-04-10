"""
Parameter management service with validation, history, and alerts
"""
import logging
from datetime import datetime, timezone, timezone
from typing import Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)

_PARAM_NOT_FOUND = _PARAM_NOT_FOUND

class ParameterType(Enum):
    """Parameter data types"""
    INTEGER = 'integer'
    FLOAT = 'float'
    STRING = 'string'
    BOOLEAN = 'boolean'
    ENUM = 'enum'

class ParameterValidator:
    """Validates parameter values"""
    
    @staticmethod
    def validate(value, param_type: ParameterType, min_val=None, max_val=None, allowed_values=None) -> Tuple[bool, Optional[str]]:
        """Validate parameter value"""
        try:
            if param_type == ParameterType.INTEGER:
                val = int(value)
                if min_val is not None and val < min_val:
                    return False, f"Value {val} is less than minimum {min_val}"
                if max_val is not None and val > max_val:
                    return False, f"Value {val} is greater than maximum {max_val}"
            
            elif param_type == ParameterType.FLOAT:
                val = float(value)
                if min_val is not None and val < min_val:
                    return False, f"Value {val} is less than minimum {min_val}"
                if max_val is not None and val > max_val:
                    return False, f"Value {val} is greater than maximum {max_val}"
            
            elif param_type == ParameterType.STRING:
                if max_val is not None and len(str(value)) > max_val:
                    return False, f"String length {len(value)} exceeds maximum {max_val}"
            
            elif param_type == ParameterType.BOOLEAN:
                if not isinstance(value, bool):
                    return False, "Value must be boolean"
            
            elif param_type == ParameterType.ENUM:
                if allowed_values and value not in allowed_values:
                    return False, f"Value {value} not in allowed values: {allowed_values}"
            
            return True, None
        except Exception as e:
            return False, str(e)

class ParameterHistory:
    """Tracks parameter value changes"""
    
    def __init__(self, param_id: int, param_name: str):
        self.param_id = param_id
        self.param_name = param_name
        self.changes = []
    
    def record_change(self, old_value, new_value, changed_by: str):
        """Record a parameter change"""
        change = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'old_value': old_value,
            'new_value': new_value,
            'changed_by': changed_by
        }
        self.changes.append(change)
        logger.info(f"[PARAM_HISTORY] {self.param_name}: {old_value} -> {new_value} by {changed_by}")
    
    def get_changes(self, limit: int = 100) -> List[dict]:
        """Get recent changes"""
        return self.changes[-limit:]
    
    def get_change_count(self) -> int:
        """Get total number of changes"""
        return len(self.changes)

class ParameterAlert:
    """Manages parameter value alerts"""
    
    def __init__(self, param_id: int, param_name: str, threshold: float, condition: str):
        self.param_id = param_id
        self.param_name = param_name
        self.threshold = threshold
        self.condition = condition  # 'greater_than', 'less_than', 'equals'
        self.triggered = False
        self.last_triggered = None
    
    def check_value(self, value: float) -> bool:
        """Check if alert should trigger"""
        try:
            val = float(value)
            
            if self.condition == 'greater_than':
                triggered = val > self.threshold
            elif self.condition == 'less_than':
                triggered = val < self.threshold
            elif self.condition == 'equals':
                triggered = val == self.threshold
            else:
                return False
            
            if triggered and not self.triggered:
                self.triggered = True
                self.last_triggered = datetime.now(timezone.utc)
                logger.warning(f"[PARAM_ALERT] Alert triggered for {self.param_name}: {value} {self.condition} {self.threshold}")
                return True
            elif not triggered:
                self.triggered = False
            
            return False
        except Exception as e:
            logger.error(f"[PARAM_ALERT] Error checking alert: {e}")
            return False

class ParameterManagementService:
    """Manages parameters with validation, history, and alerts"""
    
    def __init__(self):
        self.parameters = {}
        self.histories = {}
        self.alerts = {}
    
    def create_parameter(self, param_id: int, name: str, param_type: ParameterType, 
                        value, min_val=None, max_val=None, allowed_values=None) -> Tuple[bool, Optional[str]]:
        """Create a new parameter"""
        try:
            # Validate value
            valid, error = ParameterValidator.validate(value, param_type, min_val, max_val, allowed_values)
            if not valid:
                return False, error
            
            self.parameters[param_id] = {
                'id': param_id,
                'name': name,
                'type': param_type.value,
                'value': value,
                'min': min_val,
                'max': max_val,
                'allowed_values': allowed_values,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Initialize history
            self.histories[param_id] = ParameterHistory(param_id, name)
            
            logger.info(f"[PARAM_MGMT] Created parameter {name} (id={param_id})")
            return True, None
        except Exception as e:
            return False, str(e)
    
    def update_parameter(self, param_id: int, value, changed_by: str) -> Tuple[bool, Optional[str]]:
        """Update parameter value"""
        try:
            if param_id not in self.parameters:
                return False, "Parameter not found"
            
            param = self.parameters[param_id]
            param_type = ParameterType(param['type'])
            
            # Validate new value
            valid, error = ParameterValidator.validate(
                value, param_type, param['min'], param['max'], param['allowed_values']
            )
            if not valid:
                return False, error
            
            # Record history
            old_value = param['value']
            self.histories[param_id].record_change(old_value, value, changed_by)
            
            # Update value
            param['value'] = value
            param['updated_at'] = datetime.now(timezone.utc).isoformat()
            
            # Check alerts
            if param_id in self.alerts:
                for alert in self.alerts[param_id]:
                    alert.check_value(value)
            
            logger.info(f"[PARAM_MGMT] Updated parameter {param['name']} to {value}")
            return True, None
        except Exception as e:
            return False, str(e)
    
    def delete_parameter(self, param_id: int) -> Tuple[bool, Optional[str]]:
        """Delete a parameter"""
        try:
            if param_id not in self.parameters:
                return False, "Parameter not found"
            
            param = self.parameters[param_id]
            del self.parameters[param_id]
            
            if param_id in self.histories:
                del self.histories[param_id]
            
            if param_id in self.alerts:
                del self.alerts[param_id]
            
            logger.info(f"[PARAM_MGMT] Deleted parameter {param['name']}")
            return True, None
        except Exception as e:
            return False, str(e)
    
    def get_parameter(self, param_id: int) -> Optional[dict]:
        """Get parameter by ID"""
        return self.parameters.get(param_id)
    
    def get_all_parameters(self) -> List[dict]:
        """Get all parameters"""
        return list(self.parameters.values())
    
    def add_alert(self, param_id: int, threshold: float, condition: str) -> Tuple[bool, Optional[str]]:
        """Add alert for parameter"""
        try:
            if param_id not in self.parameters:
                return False, "Parameter not found"
            
            param = self.parameters[param_id]
            alert = ParameterAlert(param_id, param['name'], threshold, condition)
            
            if param_id not in self.alerts:
                self.alerts[param_id] = []
            
            self.alerts[param_id].append(alert)
            logger.info(f"[PARAM_MGMT] Added alert for {param['name']}: {condition} {threshold}")
            return True, None
        except Exception as e:
            return False, str(e)
    
    def get_parameter_history(self, param_id: int, limit: int = 100) -> Optional[List[dict]]:
        """Get parameter change history"""
        if param_id not in self.histories:
            return None
        return self.histories[param_id].get_changes(limit)
    
    def get_parameter_stats(self, param_id: int) -> Optional[dict]:
        """Get parameter statistics"""
        if param_id not in self.parameters:
            return None
        
        param = self.parameters[param_id]
        history = self.histories.get(param_id)
        
        return {
            'id': param_id,
            'name': param['name'],
            'current_value': param['value'],
            'change_count': history.get_change_count() if history else 0,
            'created_at': param['created_at'],
            'updated_at': param['updated_at']
        }


# Global instance
_param_mgmt_service = None

def get_parameter_management_service() -> ParameterManagementService:
    """Get or create parameter management service"""
    global _param_mgmt_service
    if _param_mgmt_service is None:
        _param_mgmt_service = ParameterManagementService()
    return _param_mgmt_service
