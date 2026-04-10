# PrecisionPulse — Production Deployment Guide

## Prerequisites

| Tool | Min version | Notes |
|------|-------------|-------|
| Ubuntu/Debian server | 22.04 LTS | Any Linux distro works |
| Docker Engine | 24+ | [Install guide](https://docs.docker.com/engine/install/ubuntu/) |
| Docker Compose | v2 (plugin) | Bundled with Docker Engine 24+ |
| Git | any | To clone the repo |
| Open ports | 3000, 5000, 18883 | In your firewall / security group |

---

## 1. Server Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version
docker compose version
```

---

## 2. Clone the Repository

```bash
git clone https://github.com/<your-org>/Precisionpulse.git
cd Precisionpulse
```

---

## 3. Configure Environment

```bash
cp .env.example .env
```

Generate strong secrets:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Edit `.env` — every value marked **REQUIRED** must be set:

```env
# Database
POSTGRES_DB=precision_pulse
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<strong-password>          # REQUIRED

# Secrets
JWT_SECRET=<64-char-hex>                     # REQUIRED
SECRET_KEY=<different-64-char-hex>           # REQUIRED

# Frontend — replace with your server's public IP or domain
NEXT_PUBLIC_BACKEND_URL=http://<SERVER_IP>:5000
NEXT_PUBLIC_SOCKETIO_URL=http://<SERVER_IP>:5000

# Desktop streamer device ID (optional)
DEVICE_ID=desktop-001
```

> Never commit `.env` to version control. It is already in `.gitignore`.

---

## 4. Open Firewall Ports

### UFW (Ubuntu)

```bash
sudo ufw allow 3000/tcp   # Frontend
sudo ufw allow 5000/tcp   # Backend API
sudo ufw allow 18883/tcp  # MQTT over TLS
sudo ufw enable
sudo ufw status
```
---

## 5. Build and Start All Services

```bash
docker compose up -d --build
```

This starts: `postgres`, `mosquitto`, `backend`, `frontend`.

Check all containers are healthy:

```bash
docker compose ps
```

Expected output — all services should show `running` or `healthy`:

```
NAME            STATUS
pp_postgres     running (healthy)
pp_mosquitto    running
pp_backend      running (healthy)
pp_streamer     running
pp_frontend     running
```

---

## 6. Run Database Migration


 apply the migration directly:

```bash
docker compose exec backend uv run alembic upgrade head
```

---

## 7. Verify Deployment

| Check | Command |
|-------|---------|
| Backend health | `curl http://<SERVER_IP>:5000/api/internal/health` |
| Frontend | Open `http://<SERVER_IP>:3000` in browser |
| API docs | Open `http://<SERVER_IP>:5000/api/docs` in browser |

Default login:

| Email | Password | Role |
|-------|----------|------|
| admin@precisionpulse.com | admin123 | admin |

**Change the default password immediately after first login.**

---

## 8. HTTPS with Nginx (Recommended for Production)

### Install Nginx and Certbot

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

### Configure Nginx

Create `/etc/nginx/sites-available/precisionpulse`:

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
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Backend REST API
    location /api/ {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Socket.IO (requires WebSocket upgrade)
    location /socket.io/ {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/precisionpulse /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Obtain TLS Certificate

```bash
sudo certbot --nginx -d yourdomain.com
```

Certbot auto-renews. Test renewal:

```bash
sudo certbot renew --dry-run
```

### Update `.env` for HTTPS

```env
NEXT_PUBLIC_BACKEND_URL=https://yourdomain.com
NEXT_PUBLIC_SOCKETIO_URL=https://yourdomain.com
```

Rebuild the frontend to bake in the new URLs:

```bash
docker compose up -d --build frontend
```

---

## 9. Useful Operations

### View logs

```bash
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f streamer
docker compose logs --tail=100 postgres
```

### Restart a single service

```bash
docker compose restart backend
```

### Stop everything

```bash
docker compose down
```

### Stop and wipe all data (destructive)

```bash
docker compose down -v
```

### Pull latest code and redeploy

```bash
git pull
docker compose up -d --build
```

---

## 10. Backups

### PostgreSQL

```bash
# Dump
docker compose exec postgres pg_dump \
  -U ${POSTGRES_USER:-postgres} precision_pulse \
  | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz

# Restore
gunzip -c backup_<timestamp>.sql.gz \
  | docker compose exec -T postgres psql \
      -U ${POSTGRES_USER:-postgres} precision_pulse
```

### Desktop SQLite

The SQLite database lives in the `desktop_data` Docker volume. Back it up with:

```bash
docker run --rm \
  -v precisionpulsedocs_desktop_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/sqlite_$(date +%Y%m%d).tar.gz /data
```

---

## 11. Monitoring

### Container resource usage

```bash
docker stats
```

### Health endpoints

```bash
# Backend
curl http://localhost:5000/api/internal/health

# PostgreSQL
docker compose exec postgres pg_isready -U postgres
```

### Auto-restart on server reboot

Docker containers already have `restart: unless-stopped` in `docker-compose.yml`. To ensure Docker itself starts on boot:

```bash
sudo systemctl enable docker
```

---

## 12. Security Checklist

- [ ] Changed default `admin@precisionpulse.com` password
- [ ] Set strong `JWT_SECRET` and `SECRET_KEY` (64-char hex each)
- [ ] Set strong `POSTGRES_PASSWORD`
- [ ] HTTPS enabled via Nginx + Let's Encrypt
- [ ] Firewall allows only ports 80, 443, 18883 (close 3000 and 5000 once Nginx is in front)
- [ ] `.env` not committed to git
- [ ] Regular PostgreSQL backups scheduled (cron)
- [ ] `docker compose pull` run periodically for security patches on base images

---

## 13. Troubleshooting

| Symptom | Check |
|---------|-------|
| Backend container keeps restarting | `docker compose logs backend` — usually a missing `JWT_SECRET` or DB connection failure |
| Frontend shows "Cannot connect to backend" | Verify `NEXT_PUBLIC_BACKEND_URL` matches the server IP/domain and port 5000 is reachable |
| MQTT not connecting | Check `docker compose logs mosquitto` and verify TLS certs in `dspl-precision-pulse-backend/config/` |
| Socket.IO disconnects immediately | Ensure Nginx `proxy_read_timeout` is set and the `/socket.io/` location block has the WebSocket upgrade headers |
| Database migration fails | Run `docker compose exec backend uv run flask db current` to check current revision, then `uv run flask db upgrade` |
| Port already in use | `sudo lsof -i :<port>` to find the conflicting process |
<!-- WARNING:app.services.cache_service:[CACHE] Redis unavailable (Error 111 connecting to localhost:6379. Connection refused.), using in-memory fallback
data points on web app chart is not showing properly its changing x and y axis directly -->
