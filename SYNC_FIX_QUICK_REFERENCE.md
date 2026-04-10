# User Sync Fix - Quick Reference

## The Problem in 30 Seconds

Users table updates are NOT syncing between PostgreSQL (backend) and SQLite (desktop) because:

1. **Backend can't find desktop's SQLite** - Wrong path
2. **Desktop doesn't tell backend about changes** - No POST request
3. **No error messages** - Failures happen silently
4. **No fallback** - If MQTT fails, nothing happens

## The Solution in 30 Seconds

1. **Fix SQLite path** - Use environment variable
2. **Add backend sync** - Desktop POSTs role changes to backend
3. **Add logging** - See what's happening
4. **Add fallback** - HTTP sync every 30 seconds

## Files to Modify

### Backend (3 files)
1. `app/services/sync_service.py` - Fix SQLite path, add logging
2. `app/controllers/user_controller.py` - Add logging to sync calls
3. `app/routes/internal_routes.py` - Add sync-status endpoint

### Desktop (2 files)
1. `src/ui/manage_users_page.py` - Add backend POST, add fallback sync
2. `src/services/user_sync_service.py` - Add logging

## Key Code Changes

### Backend - sync_service.py
```python
# Use environment variable for SQLite path
env_path = os.environ.get('SQLITE_DB_PATH')
if env_path:
    self.sqlite_path = env_path

# Add logging
logger.info(f"[SYNC_SERVICE] Syncing user {user_data['email']} role={user_data['role']} to SQLite")
```

### Desktop - manage_users_page.py
```python
# After updating SQLite, POST to backend
response = requests.put(
    "http://localhost:5000/api/internal/sync-user-role",
    json={"email": user['email'], "role": user_data['role']},
    headers={"Authorization": f"Bearer {token}"},
    timeout=5
)

# Add fallback sync timer
self._role_sync_timer = QTimer()
self._role_sync_timer.timeout.connect(self._sync_roles_from_backend)
self._role_sync_timer.start(30000)
```

## How to Verify It Works

### Test 1: Check Backend Can Find SQLite
```bash
curl http://localhost:5000/api/internal/sync-status
# Should return: {"status": "ok", "user_count": X}
```

### Test 2: Web→Desktop Sync
```
1. Create user on web
2. Check desktop SQLite: SELECT * FROM users WHERE email='newuser@example.com'
3. Should exist with correct role
```

### Test 3: Desktop→Web Sync
```
1. Login on desktop as admin
2. Change user role in Manage Users
3. Check web dashboard - role should update
4. Check backend logs for: "[MANAGE_USERS] Synced role to backend"
```

### Test 4: MQTT Sync
```
1. Change role on web
2. Check desktop console for: "[USER_SYNC] Processing role_changed"
3. Check desktop SQLite for updated role
```

### Test 5: Fallback Sync
```
1. Stop MQTT broker
2. Change role on web
3. Wait 30 seconds
4. Check desktop console for: "[MANAGE_USERS] Role sync from backend"
5. Desktop UI should update
```

## Console Log Indicators

### Success
```
[SYNC_SERVICE] Syncing user testuser@example.com role=admin to SQLite
[MANAGE_USERS] Synced role to backend: testuser@example.com -> admin
[USER_SYNC] Processing role_changed: testuser@example.com user -> admin
[MANAGE_USERS] Role sync from backend: testuser@example.com -> admin
```

### Failure
```
[SYNC_SERVICE] SQLite database not found at /app/data/precision_pulse.db
[MANAGE_USERS] Backend sync failed: 500
[USER_SYNC] Failed to update SQLite: testuser@example.com
```

## Docker Setup

Add to docker-compose.yml:
```yaml
services:
  backend:
    environment:
      - SQLITE_DB_PATH=/shared/data/precision_pulse.db
    volumes:
      - ./data:/shared/data
```

## Expected Behavior After Fix

| Scenario | Before | After |
|----------|--------|-------|
| Admin changes role on web | Desktop doesn't update | Desktop updates via MQTT or HTTP fallback |
| Admin changes role on desktop | Backend doesn't update | Backend updates via POST request |
| MQTT fails | No sync happens | HTTP fallback syncs every 30s |
| User logs in | Role might be wrong | Role synced from backend on login |

## Implementation Order

1. Fix backend SQLite path (sync_service.py)
2. Add logging to backend (user_controller.py, sync_service.py)
3. Add sync-status endpoint (internal_routes.py)
4. Add backend POST to desktop (manage_users_page.py)
5. Add fallback HTTP sync to desktop (manage_users_page.py)
6. Add logging to desktop (user_sync_service.py)
7. Test all scenarios

## Troubleshooting

| Issue | Check |
|-------|-------|
| SQLite not found | `curl http://localhost:5000/api/internal/sync-status` |
| Role not syncing | Check console logs for `[SYNC_SERVICE]` messages |
| Backend POST fails | Check desktop console for `[MANAGE_USERS] Backend sync failed` |
| MQTT not working | Check desktop console for `[USER_SYNC] Processing role_changed` |
| Fallback not working | Check desktop console for `[MANAGE_USERS] Role sync from backend` |

## Files Reference

- **Root Cause Analysis:** `USER_SYNC_ROOT_CAUSE_ANALYSIS.md`
- **Implementation Guide:** `SYNC_FIX_IMPLEMENTATION.md`
- **This Quick Reference:** `SYNC_FIX_QUICK_REFERENCE.md`
