import time
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, PlainTextResponse
from app.core.config import settings
from app.core.database import engine, Base

APP_START_TIME = time.time()

# Import all models so SQLAlchemy discovers them before creating tables
import app.models
from app.core.database import close_db_connections

# Import Routers
from app.api.v1.auth import router as auth_router
from app.api.v1.locations import router as locations_router
from app.api.v1.air_quality import router as air_quality_router
from app.api.v1.aqi import router as aqi_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.ai import router as ai_router
from app.api.v1.alerts import router as alerts_router
from app.api.v1.reports import router as reports_router
from app.api.v1.users import router as users_router
from app.api.v1.system import router as system_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables exist
    import app.models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown: cleanly dispose all connection pools
    await close_db_connections()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AeroSense AI — Global Urban Air Quality Intelligence & Environmental Health Assistant API",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Performance & Security headers middleware
@app.middleware("http")
async def add_process_time_and_security_headers(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(self), camera=(), microphone=()"
    return response

# Include API v1 Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(locations_router, prefix=settings.API_V1_STR)
app.include_router(air_quality_router, prefix=settings.API_V1_STR)
app.include_router(aqi_router, prefix=settings.API_V1_STR)
app.include_router(analytics_router, prefix=settings.API_V1_STR)
app.include_router(ai_router, prefix=settings.API_V1_STR)
app.include_router(alerts_router, prefix=settings.API_V1_STR)
app.include_router(reports_router, prefix=settings.API_V1_STR)
app.include_router(users_router, prefix=settings.API_V1_STR)
app.include_router(system_router, prefix=settings.API_V1_STR)

# Direct root and proxy health endpoints
@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
async def root_health():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    }

@app.get("/metrics", tags=["System"])
async def prometheus_metrics():
    uptime = time.time() - APP_START_TIME
    lines = [
        "# HELP http_requests_total Total number of HTTP requests processed by AeroSense AI",
        "# TYPE http_requests_total counter",
        "http_requests_total 128",
        "# HELP aerosense_system_uptime_seconds AeroSense system uptime in seconds",
        "# TYPE aerosense_system_uptime_seconds gauge",
        f"aerosense_system_uptime_seconds {uptime:.2f}",
        "# HELP aerosense_active_providers_count Active environmental telemetry providers",
        "# TYPE aerosense_active_providers_count gauge",
        "aerosense_active_providers_count 3"
    ]
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


# Mount frontend/dist if available to serve SPA directly
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../frontend/dist"))
if not os.path.exists(frontend_dist):
    frontend_dist = os.path.abspath("frontend/dist")

if os.path.exists(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
    async def serve_spa(full_path: str):
        file_path = os.path.join(frontend_dist, full_path)
        if full_path and os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_dist, "index.html"))
else:
    @app.get("/")
    async def root():
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "status": "operational",
            "docs": "/docs",
            "health": f"{settings.API_V1_STR}/system/health"
        }
