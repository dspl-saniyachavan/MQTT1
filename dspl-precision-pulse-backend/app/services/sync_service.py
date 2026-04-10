"""
Database sync service to mirror data between PostgreSQL (backend) and SQLite (desktop)
"""
import sqlite3
import os
import logging
from datetime import datetime, timezone, timezone
from app.models import db
from app.models.user import User
from app.models.parameter import Parameter

logger = logging.getLogger(__name__)

class DatabaseSyncService:
    """Service to sync data between PostgreSQL and SQLite databases"""
    
    def __init__(self, sqlite_path=None):
        if sqlite_path:
            self.sqlite_path = sqlite_path
        else:
            # SQLITE_DB_PATH env var takes priority (set in docker-compose.yml).
            # Inside Docker: /app/data/precision_pulse.db (shared volume).
            # Local dev: sibling data/ directory next to the backend folder.
            env_path = os.environ.get('SQLITE_DB_PATH')
            if env_path:
                self.sqlite_path = env_path
            elif os.path.isdir('/app'):
                self.sqlite_path = '/app/data/precision_pulse.db'
            else:
                self.sqlite_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    'data', 'precision_pulse.db'
                )

        os.makedirs(os.path.dirname(self.sqlite_path), exist_ok=True)
        logger.info("[SYNC_SERVICE] Using SQLite path: %s", self.sqlite_path)
    
    def full_sync_to_sqlite(self):
        """Sync all PostgreSQL users and parameters to SQLite"""
        try:
            users = User.query.all()
            for user in users:
                self.sync_user_to_sqlite(user.to_dict())
            from app.models.parameter import Parameter
            params = Parameter.query.all()
            for param in params:
                self.sync_parameter_to_sqlite(param.to_dict())
            logger.info('[SYNC_SERVICE] full_sync_to_sqlite: %d users, %d params', len(users), len(params))
        except Exception as e:
            logger.error('[SYNC_SERVICE] full_sync_to_sqlite error: %s', e)
            raise

    def full_sync_from_sqlite(self):
        """Sync all SQLite users and parameters back to PostgreSQL"""
        try:
            if not os.path.exists(self.sqlite_path):
                logger.warning('[SYNC_SERVICE] SQLite not found at %s', self.sqlite_path)
                return
            with sqlite3.connect(self.sqlite_path) as conn:
                cursor = conn.cursor()
                # Check table exists before querying
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
                if not cursor.fetchone():
                    logger.info('[SYNC_SERVICE] No users table in SQLite, skipping from-sqlite sync')
                    return
                cursor.execute('SELECT email, name, password_hash, role, is_active FROM users')
                for row in cursor.fetchall():
                    email, name, password_hash, role, is_active = row
                    user = User.query.filter_by(email=email).first()
                    if user:
                        user.name = name
                        user.password_hash = password_hash
                    else:
                        user = User(email=email, name=name, role=role or 'user', is_active=bool(is_active))
                        user.password_hash = password_hash
                        db.session.add(user)
                db.session.commit()
            logger.info('[SYNC_SERVICE] full_sync_from_sqlite complete')
        except Exception as e:
            logger.error('[SYNC_SERVICE] full_sync_from_sqlite error: %s', e)
            db.session.rollback()
            raise

    def sync_user_to_sqlite(self, user_data):
        """Sync user from PostgreSQL to SQLite with error handling"""
        try:
            os.makedirs(os.path.dirname(self.sqlite_path), exist_ok=True)
            
            with sqlite3.connect(self.sqlite_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT id FROM users WHERE email = ?', (user_data['email'],))
                existing = cursor.fetchone()
                
                if existing:
                    cursor.execute('''
                        UPDATE users SET name = ?, role = ?, is_active = ?, password_hash = ?, avatar_url = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE email = ?
                    ''', (user_data['name'], user_data['role'], user_data['is_active'],
                          user_data['password_hash'], user_data.get('avatar_url'), user_data['email']))
                    logger.info(f"[SYNC_SERVICE] Updated user {user_data['email']} in SQLite")
                else:
                    cursor.execute('''
                        INSERT INTO users (email, name, password_hash, role, is_active, avatar_url, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ''', (user_data['email'], user_data['name'], user_data['password_hash'],
                          user_data['role'], user_data['is_active'], user_data.get('avatar_url')))
                    logger.info(f"[SYNC_SERVICE] Inserted user {user_data['email']} into SQLite")
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"[SYNC_SERVICE] Error syncing user to SQLite: {e}")
            return False
    
    def sync_parameter_to_sqlite(self, param_data):
        """Sync parameter from PostgreSQL to SQLite with error handling"""
        try:
            os.makedirs(os.path.dirname(self.sqlite_path), exist_ok=True)

            with sqlite3.connect(self.sqlite_path) as conn:
                cursor = conn.cursor()
                # Use the real integer id — never a derived string key
                cursor.execute('''
                    INSERT OR REPLACE INTO parameters (id, name, unit, description, enabled,
                        alert_min, alert_max, warn_min, warn_max)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (param_data['id'], param_data['name'], param_data['unit'],
                      param_data.get('description', ''), param_data['enabled'],
                      param_data.get('alert_min'), param_data.get('alert_max'),
                      param_data.get('warn_min'), param_data.get('warn_max')))
                conn.commit()
                logger.info(f"[SYNC_SERVICE] Synced parameter id={param_data['id']} name={param_data['name']} to SQLite")
                return True
        except Exception as e:
            logger.error(f"[SYNC_SERVICE] Error syncing parameter to SQLite: {e}")
            return False
    
    def delete_user_from_sqlite(self, email):
        """Delete user from SQLite with error handling"""
        try:
            if not os.path.exists(self.sqlite_path):
                return False
            
            with sqlite3.connect(self.sqlite_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM users WHERE email = ?', (email,))
                conn.commit()
                logger.info(f"[SYNC_SERVICE] Deleted user {email} from SQLite")
                return True
        except Exception as e:
            logger.error(f"[SYNC_SERVICE] Error deleting user from SQLite: {e}")
            return False
    
    def get_sync_status(self):
        """Get sync status and health check"""
        try:
            if not os.path.exists(self.sqlite_path):
                return {
                    'status': 'error',
                    'message': f'SQLite database not found at {self.sqlite_path}',
                    'sqlite_path': self.sqlite_path,
                    'connected': False
                }
            
            with sqlite3.connect(self.sqlite_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM users')
                user_count = cursor.fetchone()[0]
                cursor.execute('SELECT COUNT(*) FROM parameters')
                param_count = cursor.fetchone()[0]
                
                return {
                    'status': 'ok',
                    'message': 'SQLite database connected',
                    'sqlite_path': self.sqlite_path,
                    'connected': True,
                    'user_count': user_count,
                    'parameter_count': param_count,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
        except Exception as e:
            logger.error(f"[SYNC_SERVICE] Error checking sync status: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'sqlite_path': self.sqlite_path,
                'connected': False
            }

sync_service = DatabaseSyncService()
