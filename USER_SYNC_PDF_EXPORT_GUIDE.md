# PrecisionPulse — User Sync & PDF Export Implementation Guide

## Issues Fixed

### 1. User Data Not Syncing from Frontend to Desktop to Database

**Problem:**
- User role changes and edits made in the frontend were not syncing to the backend database
- Desktop app changes were not being reflected in the backend
- Missing backend endpoints for user synchronization

**Root Cause:**
- Backend was missing `/api/internal/sync-user`, `/api/internal/sync-user-role`, and `/api/internal/sync-user-delete` endpoints
- Desktop app was calling these endpoints but they didn't exist, causing silent failures

**Solution Implemented:**

#### Backend Changes (`app/routes/internal_routes.py`)

Added three new endpoints:

**1. POST `/api/internal/sync-user`**
```python
# Creates or updates user from desktop
# Accepts: email, name, password_hash, role
# Returns: user object with success status
```
- Creates new user if doesn't exist
- Updates existing user (name, role, password_hash)
- Broadcasts user creation/update via MQTT to other clients

**2. PUT `/api/internal/sync-user-role`**
```python
# Updates user role from desktop
# Accepts: email, role
# Returns: old_role and new_role for audit
```
- Updates user role in PostgreSQL
- Broadcasts role change via MQTT topic: `precisionpulse/sync/roles/changed`
- Logs role transition for audit trail

**3. DELETE `/api/internal/sync-user-delete`**
```python
# Deletes user from backend
# Accepts: email
# Returns: success status
```
- Removes user from PostgreSQL
- Broadcasts deletion via MQTT
- Prevents orphaned user records

#### Desktop App Changes (`src/ui/manage_users_page.py`)

The desktop app already had the correct implementation:

**Add User Flow:**
```
1. User fills form (name, email, password, role)
2. Save to local SQLite
3. POST to /api/internal/sync-user (backend)
4. Publish to MQTT for other clients
```

**Edit User (Role Change) Flow:**
```
1. User selects "Edit Role"
2. Update role in local SQLite
3. PUT to /api/internal/sync-user-role (backend)
4. Publish to MQTT for sync
```

**Delete User Flow:**
```
1. User confirms deletion
2. Delete from local SQLite
3. DELETE to /api/internal/sync-user-delete (backend)
4. Publish to MQTT for sync
```

#### Frontend Changes (`src/ui/manage_users_page.py`)

The frontend already calls the correct endpoints via `backendService.ts`:
- `userService.createUser()` → POST `/api/users`
- `userService.updateUser()` → PUT `/api/users/<id>`
- `userService.deleteUser()` → DELETE `/api/users/<id>`

**Data Flow:**
```
Frontend (Next.js)
    ↓
Backend REST API (/api/users/*)
    ↓
PostgreSQL Database
    ↓
MQTT Broadcast (precisionpulse/sync/users/*)
    ↓
Desktop App (receives via MQTT subscriber)
    ↓
Local SQLite Database
```

---

### 2. PDF Generation for History Page

**Problem:**
- History page had no PDF export functionality
- Users couldn't generate formatted reports with charts and statistics

**Solution Implemented:**

#### Backend Changes

**New File:** `app/routes/history_export_routes.py`

**Endpoint:** `GET /api/reports/history/export/pdf`

**Features:**
- Accepts query parameters:
  - `preset`: Time range (last_15_minutes, last_hour, last_24_hours, last_7_days, etc.)
  - `start_date`, `end_date`: Custom date range
  - `param_ids`: Comma-separated parameter IDs to include

- Generates PDF with:
  1. **Header Section**
     - Report title: "PrecisionPulse — Parameter History Report"
     - Generation timestamp
     - Time range used

  2. **For Each Parameter:**
     - Parameter name and unit
     - Statistics table:
       - Record count
       - Min value
       - Max value
       - Average value
       - Standard deviation
     - Trend chart (matplotlib):
       - Line graph with fill
       - Time on X-axis
       - Value on Y-axis
       - Grid and legend

  3. **Formatting:**
     - Professional dark theme colors
     - Responsive layout
     - Page breaks between parameters
     - Proper spacing and typography

