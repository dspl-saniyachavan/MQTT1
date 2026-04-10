# Summary of Changes — User Sync & PDF Export Implementation

## Overview
Fixed user data synchronization between frontend, desktop, and backend database. Implemented PDF export for history page with charts and statistics.

---

## Files Modified

### 1. Backend — User Sync Endpoints
**File:** `dspl-precision-pulse-backend/app/routes/internal_routes.py`

**Changes:**
- Added `POST /api/internal/sync-user` endpoint
  - Creates or updates user from desktop
  - Accepts: email, name, password_hash, role
  - Broadcasts via MQTT: `precisionpulse/sync/users/created`

- Added `PUT /api/internal/sync-user-role` endpoint
  - Updates user role
  - Accepts: email, role
  - Broadcasts via MQTT: `precisionpulse/sync/roles/changed`

- Added `DELETE /api/internal/sync-user-delete` endpoint
  - Deletes user from backend
  - Accepts: email
  - Broadcasts via MQTT: `precisionpulse/sync/users/deleted`

**Impact:**
- Desktop app can now sync user changes to backend
- All changes broadcast via MQTT for real-time sync
- Audit logging for all user operations

---

### 2. Backend — PDF Export Route
**File:** `dspl-precision-pulse-backend/app/routes/history_export_routes.py` (NEW)

**Features:**
- `GET /api/reports/history/export/pdf` endpoint
- Accepts query parameters:
  - `preset`: Time range (last_15_minutes, last_hour, last_24_hours, last_7_days, last_30_days, custom)
  - `start_date`, `end_date`: Custom date range
  - `param_ids`: Comma-separated parameter IDs

- Generates PDF with:
  - Report header (title, timestamp, range)
  - For each parameter:
    - Statistics table (count, min, max, avg, stddev)
    - Trend chart (matplotlib)
  - Professional formatting with reportlab

**Dependencies:**
- reportlab (PDF generation)
- matplotlib (chart generation)

**Impact:**
- Users can export history data as formatted PDF
- Charts visualize trends
- Statistics provide data insights

---

### 3. Backend — App Initialization
**File:** `dspl-precision-pulse-backend/app/__init__.py`

**Changes:**
- Imported `history_export_bp` from new routes file
- Registered `history_export_bp` in `_BLUEPRINTS` list

**Impact:**
- New PDF export endpoint is accessible

---

### 4. Frontend — Export Service
**File:** `dspl-precision-pulse-frontend/src/services/historyExportService.ts` (NEW)

**Methods:**
- `exportPDF(options)`: Downloads PDF from backend
  - Handles authentication
  - Manages file download
  - Error handling

- `exportCSV(options, timestamps, values, parameters)`: Generates CSV client-side
  - Creates formatted CSV
  - Downloads as file
  - No backend call needed

**Usage:**
```typescript
import { historyExportService } from '@/services/historyExportService';

// Export PDF
await historyExportService.exportPDF({
  preset: 'last_24_hours',
  paramIds: [1, 2, 3],
  token: localStorage.getItem('token')
});

// Export CSV
await historyExportService.exportCSV(
  { preset, paramIds, token },
  allTimestamps,
  valueLookup,
  parameters
);
```

**Impact:**
- Frontend can export history data
- Two export formats (PDF and CSV)
- User-friendly download experience

---

## Data Flow Diagrams

### User Sync Flow
```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                       │
│              User Management Page                           │
│  - Add User → POST /api/users                               │
│  - Edit User → PUT /api/users/<id>                          │
│  - Delete User → DELETE /api/users/<id>                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│                  Backend (Flask)                            │
│  - /api/users/* (REST endpoints)                            │
│  - /api/internal/sync-user* (desktop sync)                  │
│  - PostgreSQL (primary database)                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│                  MQTT Broker                                │
│  - precisionpulse/sync/users/created                        │
│  - precisionpulse/sync/users/updated                        │
│  - precisionpulse/sync/users/deleted                        │
│  - precisionpulse/sync/roles/changed                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│                  Desktop (PySide6)                          │
│  - Manage Users Page                                        │
│  - MQTT Subscriber (receives sync events)                   │
│  - Local SQLite Database                                    │
└─────────────────────────────────────────────────────────────┘
```

### PDF Export Flow
```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                       │
│              History Page                                   │
│  - Select parameters                                        │
│  - Choose time range                                        │
│  - Click "Export PDF"                                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│                  Backend (Flask)                            │
│  - GET /api/reports/history/export/pdf                      │
│  - Query ParameterStream table                              │
│  - Calculate statistics                                     │
│  - Generate charts (matplotlib)                             │
│  - Format PDF (reportlab)                                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                       │
│  - Download PDF file                                        │
│  - Save as history_report_YYYY-MM-DD.pdf                    │
└─────────────────────────────────────────────────────────────┘
```

---

## API Endpoints Added

### User Sync Endpoints (Internal)

**1. Create/Update User**
```
POST /api/internal/sync-user
Content-Type: application/json

{
  "email": "user@example.com",
  "name": "User Name",
  "password_hash": "bcrypt_hash",
  "role": "user"
}

Response:
{
  "success": true,
  "message": "User created",
  "user": { ... }
}
```

**2. Update User Role**
```
PUT /api/internal/sync-user-role
Content-Type: application/json

{
  "email": "user@example.com",
  "role": "admin"
}

Response:
{
  "success": true,
  "message": "User role updated",
  "email": "user@example.com",
  "old_role": "user",
  "new_role": "admin"
}
```

