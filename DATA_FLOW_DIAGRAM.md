# User Role Update - Complete Data Flow

## Correct Flow (After Fix)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React/Next.js)                            │
│                                                                             │
│  User clicks "Edit" → Opens Modal → Changes role → Clicks "Update"        │
│                                                                             │
│  handleSubmit() {                                                          │
│    PUT /api/users/{id} with { role: "admin" }                             │
│  }                                                                          │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 │ HTTP PUT Request
                                 │ { role: "admin" }
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    BACKEND (Flask/Python)                                   │
│                                                                             │
│  PUT /api/users/{id}                                                       │
│    ↓                                                                        │
│  UserController.update_user()                                              │
│    ├─ Update PostgreSQL: user.role = "admin" ✓                            │
│    ├─ Sync to SQLite: sync_user_to_sqlite() ✓                            │
│    ├─ Publish MQTT: mqtt_pub.publish_user_updated() ✓                    │
│    ├─ Broadcast WebSocket: socketio.emit('user_updated') ✓               │
│    └─ Send remote command: remote_commands_service.send_user_sync_command() ✓
│                                                                             │
│  Response: { id, email, name, role: "admin", is_active, ... }            │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
         HTTP Response    MQTT Publish   WebSocket Broadcast
         (JSON)           (MQTT)         (Socket.IO)
                    │            │            │
                    ▼            ▼            ▼
        ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
        │ FRONTEND         │  │ DESKTOP (MQTT)   │  │ FRONTEND         │
        │ (HTTP Response)  │  │ (MQTT Subscriber)│  │ (WebSocket)      │
        │                  │  │                  │  │                  │
        │ const updated =  │  │ Receives:        │  │ Receives:        │
        │   await res.json()│  │ {                │  │ {                │
        │                  │  │   type: 'role_   │  │   user: {        │
        │ setUsers(users   │  │   changed',      │  │     id, email,   │
        │   .map(u =>      │  │   email,         │  │     role: "admin"│
        │   u.id ===       │  │   old_role,      │  │   }              │
        │   editingId ?    │  │   new_role       │  │ }                │
        │   {             │  │ }                │  │                  │
        │     ...u,        │  │                  │  │ setUsers(prev =>  │
        │     role:        │  │ Updates SQLite:  │  │   prev.map(u =>   │
        │     updated.role │  │ UPDATE users SET │  │   u.id === id ?   │
        │   } : u          │  │ role = "admin"   │  │   {...u,          │
        │ ))               │  │ WHERE email=...  │  │    role: "admin"} │
        │                  │  │                  │  │   : u             │
        │ UI Updates ✓     │  │ Publishes MQTT   │  │ ))                │
        │                  │  │ to other clients │  │                  │
        │                  │  │                  │  │ UI Updates ✓      │
        └──────────────────┘  └──────────────────┘  └──────────────────┘
```

## Data Sync Layers

### Layer 1: PostgreSQL (Backend Primary Database)
```
User Table:
┌────┬──────────────────┬──────────┬────────┐
│ id │ email            │ name     │ role   │
├────┼──────────────────┼──────────┼────────┤
│ 1  │ admin@...        │ Admin    │ admin  │
│ 2  │ john@example.com │ John Doe │ admin  │ ← Updated
│ 3  │ jane@example.com │ Jane Doe │ user   │
└────┴──────────────────┴──────────┴────────┘

Updated by: UserController.update_user()
Sync method: Direct database update
Timing: Immediate
```

### Layer 2: SQLite (Desktop Local Database)
```
User Table:
┌────┬──────────────────┬──────────┬────────┐
│ id │ email            │ name     │ role   │
├────┼──────────────────┼──────────┼────────┤
│ 1  │ admin@...        │ Admin    │ admin  │
│ 2  │ john@example.com │ John Doe │ admin  │ ← Updated
│ 3  │ jane@example.com │ Jane Doe │ user   │
└────┴──────────────────┴──────────┴────────┘

Updated by: sync_user_to_sqlite() (from backend)
Sync method: HTTP request from backend
Timing: Within 1 second
```

### Layer 3: Frontend UI (React State)
```
users = [
  { id: "1", email: "admin@...", name: "Admin", role: "admin" },
  { id: "2", email: "john@...", name: "John Doe", role: "admin" }, ← Updated
  { id: "3", email: "jane@...", name: "Jane Doe", role: "user" }
]

Updated by: handleSubmit() (from HTTP response or WebSocket)
Sync method: HTTP response or Socket.IO event
Timing: Immediate (HTTP) or within 1 second (WebSocket)
```

## Event Flow Timeline

```
T+0ms:   User clicks "Update" button
         ↓
