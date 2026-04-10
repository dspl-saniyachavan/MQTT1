# User Sync Issues - Root Cause Analysis & Fixes

## Issues Identified

### Issue 1: SQLite Path Not Found
**Problem:** Backend's `sync_service` tries to sync to SQLite but the path is wrong
- Backend looks for SQLite at: `/app/data/precision_pulse.db` (Docker) or sibling `data/` directory
- Desktop creates SQLite at: `data/precision_pulse.db` (relative to desktop app)
- These paths don't match → sync fails silently

**Solution:** Use environment variable `SQLITE_DB_PATH` to point to correct location

### Issue 2: Desktop → PostgreSQL Sync Missing
**Problem:** When desktop updates user role, it only updates local SQLite
- Desktop calls `edit_user()` → updates SQLite only
- Backend never receives the update
- No MQTT message published from desktop

**Solution:** Desktop must POST to backend `/api/internal/sync-user-role` endpoint

### Issue 3: PostgreSQL → SQLite Sync Not Triggered
**Problem:** Backend's `sync_service.sync_user_to_sqlite()` is called but SQLite path is wrong
- Even if called, it fails because SQLite path doesn't exist
- No error handling or retry logic

**Solution:** 
1. Fix SQLite path resolution
2. Add error logging
3. Add retry mechanism

### Issue 4: MQTT Role Change Not Reaching Desktop
**Problem:** Backend publishes role_changed to MQTT but desktop doesn't process it
- Desktop subscribes to `precisionpulse/sync/roles/#` but handler might not be triggered
- No logging to verify message receipt

**Solution:** Add comprehensive logging at each step

### Issue 5: No Bidirectional Sync Verification
**Problem:** No way to verify if sync actually happened
- No status endpoint to check sync health
- No audit trail of sync operations

**Solution:** Add sync status endpoint and logging

---

## Implementation Plan

### Step 1: Fix SQLite Path Resolution (Backend)
- Use shared Docker volume path
- Add environment variable support
- Add fallback paths

### Step 2: Add Desktop → Backend Sync (Desktop)
- When user edits role, POST to `/api/internal/sync-user-role`
- Wait for response before updating UI
- Add error handling

### Step 3: Enhance Logging (Both)
- Log every sync operation
- Log failures with reasons
- Add debug mode

### Step 4: Add Sync Verification (Backend)
- Add `/api/internal/sync-status` endpoint
- Return SQLite connection status
- Return user count comparison

### Step 5: Add Fallback Sync (Desktop)
- Periodic HTTP fetch of users from backend
- Compare roles and update if different
- Run every 30 seconds

---

## Files to Modify

1. **Backend:**
   - `app/services/sync_service.py` - Fix SQLite path, add logging
   - `app/controllers/user_controller.py` - Already has sync calls, just needs logging
   - `app/routes/internal_routes.py` - Add sync status endpoint

2. **Desktop:**
   - `src/ui/manage_users_page.py` - Add POST to backend on role change
   - `src/services/user_sync_service.py` - Add fallback HTTP sync
   - `src/services/mqtt_service.py` - Add logging for message receipt

---

## Expected Behavior After Fix

### Scenario 1: Admin Changes User Role on Web
```
Web Dashboard (admin changes role)
    ↓
Backend PostgreSQL updated
    ↓
sync_service.sync_user_to_sqlite() called
    ↓
SQLite updated (via shared Docker volume)
    ↓
MQTT publish: precisionpulse/sync/roles/changed
    ↓
Desktop receives MQTT message
    ↓
UserSyncService updates SQLite
    ↓
ManageUsersPage refreshes UI
    ↓
Desktop shows new role
```

### Scenario 2: Desktop Admin Changes User Role
```
Desktop Manage Users page (admin changes role)
    ↓
POST /api/internal/sync-user-role
    ↓
Backend PostgreSQL updated
    ↓
sync_service.sync_user_to_sqlite() called
    ↓
SQLite updated
    ↓
MQTT publish: precisionpulse/sync/roles/changed
    ↓
All connected desktops receive update
    ↓
All desktops update UI
```

### Scenario 3: MQTT Fails
```
Admin changes role on web
    ↓
Backend updates PostgreSQL & SQLite
    ↓
MQTT publish fails (broker down)
    ↓
Desktop periodic sync (every 30s) fetches users via HTTP
    ↓
Desktop detects role mismatch
    ↓
Desktop updates SQLite
    ↓
Desktop UI refreshes
```

---

## Testing Steps

### Test 1: Verify SQLite Path
```bash
# Check backend can find SQLite
curl http://localhost:5000/api/internal/sync-status
# Should return: {"status": "ok", "user_count": X, "parameter_count": Y}
```

### Test 2: Web → Desktop Sync
```
1. Create user on web: testuser@example.com
2. Check desktop SQLite: SELECT * FROM users WHERE email='testuser@example.com'
3. Should exist with correct role
```

### Test 3: Desktop → Web Sync
```
1. Login on desktop as admin
2. Change testuser role from "user" to "admin"
3. Check web dashboard: User should show as "admin"
4. Check backend PostgreSQL: SELECT role FROM users WHERE email='testuser@example.com' should be 'admin'
```

### Test 4: MQTT Sync
```
1. Change role on web
2. Check desktop console for: "[USER_SYNC] Role change detected:"
3. Check desktop SQLite for updated role
4. Check desktop UI for updated role badge
```

### Test 5: Fallback HTTP Sync
```
1. Stop MQTT broker
2. Change role on web
3. Wait 30 seconds
4. Check desktop console for: "[MANAGE_USERS] Role sync from backend:"
5. Check desktop UI for updated role
```
