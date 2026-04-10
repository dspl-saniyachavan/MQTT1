"""
MQTT event handlers for configuration updates.
Receives real-time config changes from backend via MQTT and persists them to SQLite.
Topics: precisionpulse/config/update  (single key)
        precisionpulse/config/bulk-update  (all keys)
"""


def setup_config_handlers(mqtt_service, config_service):
    """Wire MQTT config topics to ConfigurationService."""

    def _persist(key, value, category='general', data_type='string', version=1, updated_at=None):
        try:
            import sqlite3
            conn = sqlite3.connect(config_service.db.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO config (key, value, category, data_type, version, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (key, str(value), category, data_type, version, updated_at))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[CONFIG_MQTT] SQLite persist error for {key}: {e}")

    def _on_mqtt_message(topic: str, payload: dict):
        try:
            if 'config/update' in topic and 'bulk' not in topic:
                key       = payload.get('key')
                value     = payload.get('value')
                action    = payload.get('action')
                version   = payload.get('version', 1)
                category  = payload.get('category', 'general')
                data_type = payload.get('data_type', 'string')
                updated_at = payload.get('timestamp')

                if not key:
                    return

                old_value = config_service.local_config.get(key, {}).get('value')

                if action == 'deleted':
                    config_service.local_config.pop(key, None)
                    try:
                        import sqlite3
                        conn = sqlite3.connect(config_service.db.db_path)
                        conn.execute('DELETE FROM config WHERE key = ?', (key,))
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        print(f"[CONFIG_MQTT] SQLite delete error for {key}: {e}")
                    print(f"[CONFIG_MQTT] Deleted: {key}")
                    return

                config_service.local_config[key] = {
                    'key': key, 'value': str(value),
                    'category': category, 'data_type': data_type,
                    'version': version, 'updated_at': updated_at
                }
                _persist(key, value, category, data_type, version, updated_at)
                print(f"[CONFIG_MQTT] Updated: {key} = {value} (was {old_value}, v{version})")

                if version:
                    config_service.config_version = version

                config_service.apply_config_change(key, value, old_value)

            elif 'config/bulk-update' in topic:
                configs        = payload.get('configs', [])
                global_version = payload.get('global_version', 1)
                timestamp      = payload.get('timestamp')

                for cfg in configs:
                    key       = cfg.get('key')
                    value     = cfg.get('value')
                    category  = cfg.get('category', 'general')
                    data_type = cfg.get('data_type', 'string')
                    version   = cfg.get('version', global_version)

                    if not key:
                        continue

                    old_value = config_service.local_config.get(key, {}).get('value')
                    config_service.local_config[key] = {
                        'key': key, 'value': str(value),
                        'category': category, 'data_type': data_type,
                        'version': version, 'updated_at': timestamp
                    }
                    _persist(key, value, category, data_type, version, timestamp)
                    config_service.apply_config_change(key, value, old_value)
                    print(f"[CONFIG_MQTT] Bulk updated: {key} = {value}")

                if global_version:
                    config_service.config_version = global_version
                print(f"[CONFIG_MQTT] Bulk update done (v{global_version})")

        except Exception as e:
            print(f"[CONFIG_MQTT] Error handling message on {topic}: {e}")

    mqtt_service.message_received.connect(_on_mqtt_message)
    print("[CONFIG_MQTT] Handlers registered on MQTT")
