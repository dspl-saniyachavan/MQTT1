# PrecisionPulse — Production Readiness & Operations Guide

**Version:** 1.0.0 | **Organization:** DSPL

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture](#2-architecture)
3. [Component Reference](#3-component-reference)
4. [Environment Configuration](#4-environment-configuration)
5. [Deployment](#5-deployment)
6. [Database Operations](#6-database-operations)
7. [Security](#7-security)
8. [Monitoring & Health Checks](#8-monitoring--health-checks)
9. [Runbooks](#9-runbooks)
10. [Backup & Recovery](#10-backup--recovery)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. System Overview

PrecisionPulse is a real-time industrial telemetry platform consisting of three components:

| Component | Technology | Role |
|---|---|---|
| **Backend** (`dspl-precision-pulse-backend`) | Python 3.11 / Flask | REST API, WebSocket hub, MQTT broker bridge, PostgreSQL |
| **Desktop** (`dspl-precision-pulse-desktop`) | Python 3.11 / PySide6 | On-device data acquisition, local SQLite, MQTT publisher |
| **Frontend** (`dspl-precision-pulse-frontend`) | Next.js 16 / React 19 | Web dashboard, real-time visualization |

Supporting infrastructure:
- **PostgreSQL 15** — primary data store
- **Eclipse Mosquitto 2** — MQTT broker (TLS on port 18883)

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Network                              │
│                                                             │
│  ┌──────────────┐   MQTT/TLS    ┌──────────────────────┐   │
│  │   Desktop    │◄─────────────►│  Mosquitto Broker    │   │
│  │  (PySide6)   │               │  port 18883          │   │
│  │  SQLite DB   │               └──────────┬───────────┘   │
│  └──────┬───────┘                          │               │
│         │ HTTP REST                        │ MQTT          │
│         ▼                                  ▼               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Backend (Flask)  :5000                  │  │
│  │  REST API · Socket.IO · MQTT Subscriber              │  │
│  │  RBAC · Audit Logging · Conflict Resolution          │  │
│  └──────────────────────┬───────────────────────────────┘  │
│                         │                                   │
│              ┌──────────┴──────────┐                        │
│              │   PostgreSQL :5432  │                        │
│              └─────────────────────┘                        │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Frontend (Next.js)  :3000               │  │
│  │  Dashboard · Real-time Charts · RBAC UI              │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. Desktop acquires sensor readings → publishes to `precisionpulse/{device_id}/telemetry` via MQTT (TLS)
2. Backend MQTT subscriber receives telemetry → stores in PostgreSQL → broadcasts via Socket.IO
3. Frontend subscribes to Socket.IO events → renders live charts and dashboards
4. Config/user changes flow backend → MQTT sync topics → Desktop SQLite (bidirectional sync)
5. Offline buffering: Desktop stores to local SQLite `local_buffer` when MQTT is unavailable; auto-flushes on reconnect

---

## 3. Component Reference

### 3.1 Backend

**Entry point:** `run.py`  
**App factory:** `app/__init__.py` → `create_app()`

#### API Route Groups

| Prefix | Blueprint | Purpose |
|---|---|---|
| `/api/auth` | `auth_bp` | Login, registration |
| `/api/users` | `user_bp` | User CRUD |
| `/api/parameters` | `parameter_bp` | Parameter management |
| `/api/telemetry` | `telemetry_bp` | Telemetry ingestion & query |
| `/api/parameter-stream` | `parameter_stream_bp` | Live stream data |
| `/api/sync` | `sync_bp` | Desktop↔Backend sync |
| `/api/internal` | `internal_bp` | Internal desktop calls |
| `/api/internal-sync` | `internal_sync_bp` | Sync orchestration |
| `/api/buffer` | `buffer_bp` | Offline buffer management |
| `/api/mqtt` | `mqtt_bridge_bp`, `mqtt_status_bp` | MQTT bridge & status |
| `/api/commands` | `remote_commands_bp` | Remote device commands |
| `/api/config` | `config_bp` | System configuration |
| `/api/audit` | `audit_bp`, `audit_log_bp` | Audit trail |
| `/api/reports` | `report_bp`, `telemetry_report_bp` | Report generation |
| `/api/conflicts` | `conflict_bp` | Conflict resolution |
| `/api/permissions` | `permission_bp` | RBAC permissions |
| `/api/docs` | Swagger UI | Interactive API docs |

#### Background Threads

| Thread | Function | Interval |
|---|---|---|
| MQTT Subscriber | `start_mqtt_subscriber()` | Persistent |
| Status Broadcast | `broadcast_mqtt_status()` | Every 5 s |
| Buffer Auto-flush | Inside status broadcast | Every 5 s (when online) |

#### Key Services

- `mqtt_publisher` / `mqtt_subscriber` — MQTT I/O
- `sync_service` — PostgreSQL ↔ SQLite mirroring
- `buffer_service` — Offline change queue flush
- `conflict_resolver` — Last-write-wins with audit trail
- `data_freshness_monitor` — Stale data detection (15 s threshold)
- `permission_sync_service` — RBAC push to desktop
- `report_generation_service` — PDF reports via ReportLab

---

### 3.2 Desktop

**Entry point:** `main.py` (GUI) | `streamer.py` (headless/Docker)  
**Local DB:** `data/precision_pulse.db` (SQLite)

#### SQLite Schema

| Table | Purpose |
|---|---|
| `users` | Local user cache (synced from backend) |
| `parameters` | Parameter definitions (synced from backend) |
| `parameter_stream` | Raw telemetry readings |
| `local_buffer` | Offline telemetry queue |
| `server_log` | Local audit/event log |
| `config` | Local configuration key-value store |
| `permissions` | RBAC permission cache |

#### MQTT Topics (Desktop)

| Topic | Direction | Purpose |
|---|---|---|
| `precisionpulse/{device_id}/telemetry` | Publish | Live sensor data |
| `precisionpulse/{device_id}/heartbeat` | Publish | Device health |
| `precisionpulse/{device_id}/command` | Subscribe | Remote commands |
| `precisionpulse/commands/{device_id}/#` | Subscribe | Targeted commands |
| `precisionpulse/commands/broadcast/#` | Subscribe | Broadcast commands |
| `precisionpulse/sync/users/#` | Subscribe | User sync |
| `precisionpulse/sync/parameters` | Subscribe | Parameter sync |
| `precisionpulse/sync/permissions/#` | Subscribe | Permission sync |
| `precisionpulse/config/update` | Subscribe | Config push |

#### Key Services

- `mqtt_service.py` — MQTT connection lifecycle, publish/subscribe
- `telemetry_service.py` — Sensor reading and publishing loop
- `offline_buffer_service.py` — Queue management when offline
- `sync_service.py` — Sync orchestration with backend
- `config_sync_service.py` — Config version management
- `user_sync_service_v2.py` — User data sync

---

### 3.3 Frontend

**Framework:** Next.js 16 (App Router)  
**API proxy:** All `/api/*` requests rewritten to `NEXT_PUBLIC_BACKEND_URL`

#### Pages

| Route | Page | Access |
|---|---|---|
| `/login` | Authentication | Public |
| `/dashboard` | Live telemetry overview | All roles |
| `/parameters` | Parameter management | admin |
| `/edit-values` | Parameter value editing | admin |
| `/telemetry` | Telemetry history | user, admin |
| `/history` | Parameter history | user, admin |
| `/users` | User management | admin |
| `/permissions` | RBAC management | admin |
| `/config` | System configuration | admin |
| `/commands` | Remote commands | admin |
| `/reports` | Report generation | user, admin |
| `/audit-logs` | Audit trail | admin |

#### Real-time Hooks

| Hook | Event | Purpose |
|---|---|---|
| `useSocket` | Socket.IO | Base connection |
| `useTelemetry` | `telemetry_update` | Live parameter values |
| `useMqttStatus` | `mqtt_status` | MQTT connectivity indicator |
| `useConfigSync` | `config_update` | Config change propagation |
| `useUserUpdates` | `user_update` | Live user list refresh |
| `useAuditLog` | `audit_log` | Live audit feed |

---

## 4. Environment Configuration

### 4.1 Backend (`config/config.py` + `.env`)

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost/precision_pulse` | PostgreSQL connection string |
| `JWT_SECRET` | *(change in production)* | JWT signing secret |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `JWT_EXPIRATION` | `86400` | Token TTL in seconds |
| `MQTT_BROKER` | `localhost` | MQTT broker hostname |
| `MQTT_PORT` | `18883` | MQTT TLS port |
| `MQTT_USE_TLS` | `true` | Enable TLS |
| `MQTT_CA_CERTS` | `config/ca.crt` | CA certificate path |
| `MQTT_KEEPALIVE` | `60` | MQTT keepalive seconds |

> **Production requirement:** Replace `JWT_SECRET` with a cryptographically random value (minimum 32 bytes).

### 4.2 Desktop (`src/core/config.py` + `.env`)

| Variable | Default | Description |
|---|---|---|
| `DATABASE_PATH` | `../data/precision_pulse.db` | SQLite file path |
| `MQTT_BROKER` | `localhost` | MQTT broker hostname |
| `MQTT_PORT` | `18883` | MQTT TLS port |
| `MQTT_USERNAME` | *(empty)* | MQTT credentials |
| `MQTT_PASSWORD` | *(empty)* | MQTT credentials |
| `MQTT_USE_TLS` | `true` | Enable TLS |
| `MQTT_CA_CERTS` | `config/ca.crt` | CA certificate path |
| `BACKEND_URL` | `http://localhost:5000` | Backend API base URL |
| `DEVICE_ID` | `desktop-001` | Unique device identifier |
| `TELEMETRY_INTERVAL` | `3` | Seconds between telemetry publishes |
| `HEARTBEAT_INTERVAL` | `30` | Seconds between heartbeats |

### 4.3 Frontend (`.env.local`)

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_BACKEND_URL` | `http://localhost:5000` | Backend API URL |
| `NEXT_PUBLIC_SOCKETIO_URL` | `http://localhost:5000` | Socket.IO server URL |
| `NEXT_PUBLIC_MQTT_BROKER` | `localhost` | MQTT broker (browser MQTT) |
| `NEXT_PUBLIC_MQTT_PORT` | `18883` | MQTT port |
| `NEXT_PUBLIC_MQTT_USE_TLS` | `true` | Enable TLS |

---

## 5. Deployment

### 5.1 Docker Compose (Recommended)

```bash
# Clone and enter project root
cd /path/to/PrecisionpulseDocs

# Start all services
docker compose up -d

# View logs
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f mosquitto

# Stop
docker compose down
```

**Service startup order:** `postgres` → `mosquitto` → `backend` → `streamer` → `frontend`

All services have `restart: unless-stopped`.

### 5.2 Service Ports

| Service | Host Port | Container Port |
|---|---|---|
| Frontend | 3000 | 3000 |
| Backend | 5000 | 5000 |
| PostgreSQL | 5432 | 5432 |
| Mosquitto (MQTT/TLS) | 18883 | 18883 |

### 5.3 Manual / Bare-Metal

#### Backend
```bash
cd dspl-precision-pulse-backend
pip install -r requirements.txt
python init_db.py          # Initialize PostgreSQL schema
python init_system_configs.py
python run.py
```

#### Desktop (GUI)
```bash
cd dspl-precision-pulse-desktop
pip install -r requirements.txt
python main.py
```

#### Desktop (Headless streamer)
```bash
python streamer.py
```

#### Frontend
```bash
cd dspl-precision-pulse-frontend
npm ci
npm run build
npm start
```

### 5.4 TLS Certificate Setup

Certificates are pre-generated in `config/`:
- `ca.crt` / `ca.key` — Certificate Authority
- `server.crt` / `server.key` — Mosquitto server certificate

For production, replace with certificates signed by your internal CA or a trusted CA. Update paths in `mosquitto.conf` and all component configs accordingly.

---

## 6. Database Operations

### 6.1 PostgreSQL (Backend)

**Initialize schema:**
```bash
python init_db.py
python init_system_configs.py
python init_telemetry_configs.py
```

**Schema auto-migration** runs on startup via `db.create_all()` and inline `ALTER TABLE IF NOT EXISTS` statements for:
- `config_change_buffer`: adds `status`, `retry_count`, `synced_at`
- `user_sync_buffer`: adds `email`

**Manual backup:**
```bash
pg_dump -U postgres precision_pulse | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

**Restore:**
```bash
gunzip -c backup_YYYYMMDD_HHMMSS.sql.gz | psql -U postgres precision_pulse
```

### 6.2 SQLite (Desktop)

**Location:** `dspl-precision-pulse-desktop/data/precision_pulse.db`

Schema is auto-created by `DatabaseManager.initialize_database()` on first launch. Migrations run automatically via `_migrate_timestamps()`.

**Manual backup:**
```bash
sqlite3 data/precision_pulse.db ".backup data/backup_$(date +%Y%m%d).db"
```

**Fix buffer tables** (if schema drift occurs):
```bash
python fix_buffer_tables.py
```

### 6.3 Sync Architecture

- Backend pushes user/parameter/config changes to Desktop via MQTT sync topics
- Desktop buffers offline changes in `local_buffer` and `config_change_buffer`
- On MQTT reconnect, `buffer_service.flush_user_changes()` and `flush_config_changes()` auto-run every 5 s
- Conflict resolution uses last-write-wins with full audit trail in `conflict_log`

---

## 7. Security

### 7.1 Authentication

- JWT tokens (HS256, 24 h TTL by default)
- Tokens passed as `Authorization: Bearer <token>` header
- Desktop supports both bcrypt (web-created users) and Argon2 (locally-created users)

### 7.2 RBAC

Three built-in roles:

| Role | Access Level |
|---|---|
| `admin` | Full access — all resources, user management, config, reports, remote commands |
| `user` | Read-only — dashboard, telemetry, history, profile, remote command view |
| `client` | No web access — desktop login, telemetry write, config read |

Permissions are defined in `app/middleware/rbac_middleware.py` and synced to Desktop via MQTT.

### 7.3 Transport Security

- All MQTT traffic uses TLS (port 18883)
- HTTP security headers set in `next.config.ts`: `X-Frame-Options`, `X-Content-Type-Options`, `X-XSS-Protection`
- CORS restricted to `localhost:3000` and `localhost:5000` — update for production domains

### 7.4 Rate Limiting

Flask-Limiter is initialized via `create_limiter()` and applied to API routes. Configure limits in `app/middleware/rate_limit_middleware.py`.

### 7.5 Production Hardening Checklist

- [ ] Replace default `JWT_SECRET` with a random 32+ byte secret
- [ ] Replace default PostgreSQL password (`postgres`)
- [ ] Replace self-signed TLS certificates with CA-signed certificates
- [ ] Update CORS `origins` in `app/__init__.py` to production domain(s)
- [ ] Update `NEXT_PUBLIC_BACKEND_URL` to production backend URL
- [ ] Set `FLASK_ENV=production` (already set in Dockerfile)
- [ ] Set `NODE_ENV=production` (already set in frontend Dockerfile)
- [ ] Restrict PostgreSQL port 5432 to internal network only
- [ ] Enable firewall rules — expose only ports 3000, 5000, 18883 externally
- [ ] Rotate MQTT credentials per device using `MQTT_USERNAME` / `MQTT_PASSWORD`

---

## 8. Monitoring & Health Checks

### 8.1 Backend Health

```bash
# API liveness
curl http://localhost:5000/api/docs

# MQTT status
curl -H "Authorization: Bearer <token>" http://localhost:5000/api/mqtt/status

# Sync status
curl -H "Authorization: Bearer <token>" http://localhost:5000/api/sync/status
```

### 8.2 Socket.IO

The backend emits the following events that can be monitored:

| Event | Payload | Meaning |
|---|---|---|
| `mqtt_status` | `{status: "online"\|"offline"}` | MQTT broker connectivity |
| `sync_status` | `{status, total, synced, unsynced}` | Data sync state |
| `internet_status` | `{connected: bool}` | Desktop internet state |
| `telemetry_update` | parameter data | Live sensor reading |

### 8.3 Data Freshness

`DataFreshnessMonitor` (initialized in `create_app()`) emits stale-data alerts via Socket.IO when no telemetry is received for >15 seconds. Frontend `ConnectivityStatusIndicator` and `MqttStatusIndicator` components surface this to users.

### 8.4 Desktop Heartbeat

Desktop publishes to `precisionpulse/{device_id}/heartbeat` every 30 s (configurable via `HEARTBEAT_INTERVAL`). Absence of heartbeat indicates device offline.

### 8.5 Log Locations

| Component | Log Output |
|---|---|
| Backend | stdout (Docker: `docker compose logs backend`) |
| Desktop | stdout + `server_log` SQLite table |
| Frontend | stdout (Docker: `docker compose logs frontend`) |
| Mosquitto | stdout (Docker: `docker compose logs mosquitto`) |

Backend log prefixes for filtering:

| Prefix | Subsystem |
|---|---|
| `[MQTT]` | MQTT subscriber/publisher |
| `[SOCKETIO]` | Socket.IO events |
| `[SYNC]` | Data sync operations |
| `[BUFFER]` | Offline buffer flush |
| `[INIT]` | Startup initialization |
| `[PERMISSION]` | RBAC operations |

---

## 9. Runbooks

### 9.1 Deploy New Version

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker compose build
docker compose up -d

# Verify all containers running
docker compose ps

# Check backend started cleanly
docker compose logs --tail=50 backend
```

### 9.2 Add a New Device

1. Assign a unique `DEVICE_ID` (e.g., `desktop-002`)
2. Set `DEVICE_ID=desktop-002` in the desktop `.env`
3. Create MQTT credentials if broker ACL is enabled
4. Start the desktop application — it will auto-register via the backend API on first sync

### 9.3 Reset Desktop Sync

If the desktop SQLite is out of sync with the backend:

```bash
# On the desktop machine
cd dspl-precision-pulse-desktop

# Delete local database (will be recreated on next start)
rm data/precision_pulse.db

# Restart desktop — DatabaseManager.initialize_database() recreates schema
# Parameters and users will re-sync via MQTT on connection
python main.py
```

### 9.4 Flush Offline Buffer Manually

```bash
# Via backend API
curl -X POST -H "Authorization: Bearer <admin_token>" \
  http://localhost:5000/api/buffer/flush
```

### 9.5 Rotate JWT Secret

1. Update `JWT_SECRET` in backend `.env`
2. Restart backend: `docker compose restart backend`
3. All existing tokens are immediately invalidated — users must re-login

### 9.6 Scale Backend Workers

The backend uses Flask-SocketIO with `async_mode='threading'`. For higher load, run behind a production WSGI server:

```bash
# Using gunicorn with eventlet
pip install gunicorn eventlet
gunicorn --worker-class eventlet -w 1 "app:create_app()" --bind 0.0.0.0:5000
```

> Note: Socket.IO requires sticky sessions if running multiple workers behind a load balancer.

---

## 10. Backup & Recovery

### 10.1 Backup Schedule (Recommended)

| Data | Frequency | Method |
|---|---|---|
| PostgreSQL full dump | Daily | `pg_dump` + gzip |
| PostgreSQL WAL | Continuous | pg_basebackup or managed DB service |
| Desktop SQLite | Daily | File copy or `sqlite3 .backup` |
| TLS certificates | On change | Secure vault |
| `.env` files | On change | Encrypted secrets manager |

### 10.2 PostgreSQL Backup

```bash
# Full backup
pg_dump -U postgres -h localhost precision_pulse \
  | gzip > /backups/precision_pulse_$(date +%Y%m%d_%H%M%S).sql.gz

# Restore
createdb -U postgres precision_pulse_restore
gunzip -c /backups/precision_pulse_YYYYMMDD_HHMMSS.sql.gz \
  | psql -U postgres precision_pulse_restore
```

### 10.3 Desktop SQLite Backup

```bash
sqlite3 data/precision_pulse.db ".backup /backups/desktop_$(date +%Y%m%d).db"
```

### 10.4 Recovery Procedure

1. Stop all services: `docker compose down`
2. Restore PostgreSQL from latest backup
3. Restore SQLite on each desktop machine
4. Start services: `docker compose up -d`
5. Verify sync status via `/api/sync/status`
6. Confirm telemetry flowing via frontend dashboard

---

## 11. Troubleshooting

### Backend won't start

| Symptom | Cause | Fix |
|---|---|---|
| `psycopg2.OperationalError` | PostgreSQL not reachable | Check `DATABASE_URL`, ensure postgres container is running |
| `Address already in use :5000` | Port conflict | `lsof -i :5000` and kill conflicting process |
| `ModuleNotFoundError` | Missing dependency | `pip install -r requirements.txt` |

### MQTT not connecting

| Symptom | Cause | Fix |
|---|---|---|
| `[MQTT] Connection failed (code: 5)` | Auth failure | Check MQTT credentials |
| `[MQTT] Connection failed (code: 3)` | Broker unavailable | Verify Mosquitto is running on port 18883 |
| TLS handshake error | Certificate mismatch | Ensure `ca.crt` matches the broker's CA |
| Desktop shows "MQTT Offline" | Broker unreachable from desktop | Check `MQTT_BROKER` env var and network routing |

### Telemetry not appearing in frontend

1. Check MQTT status indicator — must show "Online"
2. Check Socket.IO connection in browser DevTools (Network → WS)
3. Verify backend is receiving MQTT: `docker compose logs backend | grep "[MQTT] Received"`
4. Check `DataFreshnessMonitor` — stale threshold is 15 s

### Desktop sync issues

| Symptom | Fix |
|---|---|
| Users not appearing on desktop | Check MQTT `precisionpulse/sync/users/#` subscription; verify backend is publishing on user create/update |
| Parameters missing | Check `get_enabled_parameters()` — falls back to `GET /api/internal/parameters` if SQLite is empty |
| Config not updating | Check `precisionpulse/config/update` topic; verify `config_sync_service` is running |

### Frontend build fails

```bash
cd dspl-precision-pulse-frontend
rm -rf .next node_modules
npm ci
npm run build
```

### Database schema drift (Desktop)

```bash
cd dspl-precision-pulse-desktop
python fix_buffer_tables.py
```

### View audit trail

```bash
# Via API
curl -H "Authorization: Bearer <admin_token>" \
  "http://localhost:5000/api/audit-logs?limit=50"

# Direct SQLite query (desktop)
sqlite3 data/precision_pulse.db \
  "SELECT timestamp, event_type, action, resource_type, user_email FROM server_log ORDER BY timestamp DESC LIMIT 50;"
```

---

*Last updated: $(date +%Y-%m-%d) | Maintained by DSPL Engineering*
