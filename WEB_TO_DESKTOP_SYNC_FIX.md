# Web-to-Desktop Role Update Sync Issue - Diagnostic & Fix

## Problem Statement

**Issue:** When admin edits user role from **desktop**, it updates in **web** ✓  
But when admin edits user role from **web**, it does NOT update in **desktop** ✗

**Impact:** One-way sync only (Desktop → Web works, Web → Desktop broken)

---

## Root Cause Analysis

### Current Flow Analysis

#### Desktop → Web (WORKS ✓)
```
Desktop Edit Role
    ↓
PUT /api/internal/sync-user-role
    ↓
Backend: sync_user_role()
    ├─ Updates PostgreSQL ✓
    ├─ Publishes MQTT: publish_role_changed() ✓
    │  Topic: precisionpulse/sync/roles/changed
    │  Payload: { type: 'role_changed', user_id, email, old_role, new_role }
    │
    └─ Broadcasts WebSocket: user_updated ✓
    ↓
Frontend receives WebSocket ✓
Frontend updates UI ✓
```

#### Web → Desktop (BROKEN ✗)
```
Frontend Edit Role
    ↓
PUT /api/users/{id}
    ↓
Backend: UserController.update_user()
    ├─ Updates PostgreSQL ✓
    ├─ Publishes MQTT: publish_user_updated() ✓
    │  Topic: precisionpulse/sync/users/updated
    │  Payload: { type: 'user_updated', user: {...} }
    │
    ├─ ALSO Publishes MQTT: publish_role_changed() ✓
    │  Topic: precisionpulse/sync/roles/changed
    │  Payload: { type: 'role_changed', user_id, email, old_role, new_role }
    │
    └─ Broadcasts WebSocket: user_updated ✓
    ↓
Desktop receives MQTT messages ✓
    ├─ Message 1: precisionpulse/sync/users/updated
    │  Handler: 'sync/users/updated' in topic → user_updated.emit()
    │  Updates SQLite ✓
    │
    └─ Message 2: precisionpulse/sync/roles/changed
       Handler: 'sync/roles/changed' in topic → role_changed.emit()
       Updates SQLite ✓
    ↓
Desktop UI should update ✓
```

### Why It's Not Working

The backend IS publishing both messages correctly. The desktop IS subscribing to both topics. But the desktop UI is NOT updating.

**Possible causes:**
1. Desktop UI is not listening to the `user_updated` or `role_changed` signals
2. Desktop UI is not refreshing the table after receiving the signal
3. The signal is being emitted but not connected to the UI update method

---

## Investigation Steps

### Step 1: Check Desktop UI Connection to Signals

**File:** `dspl-precision-pulse-desktop/src/ui/manage_users_page.py`

Need to verify:
1. Is `user_sync_service` connected to the page?
2. Are signals connected to refresh methods?

### Step 2: Check Signal Emission

**File:** `dspl-precision-pulse-desktop/src/services/user_sync_service.py`

The signals ARE being emitted:
- Line 95: `self.user_updated.emit(user)`
- Line 113: `self.role_changed.emit(user_id, email, old_role, new_role)`

### Step 3: Check MQTT Message Reception

**File:** `dspl-precision-pulse-desktop/src/services/mqtt_service.py`

The MQTT service IS subscribing:
- Line 56: `self.client.subscribe("precisionpulse/sync/users/#")`
- Line 57: `self.client.subscribe("precisionpulse/sync/roles/#")`

---

## Solution

### Fix 1: Ensure Desktop UI Connects to Signals

**File:** `dspl-precision-pulse-desktop/src/ui/manage_users_page.py`

Add signal connections in `__init__`:

```python
def __init__(self, db_manager=None, auth_service=None, sync_service=None):
    super().__init__()
    self.db = db_manager
    self.auth_service = auth_service
    self.sync_service = sync_service
    self.users = []
    self._logged_in_emails: set = set()
    self._user_page = 1
    self._user_page_size = 15
    
    # ... existing code ...
    
    # CRITICAL: Connect sync service signals to UI update methods
    if sync_service:
        sync_service.user_updated.connect(self._on_user_updated)
        sync_service.role_changed.connect(self._on_role_changed)
        sync_service.user_created.connect(self._on_user_created)
        sync_service.user_deleted.connect(self._on_user_deleted)
        print("[MANAGE_USERS] Connected to sync service signals")
    
    self.setup_ui()
    self.load_users()
```

