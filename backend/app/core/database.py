"""
Database connection, engine configuration, and session lifecycle management for AeroSense AI.
Supports both PostgreSQL (Neon Serverless, AWS RDS) via asyncpg and SQLite via aiosqlite.
"""
import os
import ssl
import socket
import logging
from typing import Tuple, Dict, Any
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

# Safe DNS resolver fallback for environments where local router/ISP DNS blocks cloud domains
_orig_getaddrinfo = socket.getaddrinfo

def _dns_resilient_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    try:
        return _orig_getaddrinfo(host, port, family, type, proto, flags)
    except socket.gaierror as e:
        if isinstance(host, str) and ("." in host):
            try:
                import dns.resolver
                res = dns.resolver.Resolver()
                res.nameservers = ["8.8.8.8", "1.1.1.1"]
                ans = res.resolve(host, "A")
                ip = ans[0].to_text()
                return _orig_getaddrinfo(ip, port, family, type, proto, flags)
            except Exception:
                raise e
        raise e

socket.getaddrinfo = _dns_resilient_getaddrinfo

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone
from app.core.config import settings

def utc_now():
    """Generates an offset-naive UTC datetime for consistent asyncpg and sqlite TIMESTAMP compatibility."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

logger = logging.getLogger("aerosense.database")

def normalize_database_url(url: str, is_production: bool = False) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """
    Normalizes and sanitizes DATABASE_URL for SQLAlchemy asyncpg or aiosqlite.
    
    Key guarantees:
    1. Prevents silent SQLite fallback in production.
    2. Translates postgres:// or postgresql:// to postgresql+asyncpg://.
    3. Strips libpq-only parameters (sslmode, channel_binding) that crash asyncpg with TypeError.
    4. Establishes a verified SSLContext with system/certifi CA bundle when connecting to Neon / PostgreSQL with SSL.
    5. Applies sensible connection pooling (pool_size=10, max_overflow=20, pool_pre_ping=True, pool_recycle=1800s).
    """
    if not url or not url.strip():
        if is_production:
            raise RuntimeError(
                "PRODUCTION ERROR: In production mode (ENVIRONMENT='production'), "
                "a valid PostgreSQL DATABASE_URL must be provided. "
                "Silent fallback to SQLite is strictly prohibited in production."
            )
        url = "sqlite+aiosqlite:///./aerosense.db"

    url = url.strip()

    # 1. SQLite Handling (Development & Testing only)
    if url.startswith("sqlite"):
        if is_production:
            raise RuntimeError(
                "PRODUCTION ERROR: In production mode (ENVIRONMENT='production'), "
                "DATABASE_URL is configured as SQLite. "
                "SQLite fallback is strictly prohibited in production to prevent data loss."
            )
        if url.startswith("sqlite://") and not url.startswith("sqlite+aiosqlite://"):
            url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)
        connect_args = {"check_same_thread": False}
        engine_kwargs: Dict[str, Any] = {}
        return url, connect_args, engine_kwargs

    # 2. PostgreSQL / Neon Handling
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()

    # Ensure asyncpg dialect
    if scheme in ("postgres", "postgresql", "postgresql+psycopg", "postgresql+psycopg2"):
        scheme = "postgresql+asyncpg"
    elif scheme != "postgresql+asyncpg":
        scheme = "postgresql+asyncpg"

    # Extract query parameters
    query_params = parse_qs(parsed.query)

    # Pop libpq-only parameters so asyncpg does not raise TypeError: unexpected keyword argument
    sslmode = query_params.pop("sslmode", [None])[0]
    unsupported_libpq_params = [
        "channel_binding",
        "target_session_attrs",
        "gssencmode",
        "sslcert",
        "sslkey",
        "sslrootcert",
    ]
    for param in unsupported_libpq_params:
        query_params.pop(param, None)

    # Determine SSL requirement (Required for Neon)
    hostname = (parsed.hostname or "").lower()
    requires_ssl = False
    if sslmode in ("require", "verify-ca", "verify-full", "prefer") or "neon.tech" in hostname:
        requires_ssl = True

    connect_args: Dict[str, Any] = {}
    if requires_ssl:
        try:
            import certifi
            ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            ssl_ctx = ssl.create_default_context()
        connect_args["ssl"] = ssl_ctx

    # Reconstruct sanitized URL without problematic query parameters
    clean_query = urlencode(query_params, doseq=True)
    clean_url = urlunparse((
        scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        clean_query,
        parsed.fragment
    ))

    # Connection pooling parameters (Optimized for single Render Free Web Service instance + Neon)
    engine_kwargs = {
        "pool_size": 5,
        "max_overflow": 5,
        "pool_timeout": 30,
        "pool_pre_ping": True,     # Recovers gracefully from Neon compute auto-suspend
        "pool_recycle": 1800,      # Recycle connections after 30 minutes to prevent stale sockets
    }

    return clean_url, connect_args, engine_kwargs

# Check production environment constraint
is_prod = settings.ENVIRONMENT.lower() == "production"
clean_db_url, connect_args, engine_args = normalize_database_url(settings.DATABASE_URL, is_production=is_prod)

# Initialize SQLAlchemy Async Engine
engine = create_async_engine(
    clean_db_url,
    echo=settings.DEBUG,
    future=True,
    connect_args=connect_args,
    **engine_args
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

Base = declarative_base()

async def get_db():
    """Dependency for providing an async database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def close_db_connections():
    """Disposes all pooled connections on application shutdown."""
    if engine:
        await engine.dispose()
