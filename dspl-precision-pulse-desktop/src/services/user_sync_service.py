"""
User synchronization service for desktop application
Handles user, role, and permission changes from backend via MQTT
"""

from typing import List, Dict, Optional
from PySide6.QtCore import QObject, Signal
import hmac
import hashlib
import json
import os
import logging

logger = logging.getLogger(__name__)

MQTT_SIGNING_SECRET = os.environ.get('MQTT_SIGNING_SECRET', 'precisionpulse-default-secret')


def _verify_payload_signature(payload: dict) -> bool:
    """Verify HMAC-SHA256 signature on incoming MQTT payload"""
    sig = payload.get('_sig')
    if not sig:
        # Allow unsigned payloads in development; log a warning
        logger.warning("[USER_SYNC] Received unsigned MQTT payload")
        return True
    unsigned = {k: v for k, v in payload.items() if k != '_sig'}
    expected = hmac.new(
        MQTT_SIGNING_SECRET.encode('utf-8'),
        json.dumps(unsigned, sort_keys=True).encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    valid = hmac.compare_digest(sig, expected)
    if not valid:
        logger.error("[USER_SYNC] Payload signature verification FAILED")
    return valid


class UserSyncService(QObject):
    """Service for syncing user, role, and permission changes from backend via MQTT"""
    
    user_created = Signal(dict)
    user_updated = Signal(dict)
    user_deleted = Signal(int, str)  # user_id, email
    role_changed = Signal(int, str, str, str)  # user_id, email, old_role, new_role
    permission_changed = Signal(str, list)  # role, permissions
    sync_error = Signal(str)
    
    def __init__(self, mqtt_service=None, database_manager=None):
        super().__init__()
        self.mqtt_service = mqtt_service
        self.database_manager = database_manager
        self.users = []
        self.permissions = {}
        
        # Connect to MQTT message signals
        if mqtt_service:
            mqtt_service.message_received.connect(self._on_mqtt_message)
    
    def _on_mqtt_message(self, topic: str, payload: dict):
        """Handle MQTT user sync messages — decrypt if encrypted"""
        try:
            # Decrypt if payload is encrypted
            if '_enc' in payload:
                try:
                    from src.core.encryption import decrypt_payload
                    payload = decrypt_payload(payload['_enc'])
                except Exception as dec_err:
                    logger.error(f"[USER_SYNC] Decryption failed: {dec_err}")
                    return
            elif not _verify_payload_signature(payload):
                logger.error(f"[USER_SYNC] Dropping message on {topic}: invalid signature")
                return

            msg_type = payload.get('type')
            print(f"[USER_SYNC] Received message on {topic}: type={msg_type}")

            if 'sync/users/created' in topic or msg_type == 'user_created':
                user = payload.get('user', {})
                self.users.append(user)
                logger.info(f"[USER_SYNC] User created: {user.get('email')}")
                if self.database_manager:
                    self._sync_user_to_db(user)
                self.user_created.emit(user)

            elif 'sync/users/updated' in topic or msg_type == 'user_updated':
                user = payload.get('user', {})
                for i, u in enumerate(self.users):
                    if u.get('id') == user.get('id'):
                        self.users[i] = user
                        break
                logger.info(f"[USER_SYNC] User updated: {user.get('email')}")
                if self.database_manager:
                    self._sync_user_to_db(user)
                self.user_updated.emit(user)

            elif 'sync/users/deleted' in topic or msg_type == 'user_deleted':
                user = payload.get('user', {})
                user_id = user.get('id')
                email = user.get('email')
                self.users = [u for u in self.users if u.get('id') != user_id]
                logger.info(f"[USER_SYNC] User deleted: {email}")
                if self.database_manager:
                    self._delete_user_from_db(email)
                self.user_deleted.emit(user_id, email)

            elif 'sync/roles/changed' in topic or msg_type == 'role_changed':
                user_id = payload.get('user_id')
                email = payload.get('email')
                old_role = payload.get('old_role')
                new_role = payload.get('new_role')
                print(f"[USER_SYNC] Role change detected: {email} {old_role} -> {new_role}")
                for u in self.users:
                    if u.get('id') == user_id:
                        u['role'] = new_role
                        break
                logger.info(f"[USER_SYNC] Role changed for {email}: {old_role} -> {new_role}")
                if self.database_manager:
                    self._update_user_role_in_db(user_id, new_role)
                self.role_changed.emit(user_id, email, old_role, new_role)

            elif 'sync/permissions/changed' in topic or msg_type == 'permission_changed':
                role = payload.get('role')
                permissions = payload.get('permissions', [])
                self.permissions[role] = permissions
                if self.database_manager:
                    self._sync_permissions_to_db(role, permissions)
                self.permission_changed.emit(role, permissions)

        except Exception as e:
            logger.error(f"[USER_SYNC] Error processing message: {e}")
            self.sync_error.emit(str(e))
    
    def _sync_user_to_db(self, user: Dict) -> bool:
        """Sync user to local SQLite — stores password_hash if provided (credential mirroring)"""
        try:
            import sqlite3
            with sqlite3.connect(self.database_manager.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT id FROM users WHERE email = ? OR id = ?',
                               (user.get('email'), user.get('id')))
                existing = cursor.fetchone()
                password_hash = user.get('password_hash', '')
                if existing:
                    if password_hash:
                        cursor.execute('''
                            UPDATE users SET name=?, email=?, role=?, is_active=?,
                                password_hash=?, updated_at=datetime('now','localtime')
                            WHERE id=?
                        ''', (user.get('name'), user.get('email'), user.get('role','user'),
                              1 if user.get('is_active', True) else 0, password_hash, user.get('id')))
                    else:
                        cursor.execute('''
                            UPDATE users SET name=?, email=?, role=?, is_active=?,
                                updated_at=datetime('now','localtime')
                            WHERE id=?
                        ''', (user.get('name'), user.get('email'), user.get('role','user'),
                              1 if user.get('is_active', True) else 0, user.get('id')))
                else:
                    cursor.execute('''
                        INSERT INTO users (id, email, name, password_hash, role, is_active, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, datetime('now','localtime'))
                    ''', (user.get('id'), user.get('email'), user.get('name'),
                          password_hash, user.get('role','user'),
                          1 if user.get('is_active', True) else 0))
                conn.commit()
                logger.info(f"[USER_SYNC] Synced user {user.get('email')} to SQLite")
                return True
        except Exception as e:
            logger.error(f"[USER_SYNC] Error syncing user to database: {e}")
            return False
    
    def _delete_user_from_db(self, email: str) -> bool:
        """Delete user from local SQLite database"""
        try:
            import sqlite3
            
            with sqlite3.connect(self.database_manager.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM users WHERE email = ?', (email,))
                conn.commit()
                logger.info(f"[USER_SYNC] Deleted user {email} from local database")
                return True
        
        except Exception as e:
            logger.error(f"[USER_SYNC] Error deleting user from database: {e}")
            return False
    
    def _update_user_role_in_db(self, user_id: int, new_role: str) -> bool:
        """Update user role in local SQLite database"""
        try:
            import sqlite3
            
            with sqlite3.connect(self.database_manager.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users SET role = ?, updated_at = datetime('now', 'localtime')
                    WHERE id = ?
                ''', (new_role, user_id))
                conn.commit()
                logger.info(f"[USER_SYNC] Updated user {user_id} role to {new_role}")
                return True
        
        except Exception as e:
            logger.error(f"[USER_SYNC] Error updating user role: {e}")
            return False
    
    def _sync_permissions_to_db(self, role: str, permissions: List[Dict]) -> bool:
        """Sync permissions to local SQLite database"""
        try:
            import sqlite3
            
            with sqlite3.connect(self.database_manager.db_path) as conn:
                cursor = conn.cursor()
                
                # Clear existing permissions for this role
                cursor.execute('DELETE FROM permissions WHERE role = ?', (role,))
                
                # Insert new permissions
                for perm in permissions:
                    cursor.execute('''
                        INSERT INTO permissions (role, resource, action, allowed)
                        VALUES (?, ?, ?, ?)
                    ''', (
                        role,
                        perm.get('resource'),
                        perm.get('action'),
                        1 if perm.get('allowed', True) else 0
                    ))
                
                conn.commit()
                logger.info(f"[USER_SYNC] Synced {len(permissions)} permissions for role {role}")
                return True
        
        except Exception as e:
            logger.error(f"[USER_SYNC] Error syncing permissions: {e}")
            return False
    
    def get_users(self) -> List[Dict]:
        """Get all synced users"""
        return self.users
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        for u in self.users:
            if u.get('id') == user_id:
                return u
        return None
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email"""
        for u in self.users:
            if u.get('email') == email:
                return u
        return None
    
    def get_permissions(self, role: str) -> List[Dict]:
        """Get permissions for a role"""
        return self.permissions.get(role, [])
    
    def has_permission(self, role: str, resource: str, action: str) -> bool:
        """Check if role has permission"""
        permissions = self.get_permissions(role)
        for perm in permissions:
            if perm.get('resource') == resource and perm.get('action') == action:
                return perm.get('allowed', False)
        return False
    
    def publish(self, topic: str, payload: dict):
        """Encrypt and publish any payload to an MQTT topic."""
        if not self.mqtt_service or not self.mqtt_service.is_connected:
            logger.warning('[USER_SYNC] MQTT not connected — cannot publish to %s', topic)
            return False
        try:
            from src.core.encryption import encrypt_payload
            import json
            try:
                msg = {'_enc': encrypt_payload(payload), 'type': payload.get('type', '')}
            except Exception:
                msg = payload
            self.mqtt_service.client.publish(topic, json.dumps(msg), qos=1)
            return True
        except Exception as e:
            logger.error('[USER_SYNC] publish error on %s: %s', topic, e)
            return False

    def publish_user_change(self, action: str, user_data: dict):
        """Publish a user create/update/delete to MQTT so the backend subscriber writes to PostgreSQL."""
        if not self.mqtt_service or not self.mqtt_service.is_connected:
            logger.warning('[USER_SYNC] MQTT not connected — cannot publish user change')
            return
        try:
            from src.core.encryption import encrypt_payload
            import uuid
            from datetime import datetime

            type_map = {'create': 'user_created', 'update': 'user_updated', 'delete': 'user_deleted'}
            topic_map = {
                'create': 'precisionpulse/sync/users/created',
                'update': 'precisionpulse/sync/users/updated',
                'delete': 'precisionpulse/sync/users/deleted',
            }
            msg_type = type_map.get(action, f'user_{action}')
            topic    = topic_map.get(action, f'precisionpulse/sync/users/{action}')

            payload = {
                'type': msg_type,
                'msg_id': str(uuid.uuid4()),
                'timestamp': datetime.now().isoformat(),
                'user': user_data,
            }
            try:
                encrypted = {'_enc': encrypt_payload(payload), 'type': msg_type}
            except Exception:
                encrypted = payload

            import json
            self.mqtt_service.client.publish(topic, json.dumps(encrypted), qos=1)
            logger.info('[USER_SYNC] Published %s for %s', msg_type, user_data.get('email'))
        except Exception as e:
            logger.error('[USER_SYNC] publish_user_change error: %s', e)
