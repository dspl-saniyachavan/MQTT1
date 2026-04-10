# PrecisionPulse

Real-time industrial telemetry platform with a Flask backend, Next.js web dashboard, and PySide6 desktop client — all connected via MQTT over TLS.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Docker Host                          │
│                                                             │
│  ┌──────────┐   MQTT/TLS   ┌────────────┐   HTTP/WS        │
│  │ Desktop  │◄────────────►│ Mosquitto  │                  │
│  │ Streamer │              │  (18883)   │                  │
│  └──────────┘              └─────┬──────┘                  │
│                                  │ MQTT                    │
│  ┌──────────┐   REST/WS   ┌──────▼──────┐   SQL            │
│  │ Frontend │◄───────────►│   Backend   │◄────►┌──────────┐│
│  │  (3000)  │             │   (5000)    │      │ Postgres ││
│  └──────────┘             └─────────────┘      └──────────┘│
└─────────────────────────────────────────────────────────────┘
```

| Component | Stack | Port |
|-----------|-------|------|
| Backend API | Python 3.11 · Flask · Flask-SocketIO · SQLAlchemy | 5000 |
| Web Frontend | Next.js 16 · React 19 · Tailwind CSS | 3000 |
| Desktop Client | Python 3.11 · PySide6 · paho-mqtt | — |
| Database | PostgreSQL 15 | 5432 |
| Message Broker | Eclipse Mosquitto 2 (TLS) | 18883 |

---

## Prerequisites

| Tool | Minimum version | Install |
|------|----------------|---------|
| Docker | 24+ | https://docs.docker.com/get-docker/ |
| Docker Compose | v2 (plugin) | bundled with Docker Desktop |
| Git | any | https://git-scm.com |
| Python | 3.11+ | only for desktop client (local run) |
| Node.js | 20+ | only for frontend (local run) |

---

## Quick Start (Docker — recommended)

### 1. Clone the repository

```bash
git clone https://github.com/<your-org>/PrecisionpulseDocs.git
cd PrecisionpulseDocs
```

### 2. Create environment file

```bash
cp .env.example .env
```

Edit `.env` and set the two required secrets:

```bash
# Generate strong secrets
python3 -c "import secrets; print(secrets.token_hex(32))"
```

```env
JWT_SECRET=<paste-generated-secret>
SECRET_KEY=<paste-different-generated-secret>
```

### 3. Set kernel parameter (required for SonarQube / Elasticsearch — skip if not using SonarQube)

```bash
sudo sysctl -w vm.max_map_count=262144
```

### 4. Start all services

```bash
docker compose up -d --build
```

### 5. Open the app

| Service | URL |
|---------|-----|
| Web Dashboard | http://localhost:3000 |
| Backend API | http://localhost:5000 |
| API Docs (Swagger) | http://localhost:5000/api/docs |

### Default credentials

| Email | Password | Role |
|-------|----------|------|
| admin@precisionpulse.com | admin123 | admin |

> **Change the default password immediately after first login.**

---

## Local Development (without Docker)

### Backend

```bash
cd dspl-precision-pulse-backend

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create venv and install all deps from uv.lock
uv sync

# Copy and configure environment
cp .env.example .env   # fill in JWT_SECRET and SECRET_KEY

# Run database migrations
uv run flask db upgrade

# Start server
uv run python run.py
```

### Frontend

```bash
cd dspl-precision-pulse-frontend

# Install dependencies
npm install

# Copy environment
cp .env.local.example .env.local   # fill in JWT_SECRET

# Start dev server
npm run dev
```

### Desktop Client

```bash
cd dspl-precision-pulse-desktop

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create venv and install all deps from uv.lock
uv sync