**Dependencies Required:**
```bash
pip install reportlab matplotlib
```

**Usage:**
```python
# Backend generates PDF with charts
GET /api/reports/history/export/pdf?preset=last_24_hours&param_ids=1,2,3
```

#### Frontend Changes

**New File:** `src/services/historyExportService.ts`

**Service Methods:**

1. **exportPDF(options)**
   ```typescript
   await historyExportService.exportPDF({
     preset: 'last_24_hours',
     paramIds: [1, 2, 3],
     token: localStorage.getItem('token')
   });
   ```
   - Calls backend PDF endpoint
   - Downloads file as `history_report_YYYY-MM-DD.pdf`

2. **exportCSV(options, timestamps, values, parameters)**
   ```typescript
   await historyExportService.exportCSV(
     { preset, paramIds, token },
     allTimestamps,
     valueLookup,
     parameters
   );
   ```
   - Generates CSV from frontend data
   - Downloads as `history_export_YYYY-MM-DD.csv`

**Frontend Integration:**

Add export buttons to history page:
```tsx
<button onClick={() => historyExportService.exportPDF({...})}>
  📄 Export PDF
</button>

<button onClick={() => historyExportService.exportCSV({...})}>
  📊 Export CSV
</button>
```

---

## Testing the Fixes

### Test User Sync

**1. Add User from Desktop:**
```
1. Open Desktop App → Manage Users
2. Click "+ Add User"
3. Fill form: name, email, password, role
4. Click "Add User"
5. Verify in Frontend: Users page should show new user
6. Verify in Backend: Check PostgreSQL users table
```

**2. Edit User Role from Desktop:**
```
1. Desktop: Select user → Click "Edit Role"
2. Change role (user → admin)
3. Click "Save Changes"
4. Verify in Frontend: User role updated
5. Verify in Backend: PostgreSQL shows new role
```

**3. Delete User from Desktop:**
```
1. Desktop: Select user → Click "Delete"
2. Confirm deletion
3. Verify in Frontend: User removed from list
4. Verify in Backend: User deleted from PostgreSQL
```

### Test PDF Export

**1. Generate PDF:**
```
1. Frontend: History page
2. Select parameters
3. Choose time range
4. Click "Export PDF"
5. Verify PDF downloads with:
   - Correct parameters
   - Charts for each parameter
   - Statistics table
   - Proper formatting
```

**2. Custom Date Range:**
```
1. Select "Custom Range"
2. Set start and end dates
3. Click "Search"
4. Click "Export PDF"
5. Verify PDF contains only data in range
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                       │
│  - User Management Page                                     │
│  - History Page with Export                                 │
│  - REST API calls via apiClient                             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│                  Backend (Flask)                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ REST API Routes                                      │   │
│  │ - /api/users/* (user management)                     │   │
│  │ - /api/internal/sync-user* (desktop sync)            │   │
│  │ - /api/reports/history/export/pdf (PDF export)       │   │
│  └──────────────────────────────────────────────────────┘   │
│                     ↓                                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Database Layer                                       │   │
│  │ - PostgreSQL (primary)                               │   │
│  │ - SQLite (desktop local)                             │   │
│  └──────────────────────────────────────────────────────┘   │
│                     ↓                                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ MQTT Broker (Mosquitto)                              │   │
│  │ - precisionpulse/sync/users/*                        │   │
│  │ - precisionpulse/sync/roles/*                        │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                     ↑
                     │
┌─────────────────────────────────────────────────────────────┐
│                  Desktop (PySide6)                          │
│  - Manage Users Page                                        │
│  - MQTT Subscriber (receives sync events)                   │
│  - Local SQLite Database                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Sync Flow

### User Creation
```
Desktop UI
  ↓ (user fills form)
