# Implementation Checklist — User Sync & PDF Export

## ✅ Completed Tasks

### Backend User Sync Endpoints
- [x] Added `POST /api/internal/sync-user` — Create/update user
- [x] Added `PUT /api/internal/sync-user-role` — Update user role
- [x] Added `DELETE /api/internal/sync-user-delete` — Delete user
- [x] All endpoints broadcast changes via MQTT
- [x] All endpoints log actions for audit trail

### Backend PDF Export
- [x] Created `app/routes/history_export_routes.py`
- [x] Implemented `GET /api/reports/history/export/pdf`
- [x] Added statistics calculation (min, max, avg, stddev)
- [x] Added matplotlib chart generation
- [x] Added reportlab PDF formatting
- [x] Registered blueprint in `app/__init__.py`

### Frontend Export Service
- [x] Created `src/services/historyExportService.ts`
- [x] Implemented `exportPDF()` method
- [x] Implemented `exportCSV()` method
- [x] Added error handling and user feedback

---

## 📋 Remaining Tasks

### 1. Install Dependencies
```bash
cd dspl-precision-pulse-backend
pip install reportlab matplotlib
```

### 2. Update Frontend History Page
Add export buttons to `src/app/history/page.tsx`:

```tsx
import { historyExportService } from '@/services/historyExportService';

// In the controls section, add:
<div className="flex flex-wrap gap-2">
  <button 
    onClick={() => historyExportService.exportPDF({
      preset,
      paramIds: [...selectedIds],
      startDate: fromDate,
      endDate: toDate,
      token: localStorage.getItem('token') || ''
    })}
    disabled={selectedIds.size === 0 || loading}
    className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white rounded-lg text-sm font-semibold"
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
    className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white rounded-lg text-sm font-semibold"
  >
    📊 Export CSV
  </button>
</div>
```

### 3. Test User Sync Flow

**Test Case 1: Add User**
```
1. Open Desktop App → Manage Users
2. Click "+ Add User"
3. Fill: name="John Doe", email="john@example.com", password="test123", role="user"
4. Click "Add User"
5. Verify:
   - ✓ User appears in Desktop table
   - ✓ User appears in Frontend Users page
   - ✓ User exists in PostgreSQL: SELECT * FROM users WHERE email='john@example.com'
   - ✓ MQTT message logged: [SYNC] User created
```

**Test Case 2: Update User Role**
```
1. Desktop: Select "John Doe" → Click "Edit Role"
2. Change role from "user" to "admin"
3. Click "Save Changes"
4. Verify:
   - ✓ Role updated in Desktop table
   - ✓ Role updated in Frontend Users page
   - ✓ PostgreSQL shows new role: SELECT role FROM users WHERE email='john@example.com'
   - ✓ MQTT message logged: [SYNC] User role updated
```

**Test Case 3: Delete User**
```
1. Desktop: Select "John Doe" → Click "Delete"
2. Confirm deletion
3. Verify:
   - ✓ User removed from Desktop table
   - ✓ User removed from Frontend Users page
   - ✓ User deleted from PostgreSQL: SELECT COUNT(*) FROM users WHERE email='john@example.com' → 0
   - ✓ MQTT message logged: [SYNC] User deleted
```

### 4. Test PDF Export Flow

**Test Case 1: Export with Preset**
```
1. Frontend: History page
2. Select parameters: Temperature, Humidity
3. Select preset: "Last 24 hours"
4. Click "Export PDF"
5. Verify:
   - ✓ PDF downloads as history_report_YYYY-MM-DD.pdf
   - ✓ PDF contains title and timestamp
   - ✓ PDF has section for each parameter
   - ✓ Each section has statistics table
   - ✓ Each section has trend chart
   - ✓ Chart shows correct data points
```

**Test Case 2: Export with Custom Range**
```
1. Frontend: History page
2. Select parameters: Temperature
3. Select preset: "Custom Range"
4. Set: From = 2026-01-01 00:00, To = 2026-01-31 23:59
5. Click "Search"
6. Click "Export PDF"
7. Verify:
   - ✓ PDF downloads
   - ✓ Data only includes records in date range
   - ✓ Chart shows correct time period
```

**Test Case 3: Export CSV**
```
1. Frontend: History page
2. Select parameters: Temperature, Humidity
3. Select preset: "Last 7 days"
4. Click "Export CSV"
5. Verify:
   - ✓ CSV downloads as history_export_YYYY-MM-DD.csv
   - ✓ Header row: Timestamp, Temperature (°C), Humidity (%)
   - ✓ Data rows contain correct values
   - ✓ Can open in Excel/Sheets
```