### Fix 2: Add Signal Handlers

**File:** `dspl-precision-pulse-desktop/src/ui/manage_users_page.py`

Add these methods to the `ManageUsersPage` class:

```python
def _on_user_updated(self, user_data: dict):
    """Handle user updated signal from sync service"""
    try:
        print(f"[MANAGE_USERS] User updated signal received: {user_data.get('email')}")
        # Update local users list
        for i, u in enumerate(self.users):
            if u['email'] == user_data.get('email'):
                self.users[i] = {
                    'id': user_data.get('id', u['id']),
                    'email': user_data.get('email', u['email']),
                    'name': user_data.get('name', u['name']),
                    'role': user_data.get('role', u['role']),
                    'is_active': user_data.get('is_active', u['is_active'])
                }
                print(f"[MANAGE_USERS] Updated user in list: {user_data.get('email')}")
                break
        # Refresh table to show updated data
        self.refresh_table()
    except Exception as e:
        print(f"[MANAGE_USERS] Error handling user updated: {e}")

def _on_role_changed(self, user_id: int, email: str, old_role: str, new_role: str):
    """Handle role changed signal from sync service"""
    try:
        print(f"[MANAGE_USERS] Role changed signal received: {email} ({old_role} -> {new_role})")
        # Update local users list
        for i, u in enumerate(self.users):
            if u['email'] == email:
                u['role'] = new_role
                print(f"[MANAGE_USERS] Updated role in list: {email} -> {new_role}")
                break
        # Refresh table to show updated role
        self.refresh_table()
    except Exception as e:
        print(f"[MANAGE_USERS] Error handling role changed: {e}")

def _on_user_created(self, user_data: dict):
    """Handle user created signal from sync service"""
    try:
        print(f"[MANAGE_USERS] User created signal received: {user_data.get('email')}")
        # Add new user to list
        self.users.append({
            'id': user_data.get('id'),
            'email': user_data.get('email'),
            'name': user_data.get('name'),
            'role': user_data.get('role', 'user'),
            'is_active': user_data.get('is_active', True)
        })
        # Refresh table
        self.refresh_table()
    except Exception as e:
        print(f"[MANAGE_USERS] Error handling user created: {e}")

def _on_user_deleted(self, user_id: int, email: str):
    """Handle user deleted signal from sync service"""
    try:
        print(f"[MANAGE_USERS] User deleted signal received: {email}")
        # Remove user from list
        self.users = [u for u in self.users if u['email'] != email]
        # Refresh table
        self.refresh_table()
    except Exception as e:
        print(f"[MANAGE_USERS] Error handling user deleted: {e}")
```

### Fix 3: Ensure Signals Are Properly Defined

**File:** `dspl-precision-pulse-desktop/src/services/user_sync_service.py`

Verify signals are defined (they already are, lines 18-23):

```python
user_created = Signal(dict)
user_updated = Signal(dict)
user_deleted = Signal(int, str)  # user_id, email
role_changed = Signal(int, str, str, str)  # user_id, email, old_role, new_role
permission_changed = Signal(str, list)  # role, permissions
sync_error = Signal(str)
```

✓ Already correct

---

## Testing Procedure

### Test 1: Web to Desktop Role Update

```
1. Open Frontend → User Management
2. Click Edit on a user (e.g., "John Doe")
3. Change role to "admin"
4. Click Update

Expected Results:
✓ Frontend UI updates immediately
✓ Backend PostgreSQL updated
✓ Backend publishes MQTT messages
✓ Desktop receives MQTT messages
✓ Desktop SQLite updated
✓ Desktop UI updates within 2 seconds
✓ Role badge changes to purple (admin)
```

### Test 2: Desktop to Web Role Update (Verify Still Works)

