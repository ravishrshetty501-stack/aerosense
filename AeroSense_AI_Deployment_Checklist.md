# AeroSense AI — Production Deployment Checklist
**Platform:** AeroSense AI — Global Urban Air Quality Intelligence Platform  
**Target:** Production Release (Docker / Linux VPS / AWS / Render / Cloud Run)  
**Security Standard:** Zero Hardcoded Secrets • Principle of Least Privilege

---

## 1. Pre-Deployment Prerequisites

- [ ] **Python Runtime:** Python 3.11.x or 3.12.x installed.
- [ ] **Node.js Runtime:** Node.js v20.x+ LTS and npm v10.x+.
- [ ] **Database Server:** PostgreSQL 15+ instance with accessible credentials, OR local persistent SQLite.
- [ ] **Domain & SSL:** Qualified domain name pointing to server IP with Let's Encrypt SSL.
- [ ] **Upstream API Accounts:**
  - Google Gemini API Key (Gemini 1.5/3.8 Flash enabled)
  - WAQI API Token (Physical ground sensor access)

---

## 2. Environment Variables Template

Create `.env` in the project root. **Never commit this file to version control.**

```bash
# ==============================================================================
# AeroSense AI — Production Environment Configuration
# ==============================================================================

# Core Application Settings
PROJECT_NAME="AeroSense AI"
VERSION="1.0.0"
ENVIRONMENT="production"
DEBUG=False

# Server & Networking
HOST="0.0.0.0"
PORT=8000
BACKEND_CORS_ORIGINS=["https://aerosense.ai","https://app.aerosense.ai"]

# Security & Authentication
# Generate with: openssl rand -hex 32
SECRET_KEY="generate_a_random_32_byte_hex_string_here"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Database Configuration
# Production PostgreSQL (asyncpg driver automatically injected):
DATABASE_URL="postgresql://aerosense_user:your_secure_password@db-host:5432/aerosense_prod"
# Fallback local SQLite:
# DATABASE_URL="sqlite:///./aerosense.db"

# Environmental Data Providers
WAQI_API_KEY="your_waqi_api_token_here"
GEMINI_API_KEY="your_google_gemini_api_key_here"
OPENAQ_API_KEY="" # Optional secondary fallback

# Rate Limiting & Performance
RATE_LIMIT_AUTH_PER_MINUTE=20
RATE_LIMIT_AI_PER_MINUTE=30
```

---

## 3. Database Initialization & Migration

Execute inside the backend virtual environment:

```bash
# 1. Activate Python virtual environment
source backend/venv/bin/activate  # On Linux/macOS
# .\backend\venv\Scripts\Activate.ps1 # On Windows

# 2. Run database migration script (creates all 12 tables and indices)
python -c "
import asyncio
from app.core.database import engine, Base
import app.models.user
import app.models.measurement
import app.models.alert
import app.models.chat
import app.models.report

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('All 12 database tables successfully provisioned.')

asyncio.run(init_db())
"
```

---

## 4. Frontend Production Build

Compile optimized, code-split client assets:

```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install production dependencies
npm ci

# 3. Compile TypeScript & build bundle with Vite
npm run build

# 4. Verify output in frontend/dist/
ls -lh dist/assets/
# Confirms:
# - react-vendor chunk (~171 KB)
# - recharts chunk (~367 KB)
# - maplibre chunk (~801 KB lazy-loaded)
# - main entry shell (~43 KB)
```

---

## 5. Backend Production Launch

### Option A: Docker Compose (Recommended)
```bash
# Build and launch detached container
docker compose up -d --build

# Inspect logs
docker compose logs -f backend
```

### Option B: Systemd Daemon (Linux Host)
Create `/etc/systemd/system/aerosense.service`:
```ini
[Unit]
Description=AeroSense AI FastAPI Service
After=network.target postgresql.service

[Service]
Type=simple
User=aerosense
WorkingDirectory=/opt/aerosense
EnvironmentFile=/opt/aerosense/.env
ExecStart=/opt/aerosense/backend/venv/bin/gunicorn app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --access-logfile /var/log/aerosense/access.log \
    --error-logfile /var/log/aerosense/error.log
Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target
```
Activate service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now aerosense.service
sudo systemctl status aerosense.service
```

---

## 6. Reverse Proxy & SSL Configuration (Nginx)

Place in `/etc/nginx/sites-available/aerosense`:
```nginx
server {
    listen 80;
    server_name aerosense.ai app.aerosense.ai;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name aerosense.ai app.aerosense.ai;

    ssl_certificate /etc/letsencrypt/live/aerosense.ai/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/aerosense.ai/privkey.pem;

    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security Headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "geolocation=(self), camera=(), microphone=()" always;

    # Gzip Compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

## 7. Post-Deployment Smoke Verification

Run these verification checks immediately after deployment:

1. **Health Check:**
   ```bash
   curl -s https://app.aerosense.ai/health | jq .
   # Expected: {"status": "healthy", "service": "AeroSense AI", "version": "1.0.0"}
   ```

2. **Metrics Check:**
   ```bash
   curl -s https://app.aerosense.ai/metrics
   # Expected: Prometheus formatted gauges and counters
   ```

3. **Telemetry Provider Check:**
   ```bash
   curl -s https://app.aerosense.ai/api/v1/system/network-status | jq .
   # Expected: "status": "operational", "waqi": {"status": "connected"}
   ```

4. **Full 20-Workflow Test Suite:**
   ```bash
   BASE_URL=https://app.aerosense.ai python scratch/smoke_test_20.py
   # Expected: 20/20 PASSED
   ```

---

## 8. Rollback & Emergency Contingency

If a production incident occurs:
1. **Immediate Service Reversion:**
   ```bash
   # Revert to previous Git tag
   git checkout tags/v0.9.8-stable
   cd frontend && npm run build
   sudo systemctl restart aerosense.service
   ```
2. **Provider Failover Verification:**
   - If WAQI API quota is exhausted, verify that the application auto-switches to Open-Meteo Copernicus CAMS fallback without 500 errors.
   - If Google Gemini quota is exceeded, verify that the deterministic rule-based grounding engine answers user inquiries.
