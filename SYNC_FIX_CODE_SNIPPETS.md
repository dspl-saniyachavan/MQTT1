# User Sync Fix - Copy-Paste Code Snippets

## Backend Changes

### 1. app/services/sync_service.py - Add Logging to sync_user_to_sqlite()

Find this method and replace it:

```python
def sync_user_to_sqlite(self, user_data):
    """Sync user from PostgreSQL to SQLite with error handling"""
    try:
        if not os.path.exists(self.sqlite_path):
            logger.warning(f"[SYNC_SERVICE] SQLite database not found at {self.sqlite_path}")
            logger.info(f"[SYNC_SERVICE] Attempting to create SQLite at {self.sqlite_path}")
            os.makedirs(os.path.dirname(self.sqlite_path), exist_ok=True)
        
        with sqlite3.connect(self.sqlite_path) as conn:
            cursor = conn.cursor()
            
            # Check if users table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if not cursor.fetchone():
                logger.error(f"[SYNC_SERVICE] Users table does not exist in SQLite at {self.sqlite_path}")
                return False
            
            cursor.execute('SELECT id FROM users WHERE email = ?', (user_data['email'],))
            existing = cursor.fetchone()
            
            if existing:
                cursor.execute('''
                    UPDATE users SET name = ?, role = ?, is_active = ?, password_hash = ?, avatar_url = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE email = ?
                ''', (user_data['name'], user_data['role'], user_data['is_active'],
                      user_data['password_hash'], user_data.get('avatar_url'), user_data['email']))
                logger.info(f"[SYNC_SERVICE] Updated user {user_data['email']} in SQLite (role={user_data['role']})")
            else:
                cursor.execute('''
                    INSERT INTO users (email, name, password_hash, role, is_active, avatar_url, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ''', (user_data['email'], user_data['name'], user_data['password_hash'],
                      user_data['role'], user_data['is_active'], user_data.get('avatar_url')))
                logger.info(f"[SYNC_SERVICE] Inserted user {user_data['email']} into SQLite (role={user_data['role']})")
            
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"[SYNC_SERVICE] Error syncing user to SQLite: {e}", exc_info=True)
        return False
```

### 2. app/controllers/user_controller.py - Add Logging After Sync Calls

In `update_user()` method, after the sync_service call, add:

```python
# Sync to SQLite
result = sync_service.sync_user_to_sqlite({
    'email': user.email,
    'name': user.name,
    'password_hash': user.password_hash,
    'role': user.role,
    'is_active': user.is_active,
    'avatar_url': user.avatar_url
})
if result:
    logger.info(f"[USER_CONTROLLER] Successfully synced user {user.email} to SQLite (role={user.role})")
else:
    logger.error(f"[USER_CONTROLLER] Failed to sync user {user.email} to SQLite")
```

### 3. app/routes/internal_routes.py - Add Sync Status Endpoint

Add this new route at the end of the file:

```python
@internal_bp.route('/sync-status', methods=['GET'])
def get_sync_status():
    """Check if SQLite is accessible and synced"""
    try:
        from app.services.sync_service import sync_service
        status = sync_service.get_sync_status()
        return jsonify(status), 200 if status.get('connected') else 500
    except Exception as e:
        logger.error(f"[INTERNAL] Error getting sync status: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
```

---

## Desktop Changes

### 1. src/ui/manage_users_page.py - Add Backend Sync in edit_user()

Find the `edit_user()` method and add this after the SQLite update:

```python
# Sync to backend PostgreSQL
try:
    import requests
    token = self.auth_service.get_token() if self.auth_service else None
    if token:
        response = requests.put(
            f"http://localhost:5000/api/internal/sync-user-role",
            json={"email": user['email'], "role": user_data['role']},
            headers={"Authorization": f"Bearer {token}"},
            timeout=5
        )
        if response.status_code == 200:
            print(f"[MANAGE_USERS] Synced role to backend: {user['email']} -> {user_data['role']}")
        else:
            print(f"[MANAGE_USERS] Backend sync failed: {response.status_code}")
except Exception as e:
    print(f"[MANAGE_USERS] Backend sync error: {e}")
```

### 2. src/ui/manage_users_page.py - Add Fallback Sync Timer

In `__init__()` method, after the online poll timer, add:

```python
# Periodic role sync from backend (every 30 seconds) as fallback
self._role_sync_timer = QTimer()
self._role_sync_timer.timeout.connect(self._sync_roles_from_backend)
self._role_sync_timer.start(30000)
```

### 3. src/ui/manage_users_page.py - Add Fallback Sync Method

Add this new method to the ManageUsersPage class:

