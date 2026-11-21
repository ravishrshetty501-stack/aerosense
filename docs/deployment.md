# Production Deployment Guide
**AeroSense AI — Deployment Architecture**

---

## 1. Hosting Architecture Recommendations

- **Frontend**: Vercel / Cloudflare Pages / Netlify (Static SPA with PWA service worker and CDN caching).
- **Backend**: Render / Railway / Fly.io / AWS ECS (Python 3.11 FastAPI ASGI container).
- **Database**: Managed PostgreSQL (Neon Serverless Postgres / Supabase / Render Postgres / AWS RDS).

---

## 2. Environment Variables Configuration

### Backend Environment Variables (`.env`)
```bash
# Security
SECRET_KEY=generate_a_secure_random_32_character_string
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# Database
# Production PostgreSQL example:
DATABASE_URL=postgresql+asyncpg://postgres:password@ep-cool-db.us-east-2.neon.tech/aerosense?sslmode=require
# Local fallback:
# DATABASE_URL=sqlite+aiosqlite:///./aerosense.db

# External API Integrations
OPENAQ_API_KEY=your_openaq_v3_api_key_here
GEMINI_API_KEY=your_google_gemini_api_key_here

# CORS Allowed Origins (Comma-separated in code or JSON array)
BACKEND_CORS_ORIGINS=["https://aerosense-ai.vercel.app","http://localhost:5173"]
```

---

## 3. Docker Deployment (`Dockerfile`)

Create `backend/Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 4. Vercel Frontend Configuration (`frontend/vercel.json`)

```json
{
  "rewrites": [
    { "source": "/api/(.*)", "destination": "https://your-backend.onrender.com/api/$1" },
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

---

## 5. Verification Checklist

1. [x] Backend responds `{"status":"healthy"}` on `/api/v1/system/health`.
2. [x] Database migrations create required tables automatically on startup.
3. [x] OpenAPI Swagger documentation renders at `/docs`.
4. [x] Frontend connects to backend API via reverse proxy or CORS headers.
5. [x] PWA manifest and service worker load cleanly on HTTPS origins.
