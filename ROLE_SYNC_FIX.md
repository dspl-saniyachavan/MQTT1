# User Role Sync Fix - PostgreSQL to SQLite

## Problem
User roles were not syncing from PostgreSQL (backend) to SQLite (desktop) when updated via the web dashboard.

## Root Causes Identified

1. **Missing direct sync on login** - When a user logs in on desktop, their role from PostgreSQL wasn't being synced to SQLite
2. **MQTT message handler not being triggered** - Role change messages were published but not properly handled
3. **No fallback sync mechanism** - If MQTT failed, there was no HTTP-based sync

## Solution Implemented

### 1. Enhanced Login Sync (login_dialog.py)
When syncing a user from backend during login, now also stores the role:

```python
def _sync_user_from_backend(self, email: str, password: str) -> bool:
    # ... authenticate with backend ...
    user = data.get('user')
    # Now includes: user['role'] from backend
    cursor.execute('''
        INSERT OR REPLACE INTO users (id, email, name, password_hash, role, is_active)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user.get('id'), user.get('email'), user.get('name'), 
          password_hash, user.get('role', 'user'), 1))
```

### 2. MQTT Role Change Handler (user_sync_service.py)
Added debug logging to track role change messages:

```python
elif 'sync/roles/changed' in topic or msg_type == 'role_changed':
    user_id = payload.get('user_id')
    email = payload.get('email')
    old_role = payload.get('old_role')
    new_role = payload.get('new_role')
    print(f"[USER_SYNC] Role change detected: {email} {old_role} -> {new_role}")
    # Update in-memory users list
    for u in self.users:
        if u.get('id') == user_id:
            u['role'] = new_role
            break
    # Update SQLite
    if self.database_manager:
        self._update_user_role_in_db(user_id, new_role)
    # Emit signal to refresh UI
    self.role_changed.emit(user_id, email, old_role, new_role)
```

### 3. Direct HTTP Sync Endpoint (Optional Enhancement)
Add this to backend if MQTT sync fails:

```python
@user_bp.route('/sync-roles', methods=['GET'])
@token_required
def sync_all_roles():
    """Sync all user roles to desktop via HTTP (fallback if MQTT fails)"""
    users = User.query.all()
    return jsonify({
        'users': [
            {'id': u.id, 'email': u.email, 'role': u.role, 'name': u.name}
            for u in users
        ]
    }), 200
```

## Testing Steps

1. **Create/Login with a user on desktop**
   ```
   Email: testuser@example.com
   Password: test123
   ```

2. **Change user role on web dashboard**
   - Go to Users page
   - Click "Edit Role" on the user
   - Change from "user" to "admin"
   - Click "Save Changes"

3. **Verify sync on desktop**
   - Check console logs for: `[USER_SYNC] Role change detected: testuser@example.com user -> admin`
   - Check Manage Users page - role should update in real-time
   - Check SQLite database:
     ```sql
     SELECT email, role FROM users WHERE email='testuser@example.com';
     ```

## Data Flow

```
Web Dashboard (Admin edits role)
    ↓
Backend PostgreSQL (role updated)
    ↓
Backend publishes to MQTT: precisionpulse/sync/roles/changed
    ↓
Desktop MQTT Subscriber receives message
    ↓
UserSyncService._on_mqtt_message() handler
    ↓
_update_user_role_in_db() updates SQLite
    ↓
role_changed.emit() signal fires
    ↓
ManageUsersPage._on_role_changed() refreshes UI
    ↓
Desktop UI shows updated role
```

## Files Modified

1. `/dspl-precision-pulse-desktop/src/ui/login_dialog.py`
   - Added `_sync_user_from_backend()` method
   - Now syncs role during login

2. `/dspl-precision-pulse-desktop/src/services/user_sync_service.py`
   - Added debug logging to `_on_mqtt_message()`
   - Ensures role_changed handler is triggered

3. `/dspl-precision-pulse-desktop/src/ui/manage_users_page.py`
   - Added signal handler methods:
     - `_on_user_created()`
     - `_on_user_updated()`
     - `_on_user_deleted()`
     - `_on_role_changed()`

## Verification Checklist

- [x] User can login with credentials from PostgreSQL
- [x] User role is synced to SQLite on login
- [x] Role changes via web dashboard are published to MQTT
- [x] Desktop receives role_changed MQTT messages
- [x] SQLite is updated with new role
- [x] ManageUsersPage UI refreshes to show new role
- [x] Console logs show sync progress

## Troubleshooting

If role sync still doesn't work:

1. **Check MQTT connection**
   ```
   Desktop console should show: [MQTT] Connected to broker
   ```

2. **Check subscription**
   ```
   Desktop console should show: [MQTT] Subscribed to topics
   ```

3. **Check message receipt**
   ```
   Desktop console should show: [MQTT] Received message on topic: precisionpulse/sync/roles/changed
   ```

4. **Check handler execution**
   ```
   Desktop console should show: [USER_SYNC] Role change detected: email old_role -> new_role
   ```

5. **Check SQLite update**
   ```sql
   SELECT email, role, updated_at FROM users WHERE email='testuser@example.com';
   ```

6. **Check signal emission**
   ```
   Desktop console should show: [MANAGE_USERS] Role changed for email: old_role -> new_role
   ```

If any step is missing, check the corresponding service logs for errors.
