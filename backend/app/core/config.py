import logging
import os
from pathlib import Path
from typing import List, Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_THIS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _THIS_DIR.parent.parent  # backend/
_ROOT_DIR = _BACKEND_DIR.parent         # project root

def _resolve_database_url() -> str:
    """
    Intelligently resolves DATABASE_URL across OS environment, root .env, and backend/.env.
    Prioritizes real PostgreSQL/Neon connection strings if present in either file.
    """
    # 1. OS environment variable takes highest precedence
    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL")

    # 2. Check root .env and backend/.env for PostgreSQL / Neon credentials
    for p in [_BACKEND_DIR / ".env", _ROOT_DIR / ".env"]:
        if p.exists():
            try:
                from dotenv import dotenv_values
                vals = dotenv_values(str(p))
                url = vals.get("DATABASE_URL")
                if url and "postgres" in url.lower():
                    return url
            except Exception as e:
                logger.debug("Failed checking %s for postgres DATABASE_URL: %s", p, e)

    # 3. Fallback to any defined DATABASE_URL in either file
    for p in [_BACKEND_DIR / ".env", _ROOT_DIR / ".env"]:
        if p.exists():
            try:
                from dotenv import dotenv_values
                vals = dotenv_values(str(p))
                url = vals.get("DATABASE_URL")
                if url:
                    return url
            except Exception as e:
                logger.debug("Failed checking %s for fallback DATABASE_URL: %s", p, e)

    return "sqlite+aiosqlite:///./aerosense.db"

def _resolve_cors_origins() -> List[str]:
    """Resolves explicit CORS allowed origins from defaults and environment configuration."""
    defaults = [
        "http://localhost:5173",
        "http://localhost:8000",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:3000",
        "https://aerosense-ai.vercel.app",
        "https://aerosense.onrender.com",
        "https://aerosense-frontend.onrender.com",
    ]
    env_origins = os.getenv("BACKEND_CORS_ORIGINS") or os.getenv("CORS_ORIGINS")
    if env_origins:
        try:
            if env_origins.startswith("[") and env_origins.endswith("]"):
                import json
                parsed = json.loads(env_origins)
                if isinstance(parsed, list):
                    for item in parsed:
                        s = str(item).strip()
                        if s and s not in defaults:
                            defaults.append(s)
                    return defaults
        except Exception as e:
            logger.debug("Failed to parse JSON formatted CORS origins: %s", e)
        for item in env_origins.split(","):
            c = item.strip()
            if c and c not in defaults:
                defaults.append(c)
    return defaults

class Settings(BaseSettings):
    PROJECT_NAME: str = "AeroSense AI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Environment & Deployment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "aerosense-super-secret-production-key-change-me-32chars")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Database: Supports SQLite (default for development/testing) and PostgreSQL (Neon, AWS RDS, etc.)
    DATABASE_URL: str = _resolve_database_url()
    
    # External APIs
    OPENAQ_API_KEY: Optional[str] = os.getenv("OPENAQ_API_KEY", "")
    WAQI_API_KEY: Optional[str] = os.getenv("WAQI_API_KEY", "")
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY", "")
    
    # CORS: Explicit allowed origins (never wildcard '*' with credentials)
    BACKEND_CORS_ORIGINS: List[str] = _resolve_cors_origins()
    
    # Rate Limiting & Safety
    MAX_REQUEST_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB
    
    @model_validator(mode="after")
    def validate_production_configuration(self):
        if self.ENVIRONMENT.lower() == "production":
            insecure_defaults = [
                "aerosense-super-secret-production-key-change-me-32chars",
                "change-me",
                "secret",
            ]
            if not self.SECRET_KEY or self.SECRET_KEY in insecure_defaults or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "PRODUCTION SECURITY ERROR: In production mode (ENVIRONMENT='production'), "
                    "a secure, randomly generated SECRET_KEY with at least 32 characters must be provided. "
                    "Insecure default or short keys are strictly prohibited."
                )
        return self

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=(str(_BACKEND_DIR / ".env"), str(_ROOT_DIR / ".env")),
        extra="ignore"
    )

settings = Settings()
