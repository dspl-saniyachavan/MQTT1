# Quick Reference — User Sync & PDF Export

## Installation

```bash
# Install backend dependencies
cd dspl-precision-pulse-backend
pip install reportlab matplotlib

# Verify installation
python -c "import reportlab; import matplotlib; print('✓ Dependencies installed')"
```

---

## Testing Commands

### Test User Sync Endpoints

```bash
# 1. Create/Update User
curl -X POST http://localhost:5000/api/internal/sync-user \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "name": "John Doe",
    "password_hash": "bcrypt_hash_here",
    "role": "user"
  }'

# Expected: {"success": true, "message": "User created", "user": {...}}

# 2. Update User Role
curl -X PUT http://localhost:5000/api/internal/sync-user-role \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "role": "admin"
  }'

# Expected: {"success": true, "message": "User role updated", "old_role": "user", "new_role": "admin"}

# 3. Delete User
curl -X DELETE http://localhost:5000/api/internal/sync-user-delete \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com"
  }'

# Expected: {"success": true, "message": "User deleted", "email": "john@example.com"}
```

### Test PDF Export Endpoint

```bash
# Get token first
TOKEN=$(curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@precisionpulse.com","password":"admin"}' \
  | jq -r '.token')

# Export PDF (last 24 hours)
curl -X GET "http://localhost:5000/api/reports/history/export/pdf?preset=last_24_hours&param_ids=1,2" \
  -H "Authorization: Bearer $TOKEN" \
  -o history_report.pdf

# Export PDF (custom range)
curl -X GET "http://localhost:5000/api/reports/history/export/pdf?preset=custom&start_date=2026-01-01T00:00:00&end_date=2026-01-31T23:59:59&param_ids=1" \
  -H "Authorization: Bearer $TOKEN" \
  -o history_custom.pdf

# Verify PDF was created
file history_report.pdf
```

---

## Database Verification

```bash
# Connect to PostgreSQL
psql -U postgres -d precision_pulse

# Check users table
SELECT id, email, name, role, is_active, created_at FROM users ORDER BY created_at DESC;

# Check specific user
SELECT * FROM users WHERE email='john@example.com';

# Check parameter stream (for PDF export)
SELECT parameter_id, value, timestamp FROM parameter_stream ORDER BY timestamp DESC LIMIT 10;

# Check audit logs
SELECT event_type, actor_email, action, created_at FROM audit_logs ORDER BY created_at DESC LIMIT 10;

# Count users by role
SELECT role, COUNT(*) FROM users GROUP BY role;
```

---

## MQTT Verification

```bash
# Subscribe to user sync topics
mosquitto_sub -h localhost -p 18883 \
  -t "precisionpulse/sync/users/#" \
  --cafile config/ca.crt

# In another terminal, trigger user creation
# Watch for messages like:
# precisionpulse/sync/users/created {"type": "user_created", "email": "john@example.com", ...}

# Subscribe to role changes
mosquitto_sub -h localhost -p 18883 \
  -t "precisionpulse/sync/roles/#" \
  --cafile config/ca.crt

# Subscribe to all sync topics
mosquitto_sub -h localhost -p 18883 \
  -t "precisionpulse/sync/#" \
  --cafile config/ca.crt
```

---

## Frontend Integration

### Add Export Buttons to History Page

```tsx
// src/app/history/page.tsx

import { historyExportService } from '@/services/historyExportService';

// In the controls section, add:
<div className="flex flex-wrap gap-2 mt-4">
  <button 
    onClick={() => historyExportService.exportPDF({
      preset,
      paramIds: [...selectedIds],
      startDate: fromDate,
      endDate: toDate,
      token: localStorage.getItem('token') || ''
    })}
    disabled={selectedIds.size === 0 || loading}
    className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white rounded-lg text-sm font-semibold flex items-center gap-2"
  >
    📄 Export PDF
  </button>
  
  <button 
    onClick={() => historyExportService.exportCSV(
      {
        preset,
        paramIds: [...selectedIds],
        startDate: fromDate,
        endDate: toDate,
        token: localStorage.getItem('token') || ''
      },
      allTimestamps,
      valueLookup,
      parameters
    )}
    disabled={selectedIds.size === 0 || loading}
    className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white rounded-lg text-sm font-semibold flex items-center gap-2"
  >
    📊 Export CSV
  </button>
</div>
```

---

## Desktop App Integration

### User Sync Already Implemented

