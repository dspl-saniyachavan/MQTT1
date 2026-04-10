# User Role Update Fix - Quick Implementation Guide

## Problem
When admin edits user role in frontend/desktop, the role is NOT syncing to both databases (PostgreSQL and SQLite).

## Root Cause
Frontend was making a redundant call to `/api/internal/sync-user-role` (which is meant for desktop-to-backend sync) AFTER already calling `/api/users/{id}` which handles everything. This caused race conditions and confusion.

## Solution

### Step 1: Update Frontend (CRITICAL)
**File:** `dspl-precision-pulse-frontend/src/app/users/content.tsx`

**Changes:**
- Remove redundant `/api/internal/sync-user-role` call
- Use response data from backend instead of local state
- Properly handle role updates

**Key Fix:**
```typescript
// BEFORE (WRONG):
if (editingId) {
    const user = users.find(u => u.id === editingId);
    if (user) {
        try {
            await fetch(`${BACKEND}/api/internal/sync-user-role`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: user.email, role: formData.role }),
            });
        } catch { /* ignore sync errors */ }
    }
    setUsers(users.map(u => u.id === editingId ? { ...u, role: formData.role } : u));
}

// AFTER (CORRECT):
if (editingId) {
    const updatedUser = await res.json();
    setUsers(users.map(u => u.id === editingId ? {
        ...u,
        role: updatedUser.role,
        name: updatedUser.name,
        isActive: updatedUser.is_active
    } : u));
}
```

### Step 2: Verify Backend (Already Correct ✓)
**File:** `dspl-precision-pulse-backend/app/controllers/user_controller.py`

The backend `update_user()` method already:
- ✓ Updates PostgreSQL
- ✓ Syncs to SQLite
- ✓ Publishes MQTT event
- ✓ Broadcasts WebSocket update
- ✓ Sends remote command to desktop

**No changes needed.**

### Step 3: Verify Desktop (Already Correct ✓)
**File:** `dspl-precision-pulse-desktop/src/ui/manage_users_page.py`

The desktop app already:
- ✓ Updates local SQLite
- ✓ Calls `/api/internal/sync-user-role` to sync to backend
- ✓ Publishes MQTT update

**No changes needed.**

## Deployment Steps

### 1. Update Frontend
```bash
cd /home/saniyachavani/Documents/PrecisionpulseDocs/dspl-precision-pulse-frontend

# The file has already been updated
# Just rebuild and restart
npm run build
```

### 2. Restart Services
```bash
# Restart frontend
systemctl restart precision-pulse-frontend

# Backend doesn't need restart (no changes)
# Desktop doesn't need restart (no changes)
```

### 3. Verify in Browser
```
1. Open http://localhost:3000/users
2. Click Edit on any user
3. Change role to "admin"
4. Click Update
5. Verify role updates immediately
```

## Testing Procedure

### Test 1: Frontend Role Update
```
Step 1: Open Frontend → User Management
Step 2: Click Edit on a user (e.g., "John Doe")
Step 3: Change role from "user" to "admin"
Step 4: Click Update

Expected Results:
✓ Frontend UI updates immediately
✓ Role badge changes to purple (admin)
✓ Backend PostgreSQL updated (verify with: SELECT * FROM users WHERE email='john@example.com';)
✓ Desktop SQLite updated (verify with: SELECT * FROM users WHERE email='john@example.com';)
✓ MQTT event published (check backend logs for: "User role updated")
✓ WebSocket broadcast received (check browser console)
```

### Test 2: Desktop Role Update
```
Step 1: Open Desktop App → Manage Users
Step 2: Click Edit Role on a user
Step 3: Change role to "admin"
Step 4: Click Save

Expected Results:
✓ Desktop SQLite updated
✓ Backend PostgreSQL updated
✓ Frontend UI updates within 2 seconds
✓ MQTT event published
```

### Test 3: Cross-Layer Verification
```
Step 1: Update role in Frontend
Step 2: Check Desktop app - role should update within 2 seconds
Step 3: Check Backend database - role should be updated
Step 4: Restart all apps and verify role persists
```

## Verification Checklist

After deployment, verify:

- [ ] Frontend can edit user role
- [ ] Role updates in PostgreSQL database
- [ ] Role updates in SQLite database (desktop)
- [ ] MQTT broadcasts role change event
- [ ] WebSocket updates frontend in real-time
- [ ] Desktop receives MQTT update
- [ ] Role persists after app restart
- [ ] No errors in backend logs
- [ ] No console errors in browser
- [ ] Desktop app shows updated role

## Troubleshooting

### Issue: Role not updating in frontend
**Solution:** 
- Clear browser cache (Ctrl+Shift+Delete)
- Refresh page (F5)
- Check browser console for errors

### Issue: Role not updating in backend database
**Solution:**
- Check backend logs: `docker logs precision-pulse-backend`
- Verify database connection: `psql -U postgres -d precision_pulse`
- Check if user exists: `SELECT * FROM users WHERE email='test@example.com';`

### Issue: Role not updating in desktop
**Solution:**
- Check desktop logs for MQTT connection errors
- Verify MQTT broker is running: `docker ps | grep mosquitto`
- Check if desktop is subscribed to MQTT topics

### Issue: WebSocket not updating frontend
**Solution:**
- Check Socket.IO connection in browser console
- Verify backend Socket.IO is running: `docker logs precision-pulse-backend | grep Socket`
- Check if frontend is listening to `user_updated` event

## Files Modified

| File | Changes | Status |
|------|---------|--------|
| `dspl-precision-pulse-frontend/src/app/users/content.tsx` | Removed redundant sync call, use response data | ✓ Updated |
| `dspl-precision-pulse-backend/app/controllers/user_controller.py` | No changes needed | ✓ Already correct |
| `dspl-precision-pulse-desktop/src/ui/manage_users_page.py` | No changes needed | ✓ Already correct |

## Summary

**Total Changes:** 1 file updated
**Deployment Time:** ~5 minutes
**Testing Time:** ~10 minutes
**Total Time:** ~15 minutes

The fix removes the redundant sync call from the frontend and ensures the backend's response data is used to update the UI. This eliminates race conditions and ensures proper synchronization across all three layers (Frontend → Backend → Desktop).
