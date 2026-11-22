from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "AeroSense AI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "aerosense-super-secret-production-key-change-me-32chars")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Database: Supports SQLite (default) and PostgreSQL
    # Example PostgreSQL: postgresql+asyncpg://user:pass@localhost:5432/aerosense
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./aerosense.db")
    
    # External APIs
    OPENAQ_API_KEY: Optional[str] = os.getenv("OPENAQ_API_KEY", "")
    WAQI_API_KEY: Optional[str] = os.getenv("WAQI_API_KEY", "")
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY", "")
    
    # CORS: Explicit allowed origins (never wildcard '*' with credentials)
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:8000",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:3000",
        "https://aerosense-ai.vercel.app"
    ]
    
    # Rate Limiting & Safety
    MAX_REQUEST_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB
    
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=("backend/.env", ".env"),
        extra="ignore"
    )

settings = Settings()
