# User Role Update Fix - Debugging & Verification Commands

## Quick Verification

### 1. Check Frontend is Updated
```bash
# Verify the fix is in place
grep -n "api/internal/sync-user-role" /home/saniyachavani/Documents/PrecisionpulseDocs/dspl-precision-pulse-frontend/src/app/users/content.tsx

# Expected: No results (the redundant call should be removed)
```

### 2. Check Backend Logs
```bash
# View backend logs
docker logs precision-pulse-backend | tail -50

# Look for: "User role updated" messages
# Example: "[SYNC] User role updated: john@example.com (user -> admin)"
```

### 3. Check Frontend Console
```bash
# Open browser console (F12)
# Look for WebSocket events
# Should see: user_updated event with updated role
```

---

## Database Verification

### PostgreSQL (Backend)
```bash
# Connect to PostgreSQL
psql -U postgres -d precision_pulse

# Check user role
SELECT id, email, name, role, is_active FROM users WHERE email='john@example.com';

# Expected output:
# id | email            | name     | role  | is_active
# ---+------------------+----------+-------+-----------
# 2  | john@example.com | John Doe | admin | t

# Check all users
SELECT id, email, name, role FROM users ORDER BY id;

# Exit
\q
```

### SQLite (Desktop)
```bash
# Connect to SQLite
sqlite3 ~/.precision_pulse/desktop.db

# Check user role
SELECT id, email, name, role FROM users WHERE email='john@example.com';

# Expected output:
# 2|john@example.com|John Doe|admin

# Check all users
SELECT id, email, name, role FROM users ORDER BY id;

# Exit
.quit
```

---

## MQTT Verification

### Subscribe to MQTT Events
```bash
# Subscribe to all user sync events
mosquitto_sub -h localhost -p 18883 \
  -t "precisionpulse/sync/users/#" \
  --cafile /path/to/ca.crt

# Expected messages when role is updated:
# {
#   "type": "role_changed",
#   "email": "john@example.com",
#   "old_role": "user",
#   "new_role": "admin",
#   "timestamp": "2024-01-15T10:30:45.123456+00:00",
#   "source": "desktop"
# }
```

### Publish Test MQTT Message
```bash
# Publish a test message
mosquitto_pub -h localhost -p 18883 \
  -t "precisionpulse/sync/users/test" \
  -m '{"test": "message"}' \
  --cafile /path/to/ca.crt
```

---

## API Testing

### Test Frontend API Call
```bash
# Get auth token
TOKEN=$(curl -s -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@precisionpulse.com","password":"admin123"}' \
  | jq -r '.token')

# Get user ID
USER_ID=$(curl -s -X GET http://localhost:5000/api/users \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.[] | select(.email=="john@example.com") | .id')

# Update user role
curl -X PUT http://localhost:5000/api/users/$USER_ID \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"role":"admin"}' \
  | jq .

# Expected response:
# {
#   "id": 2,
#   "email": "john@example.com",
#   "name": "John Doe",
#   "role": "admin",
#   "is_active": true,
#   ...
# }
```

### Test Desktop Sync Endpoint
```bash
# This endpoint is called by desktop app
curl -X PUT http://localhost:5000/api/internal/sync-user-role \
  -H "Content-Type: application/json" \
  -d '{"email":"john@example.com","role":"admin"}' \
  | jq .

# Expected response:
# {
#   "success": true,
#   "message": "User role updated",
#   "email": "john@example.com",
#   "old_role": "user",
#   "new_role": "admin"
# }
```

---

## End-to-End Testing

### Test 1: Frontend Role Update
```bash
#!/bin/bash

echo "=== Test 1: Frontend Role Update ==="

# Get token
TOKEN=$(curl -s -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@precisionpulse.com","password":"admin123"}' \
  | jq -r '.token')

echo "✓ Got auth token"

# Get user ID
USER_ID=$(curl -s -X GET http://localhost:5000/api/users \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.[] | select(.email=="john@example.com") | .id')

echo "✓ Got user ID: $USER_ID"

# Update role via frontend API
RESPONSE=$(curl -s -X PUT http://localhost:5000/api/users/$USER_ID \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"role":"admin"}')

echo "✓ Updated role via API"
echo "Response: $RESPONSE"

# Verify in PostgreSQL
echo ""
echo "Checking PostgreSQL..."
psql -U postgres -d precision_pulse -c \
  "SELECT email, role FROM users WHERE id=$USER_ID;"

# Verify in SQLite
echo ""
echo "Checking SQLite..."
sqlite3 ~/.precision_pulse/desktop.db \
  "SELECT email, role FROM users WHERE id=$USER_ID;"

echo ""
echo "✓ Test 1 Complete"
```

