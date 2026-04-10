"""
System Configuration Manager Service
Handles fetching, caching, and providing system configuration values
"""

from app.models.system_config import SystemConfig
from app.models import db
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages system configuration with caching"""
    
    def __init__(self, cache_ttl_seconds=300):
        """
        Initialize config manager
        
        Args:
            cache_ttl_seconds: Cache time-to-live in seconds (default 5 minutes)
        """
        self.cache = {}
        self.cache_ttl = cache_ttl_seconds
        self.cache_timestamps = {}
    
    def _is_cache_valid(self, key):
        """Check if cached value is still valid"""
        if key not in self.cache_timestamps:
            return False
        
        age = (datetime.now(timezone.utc) - self.cache_timestamps[key]).total_seconds()
        return age < self.cache_ttl
    
    def get_config(self, key, default=None, use_cache=True):
        try:
            if use_cache and self._is_cache_valid(key):
                logger.debug(f"[CONFIG_MGR] Cache hit for {key}")
                return self.cache[key]

            try:
                from flask import current_app
                # If we are inside an active app context this is a no-op;
                # if not, push one so the DB query works from background threads.
                ctx = None
                try:
                    current_app._get_current_object()  # raises if no context
                except RuntimeError:
                    from app import create_app
                    _app = getattr(self, '_app', None)
                    if _app is None:
                        logger.warning(f"[CONFIG_MGR] No app context for {key}, returning default")
                        return default
                    ctx = _app.app_context()
                    ctx.push()

                try:
                    config = SystemConfig.query.filter_by(key=key).first()
                finally:
                    if ctx:
                        ctx.pop()
            except Exception as db_error:
                logger.warning(f"[CONFIG_MGR] Database query error for {key}: {db_error}, using default: {default}")
                return default

            if not config:
                logger.debug(f"[CONFIG_MGR] Configuration not found: {key}, using default: {default}")
                return default

            typed_value = config.get_typed_value()
            self.cache[key] = typed_value
            self.cache_timestamps[key] = datetime.now(timezone.utc)
            logger.debug(f"[CONFIG_MGR] Fetched {key} = {typed_value} (type: {config.data_type})")
            return typed_value

        except Exception as e:
            logger.warning(f"[CONFIG_MGR] Error fetching config {key}: {e}, using default: {default}")
            return default
    
    def get_all_configs(self, category=None, use_cache=True):
        """
        Get all configurations, optionally filtered by category
        
        Args:
            category: Optional category filter
            use_cache: Whether to use cached values
        
        Returns:
            Dictionary of key-value pairs
        """
        try:
            cache_key = f"all_configs_{category or 'all'}"
            
            # Check cache first
            if use_cache and self._is_cache_valid(cache_key):
                logger.debug("[CONFIG_MGR] Cache hit for all configs")
                return self.cache[cache_key]
            
            # Query database with error handling
            try:
                query = SystemConfig.query
                if category:
                    query = query.filter_by(category=category)
                
                configs = query.all()
            except Exception as db_error:
                logger.warning(f"[CONFIG_MGR] Database query error: {db_error}")
                return {}
            
            # Build result dictionary
            result = {}
            for config in configs:
                try:
                    result[config.key] = config.get_typed_value()
                except Exception as e:
                    logger.warning(f"[CONFIG_MGR] Error getting typed value for {config.key}: {e}")
                    result[config.key] = config.value
            
            # Cache the result
            self.cache[cache_key] = result
            self.cache_timestamps[cache_key] = datetime.now(timezone.utc)
            
            logger.debug(f"[CONFIG_MGR] Fetched {len(result)} configs")
            return result
        
        except Exception as e:
            logger.warning(f"[CONFIG_MGR] Error fetching all configs: {e}")
            return {}
    
    def invalidate_cache(self, key=None):
        """
        Invalidate cache for a specific key or all keys
        
        Args:
            key: Specific key to invalidate, or None to invalidate all
        """
        try:
            if key:
                if key in self.cache:
                    del self.cache[key]
                if key in self.cache_timestamps:
                    del self.cache_timestamps[key]
                logger.debug(f"[CONFIG_MGR] Invalidated cache for {key}")
            else:
                self.cache.clear()
                self.cache_timestamps.clear()
                logger.debug("[CONFIG_MGR] Invalidated all cache")
        except Exception as e:
            logger.warning(f"[CONFIG_MGR] Error invalidating cache: {e}")
    
    def get_mqtt_config(self):
        """Get MQTT-related configurations"""
        try:
            return {
                'broker':      self.get_config('MQTT_BROKER', 'localhost'),
                'keep_alive':  self.get_config('MQTT_KEEP_ALIVE', 60),
            }
        except Exception as e:
            logger.warning(f"[CONFIG_MGR] Error getting MQTT config: {e}")
            return {
                'broker': 'localhost',
                'keep_alive': 60,
            }

    def get_telemetry_config(self):
        """Get telemetry-related configurations"""
        try:
            return {
                'fetch_interval_ms':     self.get_config('TELEMETRY_FETCH_INTERVAL_MS', 3000),
                'max_chart_data_points': self.get_config('MAX_CHART_DATA_POINTS', 50),
                'retention_days':        self.get_config('TELEMETRY_RETENTION_DAYS', 30),
            }
        except Exception as e:
            logger.warning(f"[CONFIG_MGR] Error getting telemetry config: {e}")
            return {
                'fetch_interval_ms': 3000,
                'max_chart_data_points': 50,
                'retention_days': 30,
            }

    def on_config_updated(self, key: str):
        """Invalidate cache for a key so the next read fetches fresh DB value."""
        try:
            self.invalidate_cache(key)
            logger.info(f"[CONFIG_MGR] Cache invalidated for {key}")
        except Exception as e:
            logger.warning(f"[CONFIG_MGR] Error invalidating cache for {key}: {e}")


# Global instance
_config_manager = None


def get_config_manager():
    """Get global config manager instance (must be initialized via init_config_manager first)"""
    global _config_manager
    if _config_manager is None:
        # Fallback: bare instance with no app context (background threads before init)
        logger.warning("[CONFIG_MGR] get_config_manager called before init_config_manager")
        _config_manager = ConfigManager()
    return _config_manager


def init_config_manager(app):
    """Initialize config manager with Flask app"""
    global _config_manager
    try:
        if _config_manager is None:
            _config_manager = ConfigManager()
        _config_manager._app = app  # store for background-thread context pushes
        app.config_manager = _config_manager
        logger.info("[CONFIG_MGR] Config manager initialized")
    except Exception as e:
        logger.warning(f"[CONFIG_MGR] Error initializing config manager: {e}")
        if _config_manager is None:
            _config_manager = ConfigManager()
