"""
Database manager for local SQLite operations
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional
from argon2 import PasswordHasher
import bcrypt
from src.core.config import Config

# SQL constants — defined once to avoid duplication across methods
_SQL_PRAGMA_CONFIG = 'PRAGMA table_info(config)'
_SQL_ADD_CATEGORY  = 'ALTER TABLE config ADD COLUMN category TEXT DEFAULT "general"'
_SQL_ADD_DATA_TYPE = 'ALTER TABLE config ADD COLUMN data_type TEXT DEFAULT "string"'
_SQL_ADD_VERSION   = 'ALTER TABLE config ADD COLUMN version INTEGER DEFAULT 1'
_SQL_ADD_CREATED_AT = 'ALTER TABLE config ADD COLUMN created_at TIMESTAMP DEFAULT (datetime("now", "localtime"))'
_SQL_ADD_UPDATED_AT = 'ALTER TABLE config ADD COLUMN updated_at TIMESTAMP DEFAULT (datetime("now", "localtime"))'
_SQL_ADD_UPDATED_BY = 'ALTER TABLE config ADD COLUMN updated_by TEXT'

class DatabaseManager:
    """Manages local SQLite database operations"""
    
    def __init__(self):
        db_path = Config.DATABASE_PATH
        if not os.path.isabs(db_path):
            app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(app_dir, db_path)
        
        self.db_path = os.path.abspath(db_path)
        self.ph = PasswordHasher()
        print(f"[DB] Database path: {self.db_path}")
        
    def initialize_database(self):
        """Initialize database with required tables"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT DEFAULT 'user',
                    is_active BOOLEAN DEFAULT 1,
                    avatar_url TEXT,
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
                )
            ''')
            
            # Parameters table for local sync
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS parameters (
                    id INTEGER PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    unit TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    enabled BOOLEAN DEFAULT 1,
                    alert_min REAL,
                    alert_max REAL,
                    warn_min REAL,
                    warn_max REAL,
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
                )
            ''')
            
            # Parameter stream table for storing streamed data
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS parameter_stream (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parameter_id INTEGER NOT NULL REFERENCES parameters(id),
                    value REAL NOT NULL,
                    timestamp TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    synced BOOLEAN DEFAULT 0
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_parameter_stream_param_id ON parameter_stream(parameter_id)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_parameter_stream_timestamp ON parameter_stream(timestamp)
            ''')
            
            # Local buffer table for offline data with foreign key
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS local_buffer (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parameter_id INTEGER NOT NULL,
                    value REAL NOT NULL,
                    timestamp TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    synced BOOLEAN DEFAULT 0,
                    FOREIGN KEY (parameter_id) REFERENCES parameters(id)
                )
            ''')
            
            # Server log table for tracking all changes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS server_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT,
                    action TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    status TEXT DEFAULT 'success',
                    error_message TEXT,
                    timestamp TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    user_email TEXT,
                    device_id TEXT
                )
            ''')
            
            # Configuration table for system settings
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    data_type TEXT DEFAULT 'string',
                    version INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    updated_by TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_config_category ON config(category)
            ''')
            
            # Permissions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    action TEXT NOT NULL,
                    allowed BOOLEAN DEFAULT 1,
                    UNIQUE(role, resource, action)
                )
            ''')

            # Telemetry buffer table for offline Socket.IO queuing
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS telemetry_buffer (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    data TEXT NOT NULL,
                    synced BOOLEAN DEFAULT 0
                )
            ''')

            conn.commit()
            self._migrate_timestamps(conn)
            self._create_default_data()
    
    def _migrate_timestamps(self, conn):
        """Migrate existing UTC timestamps to local time and ensure config table schema"""
        cursor = conn.cursor()
        try:
            # Migrate users table: rename user_id -> id if needed
            cursor.execute('PRAGMA table_info(users)')
            user_columns = {row[1] for row in cursor.fetchall()}
            if 'id' not in user_columns and 'user_id' in user_columns:
                cursor.execute('ALTER TABLE users RENAME TO users_old')
                cursor.execute('''
                    CREATE TABLE users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT UNIQUE NOT NULL,
                        name TEXT NOT NULL,
                        password_hash TEXT NOT NULL,
                        role TEXT DEFAULT "user",
                        is_active BOOLEAN DEFAULT 1,
                        avatar_url TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                cursor.execute('''
                    INSERT INTO users (id, email, name, password_hash, role, is_active, avatar_url, created_at, updated_at)
                    SELECT user_id, email, name, password_hash, role, is_active, avatar_url, created_at, updated_at
                    FROM users_old
                ''')
                cursor.execute('DROP TABLE users_old')
                conn.commit()
                print('[DB] Migrated users table: user_id -> id')
                # Refresh column set after migration
                cursor.execute('PRAGMA table_info(users)')
                user_columns = {row[1] for row in cursor.fetchall()}

            cursor.execute('SELECT COUNT(*) FROM users')
            if cursor.fetchone()[0] > 0:
                cursor.execute('''
                    UPDATE users SET updated_at = datetime('now', 'localtime')
                    WHERE updated_at IS NULL
                ''')
            cursor.execute('SELECT COUNT(*) FROM parameters')
            if cursor.fetchone()[0] > 0:
                cursor.execute('''
                    UPDATE parameters SET updated_at = datetime('now', 'localtime')
                    WHERE updated_at IS NULL
                ''')

            # Add avatar_url column if missing (existing databases)
            if 'avatar_url' not in user_columns:
                cursor.execute('ALTER TABLE users ADD COLUMN avatar_url TEXT')

            # Add alert columns to parameters if missing (existing databases)
            cursor.execute('PRAGMA table_info(parameters)')
            param_columns = {row[1] for row in cursor.fetchall()}
            for col, typ in [('alert_min', 'REAL'), ('alert_max', 'REAL'),
                             ('warn_min', 'REAL'), ('warn_max', 'REAL')]:
                if col not in param_columns:
                    cursor.execute(f'ALTER TABLE parameters ADD COLUMN {col} {typ}')
            
            # Ensure config table has all required columns
            try:
                cursor.execute(_SQL_PRAGMA_CONFIG)
                columns = {row[1] for row in cursor.fetchall()}

                if 'category'   not in columns: cursor.execute(_SQL_ADD_CATEGORY)
                if 'data_type'  not in columns: cursor.execute(_SQL_ADD_DATA_TYPE)
                if 'version'    not in columns: cursor.execute(_SQL_ADD_VERSION)
                if 'created_at' not in columns: cursor.execute(_SQL_ADD_CREATED_AT)
                if 'updated_at' not in columns: cursor.execute(_SQL_ADD_UPDATED_AT)
                if 'updated_by' not in columns: cursor.execute(_SQL_ADD_UPDATED_BY)
            except sqlite3.Error as e:
                print(f"[DB] Config table migration warning: {e}")
            
            conn.commit()
        except Exception as e:
            print(f"[DB] Migration error: {e}")
    
    def _create_default_data(self):
        """Create default admin user and permissions — only if they don't already exist"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Admin user — only insert once
            cursor.execute('SELECT COUNT(*) FROM users WHERE email = ?', ('admin@precisionpulse.com',))
            if cursor.fetchone()[0] == 0:
                admin_hash = self.ph.hash('admin123')
                cursor.execute('''
                    INSERT INTO users (email, name, password_hash, role)
                    VALUES (?, ?, ?, ?)
                ''', ('admin@precisionpulse.com', 'Admin User', admin_hash, 'admin'))

            # Default permissions — INSERT OR IGNORE prevents duplicates
            default_permissions = [
                ('admin', 'users', 'read'), ('admin', 'users', 'write'),
                ('admin', 'roles', 'read'), ('admin', 'roles', 'write'),
                ('admin', 'config', 'read'), ('admin', 'config', 'write'),
                ('admin', 'livedata', 'read'), ('admin', 'livedata', 'write'),
                ('admin', 'reports', 'read'), ('admin', 'reports', 'export'),
                ('admin', 'web', 'login'), ('admin', 'desktop', 'login'),
                ('client', 'config', 'read'),
                ('client', 'livedata', 'write'), ('client', 'desktop', 'login'),
                ('user', 'livedata', 'read'), ('user', 'reports', 'read'),
                ('user', 'web', 'login'), ('user', 'desktop', 'login'),
            ]
            for role, resource, action in default_permissions:
                cursor.execute('''
                    INSERT OR IGNORE INTO permissions (role, resource, action, allowed)
                    VALUES (?, ?, ?, 1)
                ''', (role, resource, action))

            conn.commit()
    
    def authenticate_user(self, email: str, password: str) -> Optional[Dict]:
        """Authenticate user credentials with both bcrypt and argon2 support"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, email, name, password_hash, role, is_active
                FROM users WHERE email = ? AND is_active = 1
            ''', (email,))
            
            user = cursor.fetchone()
            if user:
                password_hash = user[3]
                try:
                    # Try bcrypt first (for users created from web app)
                    if password_hash.startswith('$2b$'):
                        if bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
                            return {
                                'id': user[0],
                                'email': user[1],
                                'name': user[2],
                                'role': user[4]
                            }
                    else:
                        # Try argon2 (for users created locally)
                        self.ph.verify(password_hash, password)
                        return {
                            'id': user[0],
                            'email': user[1],
                            'name': user[2],
                            'role': user[4]
                        }
                except Exception:
                    return None
            return None
    
    def get_enabled_parameters(self) -> List[Dict]:
        """Get enabled parameters from local SQLite including alert columns."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, unit, description, enabled, alert_min, alert_max, warn_min, warn_max
                FROM parameters WHERE enabled = 1
                ORDER BY name
            ''')
            local_params = [
                {
                    'id': row[0], 'name': row[1], 'unit': row[2],
                    'description': row[3] or '',
                    'alert_min': row[5], 'alert_max': row[6],
                    'warn_min': row[7], 'warn_max': row[8],
                }
                for row in cursor.fetchall()
            ]
            if local_params:
                print(f"Using {len(local_params)} parameters from SQLite")
                return local_params
        return []
    
    def buffer_telemetry(self, parameter_id: int, value: float):
        """Buffer telemetry data when offline"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO local_buffer (parameter_id, value, timestamp)
                VALUES (?, ?, datetime('now', 'localtime'))
            ''', (parameter_id, value))
            conn.commit()
    
    def store_parameter_stream(self, parameter_id: int, value: float, timestamp: str = None) -> int:
        """Store parameter stream data with dedup guard.
        Returns the inserted row id, or 0 if skipped/failed.
        Skips insert if a row for the same parameter_id already exists
        within a 2-second window of the given timestamp to prevent
        duplicates from concurrent write paths.
        """
        try:
            if parameter_id is None:
                return 0
            try:
                param_id = int(parameter_id)
            except (ValueError, TypeError):
                return 0
            try:
                val = float(value) if value is not None else 0.0
            except (ValueError, TypeError):
                return 0

            ts_str = timestamp or datetime.now().isoformat()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Dedup: skip if a row for this parameter already exists
                # within a 2-second window of the incoming timestamp.
                cursor.execute('''
                    SELECT id FROM parameter_stream
                    WHERE parameter_id = ?
                      AND timestamp BETWEEN datetime(?, '-2 seconds')
                                        AND datetime(?, '+2 seconds')
                    LIMIT 1
                ''', (param_id, ts_str, ts_str))
                if cursor.fetchone():
                    return 0  # duplicate — skip silently

                if timestamp:
                    cursor.execute(
                        'INSERT INTO parameter_stream (parameter_id, value, timestamp) VALUES (?, ?, ?)',
                        (param_id, val, ts_str)
                    )
                else:
                    cursor.execute(
                        "INSERT INTO parameter_stream (parameter_id, value, timestamp) VALUES (?, ?, datetime('now', 'localtime'))",
                        (param_id, val)
                    )
                conn.commit()
                return cursor.lastrowid or 0
        except sqlite3.Error as e:
            print(f"[DB] SQLite Error storing parameter_stream: {e}")
            return 0
        except Exception as e:
            print(f"[DB] Unexpected error storing parameter_stream: {e}")
            return 0
    
    def get_buffered_data(self) -> List[Dict]:
        """Get all unsynced buffered data with parameter details"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT lb.id, lb.parameter_id, p.name, p.unit, lb.value, lb.timestamp
                FROM local_buffer lb
                JOIN parameters p ON lb.parameter_id = p.id
                WHERE lb.synced = 0
                ORDER BY lb.timestamp ASC
            ''')
            
            return [
                {
                    'id': row[0],
                    'parameter_id': row[1],
                    'parameter_name': row[2],
                    'unit': row[3],
                    'value': row[4],
                    'timestamp': row[5]
                }
                for row in cursor.fetchall()
            ]
    
    def get_parameter_stream_data(self, parameter_id: Optional[int] = None, limit: int = 100) -> List[Dict]:
        """Get parameter stream data"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if parameter_id:
                cursor.execute('''
                    SELECT ps.id, ps.parameter_id, p.name, p.unit, ps.value, ps.timestamp
                    FROM parameter_stream ps
                    JOIN parameters p ON ps.parameter_id = p.id
                    WHERE ps.parameter_id = ?
                    ORDER BY ps.timestamp DESC
                    LIMIT ?
                ''', (parameter_id, limit))
            else:
                cursor.execute('''
                    SELECT ps.id, ps.parameter_id, p.name, p.unit, ps.value, ps.timestamp
                    FROM parameter_stream ps
                    JOIN parameters p ON ps.parameter_id = p.id
                    ORDER BY ps.timestamp DESC
                    LIMIT ?
                ''', (limit,))
            
            return [
                {
                    'id': row[0],
                    'parameter_id': row[1],
                    'parameter_name': row[2],
                    'unit': row[3],
                    'value': row[4],
                    'timestamp': row[5]
                }
                for row in cursor.fetchall()
            ]
    
    def log_server_event(self, event_type: str, resource_type: str, action: str, 
                        resource_id: Optional[str] = None, old_value: Optional[str] = None,
                        new_value: Optional[str] = None, status: str = 'success',
                        error_message: Optional[str] = None, user_email: Optional[str] = None,
                        device_id: Optional[str] = None):
        """Log server event to database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO server_log 
                (event_type, resource_type, resource_id, action, old_value, new_value, 
                 status, error_message, user_email, device_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
            ''', (event_type, resource_type, resource_id, action, old_value, new_value,
                  status, error_message, user_email, device_id))
            conn.commit()
    
    def get_server_logs(self, limit: int = 100, event_type: Optional[str] = None) -> List[Dict]:
        """Get server logs"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if event_type:
                cursor.execute('''
                    SELECT id, event_type, resource_type, resource_id, action, old_value, 
                           new_value, status, error_message, timestamp, user_email, device_id
                    FROM server_log
                    WHERE event_type = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (event_type, limit))
            else:
                cursor.execute('''
                    SELECT id, event_type, resource_type, resource_id, action, old_value, 
                           new_value, status, error_message, timestamp, user_email, device_id
                    FROM server_log
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (limit,))
            
            return [
                {
                    'id': row[0],
                    'event_type': row[1],
                    'resource_type': row[2],
                    'resource_id': row[3],
                    'action': row[4],
                    'old_value': row[5],
                    'new_value': row[6],
                    'status': row[7],
                    'error_message': row[8],
                    'timestamp': row[9],
                    'user_email': row[10],
                    'device_id': row[11]
                }
                for row in cursor.fetchall()
            ]
    
    def mark_data_synced(self, buffer_ids: List[int]):
        """Mark buffered data as synced"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            placeholders = ','.join('?' * len(buffer_ids))
            cursor.execute(f'''
                UPDATE local_buffer 
                SET synced = 1 
                WHERE id IN ({placeholders})
            ''', buffer_ids)
            conn.commit()
    
    def clear_synced_data(self):
        """Clear old synced data"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM local_buffer 
                WHERE synced = 1 AND timestamp < datetime('now', 'localtime', '-1 day')
            ''')
            conn.commit()
    
    def check_permission(self, role: str, resource: str, action: str) -> bool:
        """Check if role has permission for resource action"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT allowed FROM permissions
                WHERE role = ? AND resource = ? AND action = ?
            ''', (role, resource, action))
            result = cursor.fetchone()
            return result[0] == 1 if result else False

    def delete_buffered_data(self, buffer_ids: List[int]):
        """Delete buffered data by IDs"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            placeholders = ','.join('?' * len(buffer_ids))
            cursor.execute(f'''
                DELETE FROM local_buffer 
                WHERE id IN ({placeholders})
            ''', buffer_ids)
            conn.commit()
            print(f"[DB] Deleted {cursor.rowcount} buffered records")
    
    def mark_parameter_stream_synced(self, stream_ids: List[int]):
        """Mark parameter stream data as synced by IDs"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            placeholders = ','.join('?' * len(stream_ids))
            cursor.execute(f'UPDATE parameter_stream SET synced = 1 WHERE id IN ({placeholders})', stream_ids)
            conn.commit()

    def mark_parameter_stream_synced_by_timestamp(self, timestamp: str):
        """Mark all parameter_stream records within a 5-second window of the given
        timestamp as synced. Uses a range query instead of exact string match
        because SQLite may normalize the timestamp format on storage.
        The window is 5s to match the backend's 3s dedup window plus margin.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''UPDATE parameter_stream SET synced = 1
                   WHERE synced = 0
                     AND timestamp BETWEEN datetime(?, '-5 seconds')
                                       AND datetime(?, '+5 seconds')''',
                (timestamp, timestamp)
            )
            conn.commit()
    
    def get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    def get_config(self, key: str, default: str = None) -> str:
        """Get configuration value"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(_SQL_PRAGMA_CONFIG)
                columns = {row[1] for row in cursor.fetchall()}
                if 'category' not in columns:
                    cursor.execute(_SQL_ADD_CATEGORY)
                    conn.commit()

                cursor.execute('SELECT value FROM config WHERE key = ?', (key,))
                result = cursor.fetchone()
                return result[0] if result else default
        except sqlite3.Error as e:
            print(f"[DB] Error getting config {key}: {e}")
            return default
    
    def set_config(self, key: str, value: str, category: str = 'general', data_type: str = 'string'):
        """Set configuration value"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(_SQL_PRAGMA_CONFIG)
                columns = {row[1] for row in cursor.fetchall()}
                if 'category'  not in columns: cursor.execute(_SQL_ADD_CATEGORY)
                if 'data_type' not in columns: cursor.execute(_SQL_ADD_DATA_TYPE)
                if 'version'   not in columns: cursor.execute(_SQL_ADD_VERSION)
                if 'updated_at' not in columns: cursor.execute(_SQL_ADD_UPDATED_AT)
                conn.commit()

                cursor.execute('''
                    INSERT OR REPLACE INTO config (key, value, category, data_type, version, updated_at)
                    VALUES (?, ?, ?, ?, 1, datetime('now', 'localtime'))
                ''', (key, value, category, data_type))
                conn.commit()
                print(f"[DB] Set config {key} = {value}")
        except sqlite3.Error as e:
            print(f"[DB] Error setting config {key}: {e}")
    
    def get_all_configs(self) -> Dict[str, str]:
        """Get all configurations"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(_SQL_PRAGMA_CONFIG)
                columns = {row[1] for row in cursor.fetchall()}
                if 'category' not in columns:
                    cursor.execute(_SQL_ADD_CATEGORY)
                    conn.commit()

                cursor.execute('SELECT key, value FROM config')
                return {row[0]: row[1] for row in cursor.fetchall()}
        except sqlite3.Error as e:
            print(f"[DB] Error getting all configs: {e}")
            return {}