T+10ms:  Frontend sends PUT /api/users/{id}
         ↓
T+50ms:  Backend receives request
         ├─ Updates PostgreSQL
         ├─ Syncs to SQLite
         ├─ Publishes MQTT event
         ├─ Broadcasts WebSocket
         └─ Sends remote command
         ↓
T+100ms: Frontend receives HTTP response
         ├─ Updates local state
         └─ UI re-renders
         ↓
T+100ms: Desktop receives MQTT event
         ├─ Updates SQLite
         └─ Publishes MQTT to other clients
         ↓
T+100ms: Frontend receives WebSocket event
         ├─ Updates local state (redundant but safe)
         └─ UI re-renders (redundant but safe)
         ↓
T+150ms: All layers synchronized ✓
```

## Sync Mechanisms

### 1. HTTP (Frontend → Backend)
```
Frontend                          Backend
   │                                │
   ├─ PUT /api/users/{id}          │
   │  { role: "admin" }            │
   │─────────────────────────────→ │
   │                                ├─ Update PostgreSQL
   │                                ├─ Sync to SQLite
   │                                ├─ Publish MQTT
   │                                ├─ Broadcast WebSocket
   │                                │
   │ ← ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │
   │  { id, email, role, ... }     │
   │                                │
   └─ Update local state            │
```

### 2. MQTT (Backend → Desktop)
```
Backend                           Desktop
   │                                │
   ├─ Publish MQTT event           │
   │  precisionpulse/sync/users/... │
   │─────────────────────────────→ │
   │                                ├─ Receive event
   │                                ├─ Update SQLite
   │                                └─ Publish to other clients
   │                                │
```

### 3. WebSocket (Backend → Frontend)
```
Backend                           Frontend
   │                                │
   ├─ Emit 'user_updated'          │
   │  { user: {...} }              │
   │─────────────────────────────→ │
   │                                ├─ Receive event
   │                                ├─ Update local state
   │                                └─ Re-render UI
   │                                │
```

## Before Fix (BROKEN)

```
Frontend Edit User Role
    ↓
PUT /api/users/{id} with { role: "admin" }
    ↓
Backend updates PostgreSQL ✓
    ↓
Frontend receives response ✓
    ↓
Frontend ALSO calls /api/internal/sync-user-role (WRONG!)
    ↓
Race condition: Two different endpoints updating same user
    ↓
Potential data inconsistency ✗
```

## After Fix (CORRECT)

```
Frontend Edit User Role
    ↓
PUT /api/users/{id} with { role: "admin" }
    ↓
Backend updates PostgreSQL ✓
Backend syncs to SQLite ✓
Backend publishes MQTT ✓
Backend broadcasts WebSocket ✓
    ↓
Frontend receives HTTP response ✓
Frontend updates local state ✓
Frontend re-renders UI ✓
    ↓
Desktop receives MQTT event ✓
Desktop updates SQLite ✓
    ↓
All layers synchronized ✓
```

## Key Points

1. **Single Source of Truth:** Backend PostgreSQL is the primary database
2. **Cascading Sync:** Backend syncs to SQLite, MQTT, and WebSocket
3. **No Redundant Calls:** Frontend only calls `/api/users/{id}`, not `/api/internal/sync-user-role`
4. **Multiple Sync Paths:** 
   - HTTP for immediate frontend response
   - MQTT for desktop sync
   - WebSocket for real-time frontend updates
5. **Idempotent Operations:** Multiple sync paths are safe because they're idempotent

## Verification Commands

### Check PostgreSQL
```bash
psql -U postgres -d precision_pulse
SELECT id, email, name, role FROM users WHERE email='john@example.com';
```

### Check SQLite (Desktop)
```bash
sqlite3 ~/.precision_pulse/desktop.db
SELECT id, email, name, role FROM users WHERE email='john@example.com';
```

### Check MQTT Events
```bash
# Subscribe to MQTT topic
mosquitto_sub -h localhost -p 18883 -t "precisionpulse/sync/users/#" --cafile config/ca.crt
```

### Check Backend Logs
```bash
docker logs precision-pulse-backend | grep "User role updated"
```

### Check Frontend Console
```javascript
// Open browser console (F12)
// Look for WebSocket events
// Should see: user_updated event with updated role
```

## Summary

The fix ensures that when a user role is updated:
1. Backend PostgreSQL is updated immediately
2. Backend syncs to SQLite via HTTP
3. Backend publishes MQTT event for desktop
4. Backend broadcasts WebSocket for frontend
5. All layers receive the update within 100-150ms
6. No race conditions or data inconsistencies