Local SQLite (INSERT)
  ↓ (POST /api/internal/sync-user)
Backend PostgreSQL (INSERT)
  ↓ (MQTT publish)
MQTT Broker
  ↓ (MQTT subscribe)
Desktop MQTT Listener
  ↓ (update local SQLite)
Frontend (polls /api/users)
  ↓ (displays new user)
Frontend UI
```

### User Role Update
```
Desktop UI (Edit Role)
  ↓
Local SQLite (UPDATE role)
  ↓ (PUT /api/internal/sync-user-role)
Backend PostgreSQL (UPDATE role)
  ↓ (MQTT publish role_changed)
MQTT Broker
  ↓
Desktop MQTT Listener (updates local)
Frontend (polls /api/users)
  ↓
Frontend UI (shows updated role)
```

---

## Configuration

### Environment Variables

**Backend (.env):**
```
MQTT_BROKER=localhost
MQTT_PORT=18883
MQTT_USE_TLS=true
MQTT_CA_CERTS=config/ca.crt
```

**Frontend (.env.local):**
```
NEXT_PUBLIC_BACKEND_URL=http://localhost:5000
```

**Desktop (config.py):**
```
BACKEND_URL = 'http://localhost:5000'
MQTT_BROKER = 'localhost'
MQTT_PORT = 18883
```

---

## Troubleshooting

### User Changes Not Syncing

**Check:**
1. Backend endpoints exist: `curl http://localhost:5000/api/internal/sync-user`
2. MQTT broker running: `mosquitto -c mosquitto.conf`
3. Desktop MQTT subscriber connected: Check logs for `[MQTT] Connected`
4. PostgreSQL accessible: `psql -U postgres -d precision_pulse`

**Fix:**
```bash
# Restart backend
python run.py

# Restart desktop app
python main.py

# Check MQTT logs
mosquitto -c mosquitto.conf -v
```

### PDF Export Not Working

**Check:**
1. Dependencies installed: `pip list | grep reportlab`
2. Backend route registered: Check app/__init__.py blueprints
3. Matplotlib available: `python -c "import matplotlib"`

**Fix:**
```bash
pip install reportlab matplotlib
python run.py
```

### User Sync Endpoint Returns 404

**Check:**
1. Backend running on port 5000
2. Route registered in app/__init__.py
3. Desktop calling correct URL: `http://localhost:5000/api/internal/sync-user`

**Fix:**
```bash
# Verify route exists
curl -X POST http://localhost:5000/api/internal/sync-user \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","name":"Test","role":"user"}'
```

---

## Files Modified/Created

### Backend
- ✅ `app/routes/internal_routes.py` — Added sync endpoints
- ✅ `app/routes/history_export_routes.py` — New PDF export route
- ✅ `app/__init__.py` — Registered new blueprint

### Frontend
- ✅ `src/services/historyExportService.ts` — New export service
- ✅ `src/app/history/page.tsx` — Add export buttons (ready for integration)

### Desktop
- ✅ `src/ui/manage_users_page.py` — Already correct, calls sync endpoints
- ✅ `src/services/user_sync_service.py` — Already correct, handles MQTT

---

## Next Steps

1. **Install Dependencies:**
   ```bash
   pip install reportlab matplotlib
   ```

2. **Restart Services:**
   ```bash
   # Backend
   cd dspl-precision-pulse-backend && python run.py
   
   # Frontend
   cd dspl-precision-pulse-frontend && npm run dev
   
   # Desktop
   cd dspl-precision-pulse-desktop && python main.py
   ```

3. **Test User Sync:**
   - Add user from desktop
   - Verify in frontend and backend

4. **Test PDF Export:**
   - Go to history page
   - Select parameters and time range
   - Click "Export PDF"
   - Verify PDF downloads with charts

5. **Monitor Logs:**
   ```bash
   # Backend logs
   tail -f dspl-precision-pulse-backend/app.log
   
   # Desktop logs
   tail -f dspl-precision-pulse-desktop/app.log
   ```