```python
def _sync_roles_from_backend(self):
    """Periodic sync of user roles from backend via HTTP (fallback if MQTT fails)"""
    try:
        import requests
        token = self.auth_service.get_token() if self.auth_service else None
        if not token:
            return
        
        response = requests.get(
            'http://localhost:5000/api/users',
            headers={'Authorization': f'Bearer {token}'},
            timeout=3
        )
        
        if response.status_code == 200:
            backend_users = response.json()
            if not isinstance(backend_users, list):
                backend_users = backend_users.get('users', [])
            
            # Update local users with backend roles
            for backend_user in backend_users:
                for local_user in self.users:
                    if local_user['email'] == backend_user.get('email'):
                        if local_user['role'] != backend_user.get('role'):
                            print(f"[MANAGE_USERS] Role sync from backend: {backend_user.get('email')} -> {backend_user.get('role')}")
                            local_user['role'] = backend_user.get('role')
                            # Update SQLite
                            if self.db:
                                import sqlite3
                                with sqlite3.connect(self.db.db_path) as conn:
                                    cursor = conn.cursor()
                                    cursor.execute(
                                        'UPDATE users SET role = ? WHERE email = ?',
                                        (backend_user.get('role'), backend_user.get('email'))
                                    )
                                    conn.commit()
                        break
            
            # Refresh table to show any updated roles
            self.refresh_table()
    except Exception as e:
        pass  # Silent fail - this is just a fallback sync
```

### 4. src/services/user_sync_service.py - Add Logging

In `_on_mqtt_message()` method, find the role_changed handler and add logging:

```python
elif 'sync/roles/changed' in topic or msg_type == 'role_changed':
    user_id = payload.get('user_id')
    email = payload.get('email')
    old_role = payload.get('old_role')
    new_role = payload.get('new_role')
    print(f"[USER_SYNC] Processing role_changed: {email} {old_role} -> {new_role}")
    for u in self.users:
        if u.get('id') == user_id:
            u['role'] = new_role
            break
    logger.info(f"[USER_SYNC] Role changed for {email}: {old_role} -> {new_role}")
    if self.database_manager:
        result = self._update_user_role_in_db(user_id, new_role)
        if result:
            print(f"[USER_SYNC] Successfully updated SQLite: {email} role={new_role}")
        else:
            print(f"[USER_SYNC] Failed to update SQLite: {email}")
    self.role_changed.emit(user_id, email, old_role, new_role)
```

---

## Docker Configuration

### docker-compose.yml - Add Shared Volume

Add this to the backend service environment:

```yaml
services:
  backend:
    environment:
      - SQLITE_DB_PATH=/shared/data/precision_pulse.db
    volumes:
      - ./data:/shared/data
```

---

## Verification Commands

### Check Backend Can Find SQLite
```bash
curl http://localhost:5000/api/internal/sync-status
```

Expected response:
```json
{
  "status": "ok",
  "message": "SQLite database connected",
  "sqlite_path": "/shared/data/precision_pulse.db",
  "connected": true,
  "user_count": 5,
  "parameter_count": 10,
  "timestamp": "2024-03-31T12:00:00.000000+00:00"
}
```

### Check SQLite User Role
```bash
sqlite3 /path/to/data/precision_pulse.db "SELECT email, role FROM users WHERE email='testuser@example.com';"
```

### Check PostgreSQL User Role
```bash
# From backend container
psql -U postgres -d precision_pulse -c "SELECT email, role FROM users WHERE email='testuser@example.com';"
```

---

## Testing Sequence

1. **Start all services**
   ```bash
   docker compose up -d
   ```

2. **Verify backend can find SQLite**
   ```bash
   curl http://localhost:5000/api/internal/sync-status
   ```

3. **Create user on web dashboard**
   - Go to http://localhost:3000
   - Login as admin
   - Create new user: testuser@example.com / test123

4. **Verify user synced to desktop SQLite**
   ```bash
   sqlite3 data/precision_pulse.db "SELECT email, role FROM users WHERE email='testuser@example.com';"
   ```

5. **Change role on web dashboard**
   - Go to Users page
   - Click "Edit Role" on testuser
   - Change from "user" to "admin"
   - Click "Save Changes"

6. **Verify role synced to desktop**
   - Check desktop console for: `[USER_SYNC] Processing role_changed`
   - Check desktop SQLite: `SELECT role FROM users WHERE email='testuser@example.com'` should be 'admin'
   - Check desktop UI: Manage Users page should show "ADMIN" badge

7. **Test fallback sync**
   - Stop MQTT broker: `docker compose stop mosquitto`
   - Change role on web again
   - Wait 30 seconds
   - Check desktop console for: `[MANAGE_USERS] Role sync from backend`
   - Verify role updated in desktop UI

---

## Troubleshooting

| Error | Solution |
|-------|----------|
| `[SYNC_SERVICE] SQLite database not found` | Check SQLITE_DB_PATH environment variable |
| `[SYNC_SERVICE] Users table does not exist` | Ensure desktop SQLite is initialized |
| `[MANAGE_USERS] Backend sync failed: 500` | Check backend logs for errors |
| `[USER_SYNC] Failed to update SQLite` | Check desktop SQLite permissions |
| Role not updating in UI | Check if refresh_table() is being called |

---

## Summary

These changes implement:
1. ✅ Backend can find desktop's SQLite
2. ✅ Desktop POSTs role changes to backend
3. ✅ Comprehensive logging at each step
4. ✅ HTTP fallback sync every 30 seconds
5. ✅ Sync status verification endpoint

After implementing these changes, user roles will sync bidirectionally between PostgreSQL and SQLite with full visibility and fallback mechanisms.