---

## 🔍 Verification Steps

### Backend Endpoints
```bash
# Test sync-user endpoint
curl -X POST http://localhost:5000/api/internal/sync-user \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "name": "Test User",
    "password_hash": "hashed_password",
    "role": "user"
  }'

# Expected response:
# {"success": true, "message": "User created", "user": {...}}

# Test sync-user-role endpoint
curl -X PUT http://localhost:5000/api/internal/sync-user-role \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "role": "admin"
  }'

# Expected response:
# {"success": true, "message": "User role updated", "old_role": "user", "new_role": "admin"}

# Test PDF export endpoint
curl -X GET "http://localhost:5000/api/reports/history/export/pdf?preset=last_24_hours&param_ids=1,2" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o history.pdf

# Expected: PDF file downloads
```

### Database Verification
```bash
# Connect to PostgreSQL
psql -U postgres -d precision_pulse

# Check users table
SELECT id, email, name, role, is_active FROM users;

# Check user was synced
SELECT * FROM users WHERE email='test@example.com';

# Check audit logs
SELECT * FROM audit_logs WHERE event_type='user_created' ORDER BY created_at DESC LIMIT 5;
```

### MQTT Verification
```bash
# Subscribe to user sync topics
mosquitto_sub -h localhost -p 18883 -t "precisionpulse/sync/users/#" --cafile config/ca.crt

# In another terminal, trigger user creation
# Watch for messages like:
# precisionpulse/sync/users/created {"type": "user_created", "email": "test@example.com", ...}
```

---

## 📊 Expected Behavior

### User Sync
```
Desktop App                Backend                 Frontend
    │                         │                        │
    ├─ Add User ─────────────→ POST /sync-user ────────┤
    │                         │                        │
    │                    PostgreSQL                    │
    │                    (INSERT user)                 │
    │                         │                        │
    │                    MQTT Publish                  │
    │                         │                        │
    │ ← MQTT Subscribe ←──────┤                        │
    │ (update SQLite)         │                        │
    │                         │                   Poll /api/users
    │                         │                        │
    │                         │                   Update UI
    │                         │                        │
    └─────────────────────────────────────────────────┘
```

### PDF Export
```
Frontend                   Backend                 Database
    │                         │                        │
    ├─ Export PDF ───────────→ GET /export/pdf ───────→ Query
    │                         │                        │
    │                    Generate Stats                │
    │                    Create Charts                 │
    │                    Format PDF                    │
    │                         │                        │
    │ ← Download PDF ←────────┤                        │
    │                         │                        │
    └─────────────────────────────────────────────────┘
```

---

## 🚀 Deployment Steps

### 1. Backend Deployment
```bash
cd dspl-precision-pulse-backend

# Install dependencies
pip install -r requirements.txt
pip install reportlab matplotlib

# Run migrations
python -m flask db upgrade

# Start backend
python run.py
```

### 2. Frontend Deployment
```bash
cd dspl-precision-pulse-frontend

# Install dependencies
npm install

# Build
npm run build

# Start
npm start
```

### 3. Desktop Deployment
```bash
cd dspl-precision-pulse-desktop

# Install dependencies
pip install -r requirements.txt

# Start
python main.py
```

---

## 📝 Notes

- All user sync endpoints are internal (no auth required) — they're called by desktop app
- MQTT broadcasts ensure real-time sync across all clients
- PDF generation uses matplotlib for charts and reportlab for formatting
- CSV export is client-side (no backend call needed)
- All changes are logged for audit trail

---

## 🆘 Support

If issues occur:

1. **Check logs:**
   ```bash
   tail -f dspl-precision-pulse-backend/app.log
   tail -f dspl-precision-pulse-desktop/app.log
   ```

2. **Verify services:**
   ```bash
   # Backend
   curl http://localhost:5000/api/internal/health
   
   # MQTT
   mosquitto_sub -h localhost -p 18883 -t "test" --cafile config/ca.crt
   ```

3. **Check database:**
   ```bash
   psql -U postgres -d precision_pulse -c "SELECT COUNT(*) FROM users;"
   ```

4. **Restart services:**
   ```bash
   # Kill all Python processes
   pkill -f "python"
   
   # Restart backend
   cd dspl-precision-pulse-backend && python run.py &
   
   # Restart desktop
   cd dspl-precision-pulse-desktop && python main.py &
   ```