```
1. Open Desktop → Manage Users
2. Click Edit Role on a user
3. Change role to "admin"
4. Click Save

Expected Results:
✓ Desktop SQLite updated
✓ Backend PostgreSQL updated
✓ Frontend UI updates within 2 seconds
✓ Role badge changes to purple (admin)
```

### Test 3: Verify Signals Are Connected

```
1. Open Desktop app
2. Check console logs for: "[MANAGE_USERS] Connected to sync service signals"
3. Edit a user role from web
4. Check console logs for: "[MANAGE_USERS] Role changed signal received"
5. Verify table refreshes
```

---

## Debugging Commands

### Check MQTT Messages

```bash
# Subscribe to all sync topics
mosquitto_sub -h localhost -p 18883 \
  -t "precisionpulse/sync/#" \
  --cafile /path/to/ca.crt

# Expected when web updates role:
# Topic: precisionpulse/sync/users/updated
# Payload: { type: 'user_updated', user: {...} }
#
# Topic: precisionpulse/sync/roles/changed
# Payload: { type: 'role_changed', user_id, email, old_role, new_role }
```

### Check Desktop Logs

```bash
# Look for signal connection messages
grep "Connected to sync service signals" desktop.log

# Look for signal reception messages
grep "Role changed signal received" desktop.log

# Look for table refresh messages
grep "Updated role in list" desktop.log
```

### Check Backend Logs

```bash
# Look for MQTT publish messages
docker logs precision-pulse-backend | grep "MQTT_PUB"

# Look for role change logs
docker logs precision-pulse-backend | grep "role"
```

---

## Files to Update

| File | Changes | Priority |
|------|---------|----------|
| `dspl-precision-pulse-desktop/src/ui/manage_users_page.py` | Add signal connections and handlers | CRITICAL |
| `dspl-precision-pulse-desktop/src/services/user_sync_service.py` | Already correct | - |
| `dspl-precision-pulse-backend/app/controllers/user_controller.py` | Already correct | - |
| `dspl-precision-pulse-backend/app/services/mqtt_publisher.py` | Already correct | - |

---

## Deployment

### Step 1: Update Desktop UI

```bash
# Update manage_users_page.py with signal connections and handlers
# File: dspl-precision-pulse-desktop/src/ui/manage_users_page.py
```

### Step 2: Restart Desktop App

```bash
# Restart the desktop application
# The signal connections will be established on startup
```

### Step 3: Test

```
1. Edit user role from web
2. Verify desktop UI updates within 2 seconds
3. Check console logs for signal messages
```

---

## Expected Behavior After Fix

### Web → Desktop Flow (After Fix)

```
Frontend Edit Role
    ↓
PUT /api/users/{id}
    ↓
Backend: UserController.update_user()
    ├─ Updates PostgreSQL ✓
    ├─ Publishes MQTT messages ✓
    └─ Broadcasts WebSocket ✓
    ↓
Desktop receives MQTT messages ✓
    ├─ Emits user_updated signal ✓
    ├─ Emits role_changed signal ✓
    ↓
Desktop UI signal handlers triggered ✓
    ├─ _on_user_updated() ✓
    ├─ _on_role_changed() ✓
    ↓
Desktop SQLite updated ✓
Desktop table refreshed ✓
Desktop UI shows new role ✓
```

---

## Summary

**Root Cause:** Desktop UI is not connected to the sync service signals, so even though MQTT messages are received and SQLite is updated, the UI doesn't refresh.

**Solution:** Connect the sync service signals to UI update methods in the `ManageUsersPage` class.

**Files to Update:** 1 (manage_users_page.py)

**Deployment Time:** ~5 minutes

**Testing Time:** ~10 minutes

**Total Time:** ~15 minutes

---

## Verification Checklist

- [ ] Signal connections added to ManageUsersPage.__init__()
- [ ] Signal handlers (_on_user_updated, _on_role_changed, etc.) added
- [ ] Desktop app restarted
- [ ] Web-to-desktop role update tested
- [ ] Desktop-to-web role update still works
- [ ] Console logs show signal messages
- [ ] Desktop UI updates within 2 seconds
- [ ] SQLite database updated
- [ ] No errors in logs