**3. Delete User**
```
DELETE /api/internal/sync-user-delete
Content-Type: application/json

{
  "email": "user@example.com"
}

Response:
{
  "success": true,
  "message": "User deleted",
  "email": "user@example.com"
}
```

### PDF Export Endpoint

**Export History as PDF**
```
GET /api/reports/history/export/pdf?preset=last_24_hours&param_ids=1,2,3
Authorization: Bearer <token>

Query Parameters:
- preset: last_15_minutes | last_30_minutes | last_hour | last_6_hours | 
          last_24_hours | last_7_days | last_30_days | custom
- param_ids: comma-separated parameter IDs
- start_date: ISO datetime (for custom preset)
- end_date: ISO datetime (for custom preset)

Response:
- Content-Type: application/pdf
- File: history_report_YYYY-MM-DD.pdf
```

---

## Database Changes

### No Schema Changes Required
- All endpoints use existing tables
- No new columns added
- No migrations needed

### Tables Used
- `users` — User data
- `parameter_stream` — Telemetry data for PDF export
- `parameters` — Parameter metadata
- `audit_logs` — Audit trail (optional)

---

## Dependencies Added

### Backend
```
reportlab>=3.6.0  # PDF generation
matplotlib>=3.5.0  # Chart generation
```

### Frontend
- No new dependencies (uses existing services)

### Desktop
- No new dependencies (already has MQTT support)

---

## Testing Checklist

### User Sync
- [ ] Add user from desktop → appears in frontend
- [ ] Edit user role from desktop → updates in frontend
- [ ] Delete user from desktop → removed from frontend
- [ ] MQTT messages logged correctly
- [ ] PostgreSQL database updated
- [ ] SQLite local database updated

### PDF Export
- [ ] Export with preset time range
- [ ] Export with custom date range
- [ ] PDF contains correct parameters
- [ ] Statistics calculated correctly
- [ ] Charts generated properly
- [ ] File downloads successfully

### CSV Export
- [ ] CSV generated with correct headers
- [ ] Data rows contain correct values
- [ ] File downloads successfully
- [ ] Can open in Excel/Sheets

---

## Deployment Instructions

### 1. Install Dependencies
```bash
cd dspl-precision-pulse-backend
pip install reportlab matplotlib
```

### 2. Restart Backend
```bash
python run.py
```

### 3. Update Frontend (Optional)
Add export buttons to history page:
```tsx
import { historyExportService } from '@/services/historyExportService';

<button onClick={() => historyExportService.exportPDF({...})}>
  📄 Export PDF
</button>
```

### 4. Test
```bash
# Test user sync
curl -X POST http://localhost:5000/api/internal/sync-user \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","name":"Test","role":"user"}'

# Test PDF export
curl -X GET "http://localhost:5000/api/reports/history/export/pdf?preset=last_24_hours" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o test.pdf
```

---

## Troubleshooting

### User Sync Not Working
1. Check backend is running: `curl http://localhost:5000/api/internal/health`
2. Check MQTT broker: `mosquitto_sub -h localhost -p 18883 -t "test"`
3. Check desktop logs for MQTT connection errors
4. Verify PostgreSQL is accessible

### PDF Export Failing
1. Check dependencies: `pip list | grep reportlab`
2. Check backend logs for errors
3. Verify parameters exist in database
4. Test with simple query: `curl http://localhost:5000/api/reports/history/export/pdf?preset=last_hour`

### MQTT Not Broadcasting
1. Check Mosquitto is running
2. Check TLS certificates are valid
3. Check firewall allows port 18883
4. Check MQTT_BROKER config in backend

---

## Performance Considerations

### User Sync
- Endpoints are fast (single DB query)
- MQTT broadcasts are asynchronous
- No performance impact on frontend

### PDF Export
- Large datasets (>2000 records) may take 5-10 seconds
- Chart generation is CPU-intensive
- Consider caching for repeated exports

### Optimization Tips
- Limit PDF export to 1000 records max
- Use presets instead of custom ranges
- Cache generated PDFs for 1 hour
- Compress PDF before download

---

## Security Considerations

### User Sync
- Endpoints are internal (no auth required)
- Should only be called by desktop app
- Consider adding IP whitelist in production
- All changes logged for audit trail

### PDF Export
- Requires JWT authentication
- User can only export their own data
- Consider rate limiting (1 export per 10 seconds)
- PDF contains sensitive data — ensure HTTPS

---

## Future Enhancements

1. **User Sync**
   - Add bulk user import/export
   - Add user groups/teams
   - Add permission templates

2. **PDF Export**
   - Add custom branding/logo
   - Add comparison reports
   - Add scheduled exports
   - Add email delivery

3. **Performance**
   - Cache PDF generation
   - Async PDF generation (background job)
   - Streaming large exports

---

## Support & Documentation

- **User Sync Guide:** `USER_SYNC_PDF_EXPORT_GUIDE.md`
- **Implementation Checklist:** `IMPLEMENTATION_CHECKLIST.md`
- **API Documentation:** See backend routes
- **Frontend Integration:** See `historyExportService.ts`

---

## Version Info

- **Backend:** Flask 2.x
- **Frontend:** Next.js 13+
- **Desktop:** PySide6
- **Database:** PostgreSQL + SQLite
- **MQTT:** Mosquitto 2.x

---

## Contact & Support

For issues or questions:
1. Check logs: `tail -f app.log`
2. Review documentation
3. Test endpoints manually
4. Check database state
5. Verify MQTT connectivity