The desktop app already has correct implementation:

```python
# src/ui/manage_users_page.py

# Add user
response = requests.post(
    "http://localhost:5000/api/internal/sync-user",
    json={
        "email": user_data['email'],
        "name": user_data['name'],
        "password_hash": password_hash,
        "role": user_data['role']
    },
    headers={"Content-Type": "application/json"},
    timeout=5
)

# Update user role
response = requests.put(
    f"http://localhost:5000/api/internal/sync-user-role",
    json={"email": user['email'], "role": user_data['role']},
    headers={"Content-Type": "application/json"},
    timeout=5
)

# Delete user
response = requests.delete(
    f"http://localhost:5000/api/internal/sync-user-delete",
    json={"email": user['email']},
    headers={"Content-Type": "application/json"},
    timeout=5
)
```

---

## Logs & Debugging

### View Backend Logs

```bash
# Real-time logs
tail -f dspl-precision-pulse-backend/app.log

# Filter for user sync
tail -f dspl-precision-pulse-backend/app.log | grep "\[SYNC\]"

# Filter for PDF export
tail -f dspl-precision-pulse-backend/app.log | grep "\[REPORT\]"

# Filter for MQTT
tail -f dspl-precision-pulse-backend/app.log | grep "\[MQTT\]"
```

### View Desktop Logs

```bash
# Real-time logs
tail -f dspl-precision-pulse-desktop/app.log

# Filter for user sync
tail -f dspl-precision-pulse-desktop/app.log | grep "\[USER_SYNC\]"

# Filter for MQTT
tail -f dspl-precision-pulse-desktop/app.log | grep "\[MQTT\]"
```

### View MQTT Broker Logs

```bash
# Start Mosquitto with verbose logging
mosquitto -c mosquitto.conf -v

# Or check existing logs
tail -f /var/log/mosquitto/mosquitto.log
```

---

## Common Issues & Solutions

### Issue: User Sync Endpoint Returns 404

**Solution:**
```bash
# 1. Check backend is running
curl http://localhost:5000/api/internal/health

# 2. Check route is registered
curl -X POST http://localhost:5000/api/internal/sync-user \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","name":"Test","role":"user"}'

# 3. Restart backend
pkill -f "python run.py"
cd dspl-precision-pulse-backend && python run.py
```

### Issue: PDF Export Returns 500 Error

**Solution:**
```bash
# 1. Check dependencies
pip list | grep -E "reportlab|matplotlib"

# 2. Install if missing
pip install reportlab matplotlib

# 3. Check backend logs
tail -f dspl-precision-pulse-backend/app.log | grep "\[REPORT\]"

# 4. Restart backend
pkill -f "python run.py"
cd dspl-precision-pulse-backend && python run.py
```

### Issue: MQTT Messages Not Received

**Solution:**
```bash
# 1. Check Mosquitto is running
ps aux | grep mosquitto

# 2. Check port is open
netstat -tlnp | grep 18883

# 3. Check TLS certificates
ls -la config/ca.crt config/server.crt config/server.key

# 4. Restart Mosquitto
pkill mosquitto
mosquitto -c mosquitto.conf
```

### Issue: User Changes Not Syncing to Frontend

**Solution:**
```bash
# 1. Check PostgreSQL has the data
psql -U postgres -d precision_pulse -c "SELECT * FROM users WHERE email='test@example.com';"

# 2. Check frontend is polling
# Open browser console and check network tab for /api/users requests

# 3. Check MQTT is broadcasting
mosquitto_sub -h localhost -p 18883 -t "precisionpulse/sync/users/#" --cafile config/ca.crt

# 4. Restart all services
pkill -f "python"
pkill mosquitto
sleep 2
cd dspl-precision-pulse-backend && python run.py &
mosquitto -c mosquitto.conf &
```

---

## Performance Tuning

### Optimize PDF Export

```python
# In history_export_routes.py, limit records
records = query.order_by(desc(ParameterStream.timestamp)).limit(1000).all()

# Use lower DPI for faster generation
fig.savefig(img_buffer, format='png', dpi=72, bbox_inches='tight')

# Cache generated PDFs
from functools import lru_cache

@lru_cache(maxsize=10)
def generate_pdf_cached(preset, param_ids):
    # Generate PDF
    pass
```

### Optimize User Sync

```python
# Batch user updates
users_to_sync = [...]
for user in users_to_sync:
    db.session.add(user)
db.session.commit()  # Single commit for all

# Use connection pooling
from sqlalchemy.pool import QueuePool
engine = create_engine(DATABASE_URL, poolclass=QueuePool, pool_size=10)
```

