"""
Configuration versioning and rollback service
"""
import logging
import json
from datetime import datetime, timezone, timezone
from typing import Dict, List, Optional
import hashlib

logger = logging.getLogger(__name__)

class ConfigVersion:
    """Represents a configuration version"""
    
    def __init__(self, version_id: int, config: dict, created_by: str, description: str = None):
        self.version_id = version_id
        self.config = config
        self.created_by = created_by
        self.description = description
        self.created_at = datetime.now(timezone.utc)
        self.checksum = self._calculate_checksum()
    
    def _calculate_checksum(self) -> str:
        """Calculate checksum of config"""
        config_str = json.dumps(self.config, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()
    
    def to_dict(self) -> dict:
        return {
            'version_id': self.version_id,
            'config': self.config,
            'created_by': self.created_by,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'checksum': self.checksum
        }

class ConfigTemplate:
    """Configuration template for quick setup"""
    
    def __init__(self, name: str, description: str, config: dict):
        self.name = name
        self.description = description
        self.config = config
        self.created_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'description': self.description,
            'config': self.config,
            'created_at': self.created_at.isoformat()
        }

class ConfigVersioningService:
    """Manages configuration versions and rollback"""
    
    def __init__(self):
        self.versions: Dict[int, ConfigVersion] = {}
        self.templates: Dict[str, ConfigTemplate] = {}
        self.current_version = None
        self.version_counter = 0
    
    def save_version(self, config: dict, created_by: str, description: str = None) -> int:
        """Save a new configuration version"""
        try:
            self.version_counter += 1
            version = ConfigVersion(self.version_counter, config, created_by, description)
            self.versions[self.version_counter] = version
            self.current_version = self.version_counter
            
            logger.info(f"[CONFIG_VERSION] Saved version {self.version_counter} by {created_by}")
            return self.version_counter
        except Exception as e:
            logger.error(f"[CONFIG_VERSION] Error saving version: {e}")
            return -1
    
    def get_version(self, version_id: int) -> Optional[ConfigVersion]:
        """Get specific configuration version"""
        return self.versions.get(version_id)
    
    def get_current_version(self) -> Optional[ConfigVersion]:
        """Get current configuration version"""
        if self.current_version:
            return self.versions.get(self.current_version)
        return None
    
    def get_all_versions(self) -> List[dict]:
        """Get all configuration versions"""
        return [v.to_dict() for v in sorted(self.versions.values(), key=lambda x: x.version_id, reverse=True)]
    
    def rollback_to_version(self, version_id: int) -> tuple[bool, Optional[str]]:
        """Rollback to specific version"""
        try:
            if version_id not in self.versions:
                return False, "Version not found"
            
            version = self.versions[version_id]
            self.current_version = version_id
            
            logger.info(f"[CONFIG_VERSION] Rolled back to version {version_id}")
            return True, None
        except Exception as e:
            logger.error(f"[CONFIG_VERSION] Error rolling back: {e}")
            return False, str(e)
    
    def validate_config(self, config: dict) -> tuple[bool, Optional[str]]:
        """Validate configuration"""
        try:
            if not isinstance(config, dict):
                return False, "Config must be a dictionary"
            
            # Add custom validation rules here
            required_keys = ['mqtt', 'database', 'api']
            for key in required_keys:
                if key not in config:
                    return False, f"Missing required key: {key}"
            
            return True, None
        except Exception as e:
            return False, str(e)
    
    def create_template(self, name: str, description: str, config: dict) -> tuple[bool, Optional[str]]:
        """Create configuration template"""
        try:
            # Validate config
            valid, error = self.validate_config(config)
            if not valid:
                return False, error
            
            template = ConfigTemplate(name, description, config)
            self.templates[name] = template
            
            logger.info(f"[CONFIG_VERSION] Created template {name}")
            return True, None
        except Exception as e:
            logger.error(f"[CONFIG_VERSION] Error creating template: {e}")
            return False, str(e)
    
    def get_template(self, name: str) -> Optional[ConfigTemplate]:
        """Get configuration template"""
        return self.templates.get(name)
    
    def get_all_templates(self) -> List[dict]:
        """Get all templates"""
        return [t.to_dict() for t in self.templates.values()]
    
    def apply_template(self, template_name: str, created_by: str) -> tuple[bool, Optional[str]]:
        """Apply template as new version"""
        try:
            template = self.get_template(template_name)
            if not template:
                return False, "Template not found"
            
            version_id = self.save_version(
                template.config,
                created_by,
                f"Applied template: {template_name}"
            )
            
            logger.info(f"[CONFIG_VERSION] Applied template {template_name} as version {version_id}")
            return True, None
        except Exception as e:
            logger.error(f"[CONFIG_VERSION] Error applying template: {e}")
            return False, str(e)
    
    def compare_versions(self, version_id1: int, version_id2: int) -> Optional[dict]:
        """Compare two configuration versions"""
        try:
            v1 = self.get_version(version_id1)
            v2 = self.get_version(version_id2)
            
            if not v1 or not v2:
                return None
            
            differences = {
                'added': {},
                'removed': {},
                'modified': {}
            }
            
            # Find added and modified
            for key, value in v2.config.items():
                if key not in v1.config:
                    differences['added'][key] = value
                elif v1.config[key] != value:
                    differences['modified'][key] = {
                        'old': v1.config[key],
                        'new': value
                    }
            
            # Find removed
            for key, value in v1.config.items():
                if key not in v2.config:
                    differences['removed'][key] = value
            
            return differences
        except Exception as e:
            logger.error(f"[CONFIG_VERSION] Error comparing versions: {e}")
            return None


# Global instance
_config_versioning_service = None

def get_config_versioning_service() -> ConfigVersioningService:
    """Get or create config versioning service"""
    global _config_versioning_service
    if _config_versioning_service is None:
        _config_versioning_service = ConfigVersioningService()
    return _config_versioning_service
