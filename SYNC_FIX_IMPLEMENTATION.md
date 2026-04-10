# User Sync Fix - Implementation Guide

## Quick Summary of Issues

1. **SQLite Path Mismatch** - Backend can't find desktop's SQLite database
2. **No Desktop→Backend Sync** - Desktop doesn't POST role changes to backend
3. **Missing Error Logging** - Sync failures happen silently
4. **No Fallback Mechanism** - If MQTT fails, no HTTP fallback exists

## Solution Overview

### Backend Changes Required

#### 1. Fix sync_service.py - SQLite Path Resolution

**Current Problem:**
```python
# Looks for SQLite in wrong location
self.sqlite_path = '/app/data/precision_pulse.db'  # Docker path
# But desktop creates it at: data/precision_pulse.db (relative)
```

**Fix:**
```python
# Use environment variable first (set in docker-compose.yml)
env_path = os.environ.get('SQLITE_DB_PATH')
if env_path:
    self.sqlite_path = env_path
# Then try Docker path
elif os.path.isdir('/app'):
    self.sqlite_path = '/app/data/precision_pulse.db'
# Then try relative path
else:
    self.sqlite_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'data', 'precision_pulse.db'
    )
```

**Add to sync_user_to_sqlite():**
```python
# Log role changes explicitly
logger.info(f"[SYNC_SERVICE] Syncing user {user_data['email']} role={user_data['role']} to SQLite")

# Check if table exists before inserting
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
if not cursor.fetchone():
    logger.error(f"[SYNC_SERVICE] Users table missing in SQLite at {self.sqlite_path}")
    return False
```

#### 2. Add Sync Status Endpoint - internal_routes.py

**Add new endpoint:**
```python
@internal_bp.route('/sync-status', methods=['GET'])
def get_sync_status():
    """Check if SQLite is accessible and synced"""
    try:
        from app.services.sync_service import sync_service
        status = sync_service.get_sync_status()
        return jsonify(status), 200 if status['connected'] else 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
```

#### 3. Enhance Logging in user_controller.py

**Add after each sync call:**
```python
# After sync_service.sync_user_to_sqlite()
result = sync_service.sync_user_to_sqlite({...})
if result:
    logger.info(f"[USER_CONTROLLER] Successfully synced user {user.email} to SQLite")
else:
    logger.error(f"[USER_CONTROLLER] Failed to sync user {user.email} to SQLite")
```

---

### Desktop Changes Required

#### 1. Fix manage_users_page.py - Add Backend Sync

**In edit_user() method, after SQLite update:**
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

#### 2. Add Fallback HTTP Sync - manage_users_page.py

**Add timer in __init__:**
```python
# Periodic role sync from backend (every 30 seconds) as fallback
self._role_sync_timer = QTimer()
self._role_sync_timer.timeout.connect(self._sync_roles_from_backend)
self._role_sync_timer.start(30000)
```

**Add method:**
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

#### 3. Add Logging to user_sync_service.py

**In _on_mqtt_message():**
```python
# Add at start of role_changed handler
print(f"[USER_SYNC] Processing role_changed: {email} {old_role} -> {new_role}")

# Add after SQLite update
result = self._update_user_role_in_db(user_id, new_role)
if result:
    print(f"[USER_SYNC] Successfully updated SQLite: {email} role={new_role}")
else:
    print(f"[USER_SYNC] Failed to update SQLite: {email}")
```

---

## Docker Compose Configuration

**Add to docker-compose.yml for backend service:**
```yaml
environment:
  - SQLITE_DB_PATH=/shared/data/precision_pulse.db
volumes:
  - ./data:/shared/data  # Shared volume for SQLite
```

**Add to docker-compose.yml for desktop service (if containerized):**
```yaml
volumes:
  - ./data:/app/data  # Same shared volume
```

---

## Testing Checklist

- [ ] Backend can find SQLite: `curl http://localhost:5000/api/internal/sync-status`
- [ ] Web→Desktop: Create user on web, verify in desktop SQLite
- [ ] Desktop→Web: Change role on desktop, verify on web PostgreSQL
- [ ] MQTT Sync: Change role on web, verify desktop receives MQTT message
- [ ] Fallback Sync: Stop MQTT, change role on web, wait 30s, verify desktop updates
- [ ] Console Logs: Check for sync messages at each step

---

## Console Log Indicators

### Successful Sync
```
[SYNC_SERVICE] Syncing user testuser@example.com role=admin to SQLite
[SYNC_SERVICE] Updated user testuser@example.com in SQLite (role=admin)
[USER_CONTROLLER] Successfully synced user testuser@example.com to SQLite
[USER_SYNC] Processing role_changed: testuser@example.com user -> admin
[USER_SYNC] Successfully updated SQLite: testuser@example.com role=admin
[MANAGE_USERS] Role sync from backend: testuser@example.com -> admin
```

### Failed Sync
```
[SYNC_SERVICE] SQLite database not found at /app/data/precision_pulse.db
[SYNC_SERVICE] Users table does not exist in SQLite
[USER_CONTROLLER] Failed to sync user testuser@example.com to SQLite
[MANAGE_USERS] Backend sync failed: 500
```

---

## Summary of Changes

| Component | Change | Impact |
|-----------|--------|--------|
| Backend sync_service.py | Fix SQLite path resolution, add logging | Enables PostgreSQL→SQLite sync |
| Backend user_controller.py | Add logging to sync calls | Visibility into sync operations |
| Backend internal_routes.py | Add sync-status endpoint | Ability to verify sync health |
| Desktop manage_users_page.py | Add backend POST on role change | Enables Desktop→PostgreSQL sync |
| Desktop manage_users_page.py | Add fallback HTTP sync timer | Fallback if MQTT fails |
| Desktop user_sync_service.py | Add logging to MQTT handler | Visibility into MQTT sync |

---

## Expected Result

After implementing these fixes:

1. **Web→Desktop:** Admin changes role on web → PostgreSQL updated → SQLite updated → MQTT published → Desktop receives → Desktop SQLite updated → Desktop UI refreshes

2. **Desktop→Web:** Admin changes role on desktop → Desktop SQLite updated → POST to backend → PostgreSQL updated → MQTT published → All desktops receive → All desktops update

3. **Fallback:** If MQTT fails → Desktop periodic HTTP fetch → Detects role mismatch → Updates SQLite → Refreshes UI

All operations will be logged for debugging and verification.