# Start desktop app
uv run python main.py
```

---

## Environment Variables

### Backend (`dspl-precision-pulse-backend/.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | yes | `postgresql://postgres:postgres@localhost/precision_pulse` | PostgreSQL connection string |
| `JWT_SECRET` | **yes** | — | 64-char hex secret for signing JWTs |
| `SECRET_KEY` | **yes** | — | Flask session secret |
| `MQTT_BROKER` | no | `localhost` | Mosquitto hostname |
| `MQTT_PORT` | no | `18883` | Mosquitto TLS port |
| `MQTT_USE_TLS` | no | `true` | Enable TLS for MQTT |
| `MQTT_CA_CERTS` | no | `config/ca.crt` | Path to CA certificate |
| `FLASK_ENV` | no | `development` | Set to `production` in prod |
| `PORT` | no | `5000` | HTTP port |

### Frontend (`dspl-precision-pulse-frontend/.env.local`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JWT_SECRET` | **yes** | — | Must match backend `JWT_SECRET` |
| `NEXT_PUBLIC_BACKEND_URL` | yes | `http://localhost:5000` | Backend base URL |
| `NEXT_PUBLIC_SOCKETIO_URL` | yes | `http://localhost:5000` | Socket.IO server URL |

### Desktop (`dspl-precision-pulse-desktop/.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BACKEND_URL` | no | `http://localhost:5000` | Backend base URL |
| `MQTT_BROKER` | no | `localhost` | Mosquitto hostname |
| `MQTT_PORT` | no | `18883` | Mosquitto TLS port |
| `DEVICE_ID` | no | `desktop-001` | Unique device identifier |

---

## Production Deployment

### Deploying to a remote server

1. **Copy `.env.example` to `.env`** and fill in all secrets and your server's public IP/domain:

```env
NEXT_PUBLIC_BACKEND_URL=http://YOUR_SERVER_IP:5000
NEXT_PUBLIC_SOCKETIO_URL=http://YOUR_SERVER_IP:5000
JWT_SECRET=<strong-secret>
SECRET_KEY=<strong-secret>
POSTGRES_PASSWORD=<strong-password>
```

2. **Open firewall ports**: `3000` (frontend), `5000` (backend), `18883` (MQTT)

3. **Start services**:

```bash
docker compose up -d --build
```

4. **View logs**:

```bash
docker compose logs -f backend
docker compose logs -f frontend
```

### Using a reverse proxy (Nginx)

For HTTPS in production, place Nginx in front:

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Backend API + Socket.IO
    location /api/ {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /socket.io/ {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

---


## Key Features

- **Real-time telemetry** — Desktop streams sensor data via MQTT → Backend → Web dashboard via Socket.IO
- **Offline resilience** — Desktop buffers data locally when MQTT disconnects; auto-flushes on reconnect
- **Role-based access control** — `admin` / `user` roles enforced on both frontend and backend
- **Configuration sync** — Admin changes system config in web UI → propagated to desktop via Socket.IO
- **Audit logging** — All user actions, config changes, and login events are logged
- **Report generation** — CSV / PDF / Excel export of telemetry data
- **Conflict resolution** — Timestamp-based conflict detection for concurrent edits
- **TLS MQTT** — All MQTT traffic encrypted with self-signed certificates

---

## Running Tests

### Backend

```bash
cd dspl-precision-pulse-backend
uv run pytest tests/ -v
```

### Frontend

```bash
cd dspl-precision-pulse-frontend
npm test
```

### Desktop

```bash
cd dspl-precision-pulse-desktop
uv run pytest tests/ -v
```

---

## SonarQube Code Analysis

```bash
# Start SonarQube (requires vm.max_map_count=262144)
sudo sysctl -w vm.max_map_count=262144
docker compose -f docker-compose.sonar.yml up -d

# Run analysis for all three projects
./run-sonar-scan.sh
```

Dashboard: http://localhost:9000 (admin / Admin@123456)

---

## Stopping Services

```bash
# Stop all containers
docker compose down

# Stop and remove volumes (deletes database data)
docker compose down -v
```