---

## Monitoring

### Health Check Script

```bash
#!/bin/bash

echo "=== PrecisionPulse Health Check ==="

# Check Backend
echo -n "Backend: "
curl -s http://localhost:5000/api/internal/health | jq -r '.status' || echo "FAILED"

# Check MQTT
echo -n "MQTT: "
mosquitto_sub -h localhost -p 18883 -t "test" --cafile config/ca.crt -W 1 2>/dev/null && echo "OK" || echo "FAILED"

# Check PostgreSQL
echo -n "PostgreSQL: "
psql -U postgres -d precision_pulse -c "SELECT 1" 2>/dev/null && echo "OK" || echo "FAILED"

# Check Users Count
echo -n "Users: "
psql -U postgres -d precision_pulse -c "SELECT COUNT(*) FROM users" 2>/dev/null | tail -1

# Check Parameter Stream Count
echo -n "Telemetry Records: "
psql -U postgres -d precision_pulse -c "SELECT COUNT(*) FROM parameter_stream" 2>/dev/null | tail -1

echo "=== End Health Check ==="
```

---

## Useful Queries

### User Management

```sql
-- List all users
SELECT id, email, name, role, is_active, created_at FROM users ORDER BY created_at DESC;

-- Find user by email
SELECT * FROM users WHERE email='john@example.com';

-- Count users by role
SELECT role, COUNT(*) as count FROM users GROUP BY role;

-- Find recently created users
SELECT * FROM users WHERE created_at > NOW() - INTERVAL '1 day' ORDER BY created_at DESC;

-- Find inactive users
SELECT * FROM users WHERE is_active = false;
```

### Telemetry Data

```sql
-- Get latest telemetry for each parameter
SELECT DISTINCT ON (parameter_id) parameter_id, value, timestamp 
FROM parameter_stream 
ORDER BY parameter_id, timestamp DESC;

-- Get telemetry for specific parameter
SELECT * FROM parameter_stream 
WHERE parameter_id = 1 
ORDER BY timestamp DESC 
LIMIT 100;

-- Get telemetry statistics
SELECT 
  parameter_id,
  COUNT(*) as count,
  MIN(value) as min_value,
  MAX(value) as max_value,
  AVG(value) as avg_value
FROM parameter_stream
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY parameter_id;

-- Get telemetry for date range
SELECT * FROM parameter_stream
WHERE timestamp BETWEEN '2026-01-01' AND '2026-01-31'
ORDER BY timestamp DESC;
```

### Audit Logs

```sql
-- Get recent audit logs
SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 20;

-- Get user activity
SELECT * FROM audit_logs 
WHERE actor_email = 'john@example.com' 
ORDER BY created_at DESC;

-- Get failed operations
SELECT * FROM audit_logs 
WHERE status = 'failure' 
ORDER BY created_at DESC;

-- Get user creation events
SELECT * FROM audit_logs 
WHERE event_type = 'user_created' 
ORDER BY created_at DESC;
```

---

## File Locations

```
Backend:
  - Routes: dspl-precision-pulse-backend/app/routes/
    - internal_routes.py (user sync endpoints)
    - history_export_routes.py (PDF export)
  - Models: dspl-precision-pulse-backend/app/models/
  - Services: dspl-precision-pulse-backend/app/services/

Frontend:
  - Services: dspl-precision-pulse-frontend/src/services/
    - historyExportService.ts (export functionality)
  - Pages: dspl-precision-pulse-frontend/src/app/
    - history/page.tsx (history page)

Desktop:
  - UI: dspl-precision-pulse-desktop/src/ui/
    - manage_users_page.py (user management)
  - Services: dspl-precision-pulse-desktop/src/services/
    - user_sync_service.py (MQTT sync)
```

---

## Documentation Files

- `USER_SYNC_PDF_EXPORT_GUIDE.md` — Comprehensive guide
- `IMPLEMENTATION_CHECKLIST.md` — Step-by-step checklist
- `CHANGES_SUMMARY.md` — Summary of all changes
- `QUICK_REFERENCE.md` — This file

---

## Support

For issues:
1. Check logs: `tail -f app.log`
2. Run health check: `./health_check.sh`
3. Test endpoints manually with curl
4. Check database state with psql
5. Verify MQTT connectivity
6. Review documentation files