### Test 2: Desktop Role Update
```bash
#!/bin/bash

echo "=== Test 2: Desktop Role Update ==="

# Simulate desktop app calling sync endpoint
RESPONSE=$(curl -s -X PUT http://localhost:5000/api/internal/sync-user-role \
  -H "Content-Type: application/json" \
  -d '{"email":"jane@example.com","role":"admin"}')

echo "✓ Desktop called sync endpoint"
echo "Response: $RESPONSE"

# Verify in PostgreSQL
echo ""
echo "Checking PostgreSQL..."
psql -U postgres -d precision_pulse -c \
  "SELECT email, role FROM users WHERE email='jane@example.com';"

# Verify in SQLite
echo ""
echo "Checking SQLite..."
sqlite3 ~/.precision_pulse/desktop.db \
  "SELECT email, role FROM users WHERE email='jane@example.com';"

echo ""
echo "✓ Test 2 Complete"
```

---

## Log Analysis

### Backend Logs
```bash
# View all user-related logs
docker logs precision-pulse-backend | grep -i "user"

# View role change logs
docker logs precision-pulse-backend | grep -i "role"

# View MQTT logs
docker logs precision-pulse-backend | grep -i "mqtt"

# View WebSocket logs
docker logs precision-pulse-backend | grep -i "socket"

# View last 100 lines
docker logs precision-pulse-backend | tail -100

# Follow logs in real-time
docker logs -f precision-pulse-backend
```

### Desktop Logs
```bash
# View desktop app logs (if running in terminal)
# Look for: "✓ User role synced to backend"
# Look for: "✗ Backend sync failed"

# Check desktop database
sqlite3 ~/.precision_pulse/desktop.db ".tables"
sqlite3 ~/.precision_pulse/desktop.db ".schema users"
```

### Frontend Console
```javascript
// Open browser console (F12)

// Check Socket.IO connection
console.log(socketIOService.socket.connected);

// Listen for user_updated events
socketIOService.on('user_updated', (data) => {
  console.log('User updated:', data);
});

// Check current users in state
// (depends on React DevTools)
```

---

## Performance Testing

### Measure Sync Time
```bash
#!/bin/bash

echo "=== Measuring Sync Time ==="

# Get token
TOKEN=$(curl -s -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@precisionpulse.com","password":"admin123"}' \
  | jq -r '.token')

# Get user ID
USER_ID=$(curl -s -X GET http://localhost:5000/api/users \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.[] | select(.email=="test@example.com") | .id')

# Measure time
START=$(date +%s%N)

# Update role
curl -s -X PUT http://localhost:5000/api/users/$USER_ID \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"role":"admin"}' > /dev/null

END=$(date +%s%N)

# Calculate elapsed time in milliseconds
ELAPSED=$(( (END - START) / 1000000 ))

echo "API Response Time: ${ELAPSED}ms"

# Wait for sync
sleep 2

# Check if synced to SQLite
SQLITE_ROLE=$(sqlite3 ~/.precision_pulse/desktop.db \
  "SELECT role FROM users WHERE id=$USER_ID;")

echo "SQLite Sync Time: ~2000ms"
echo "Total Sync Time: ~2000ms"
echo "Final Role in SQLite: $SQLITE_ROLE"
```

---

## Troubleshooting Commands

### Check Service Status
```bash
# Check if backend is running
curl -s http://localhost:5000/api/internal/health | jq .

# Check if frontend is running
curl -s http://localhost:3000 | head -20

# Check if MQTT is running
mosquitto_sub -h localhost -p 18883 -t "test" --cafile /path/to/ca.crt &
sleep 1
kill %1
```

### Check Database Connections
```bash
# Check PostgreSQL connection
psql -U postgres -d precision_pulse -c "SELECT 1;"

# Check SQLite connection
sqlite3 ~/.precision_pulse/desktop.db "SELECT 1;"

# Check MQTT connection
mosquitto_pub -h localhost -p 18883 -t "test" -m "test" --cafile /path/to/ca.crt
```

### Check Network Connectivity
```bash
# Check backend API
curl -v http://localhost:5000/api/internal/health

# Check frontend
curl -v http://localhost:3000

# Check MQTT
telnet localhost 18883
```

---

## Cleanup Commands

### Clear Cache
```bash
# Clear browser cache
# Ctrl+Shift+Delete (Windows/Linux)
# Cmd+Shift+Delete (Mac)

# Or use curl to clear
curl -X POST http://localhost:5000/api/cache/clear \
  -H "Authorization: Bearer $TOKEN"
```

### Reset Databases
```bash
# WARNING: This will delete all data!

# Reset PostgreSQL
psql -U postgres -d precision_pulse -c "DELETE FROM users WHERE email != 'admin@precisionpulse.com';"

# Reset SQLite
sqlite3 ~/.precision_pulse/desktop.db "DELETE FROM users WHERE email != 'admin@precisionpulse.com';"
```

---

## Summary

Use these commands to:
1. Verify the fix is deployed
2. Test the sync functionality
3. Debug issues
4. Monitor performance
5. Troubleshoot problems

All commands are safe and non-destructive (except cleanup commands which have warnings).
