"""
Tests for Neon PostgreSQL URL normalization, SSL injection, and schema integrity.
"""
import pytest
import ssl
from app.core.database import normalize_database_url, Base
import app.models

def test_neon_url_normalization_with_sslmode_and_channel_binding():
    neon_url = "postgresql://neondb_owner:secret_pass_123@ep-aerosense-production-123456.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=prefer"
    
    clean_url, connect_args, engine_kwargs = normalize_database_url(neon_url, is_production=False)
    
    # 1. Scheme translated to asyncpg
    assert clean_url.startswith("postgresql+asyncpg://")
    
    # 2. Problematic libpq parameters stripped from query string
    assert "sslmode" not in clean_url
    assert "channel_binding" not in clean_url
    
    # 3. SSLContext passed via connect_args
    assert "ssl" in connect_args
    assert isinstance(connect_args["ssl"], ssl.SSLContext)
    
    # 4. Sensible pooling options (Optimized for single Render Free Web Service + Neon)
    assert engine_kwargs.get("pool_size") == 5
    assert engine_kwargs.get("max_overflow") == 5
    assert engine_kwargs.get("pool_pre_ping") is True
    assert engine_kwargs.get("pool_recycle") == 1800
    assert engine_kwargs.get("pool_timeout") == 30

def test_production_secret_key_validation():
    from app.core.config import Settings
    import os
    
    # Insecure secret key in production must raise ValueError
    with pytest.raises(ValueError, match=r"PRODUCTION SECURITY ERROR"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="short-key",
            DATABASE_URL="postgresql://user:pass@ep-test.ap-southeast-1.aws.neon.tech/neondb"
        )
        
    with pytest.raises(ValueError, match=r"PRODUCTION SECURITY ERROR"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="aerosense-super-secret-production-key-change-me-32chars",
            DATABASE_URL="postgresql://user:pass@ep-test.ap-southeast-1.aws.neon.tech/neondb"
        )
        
    # Secure secret key in production succeeds
    valid_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="super-strong-production-cryptographic-key-1234567890",
        DATABASE_URL="postgresql://user:pass@ep-test.ap-southeast-1.aws.neon.tech/neondb"
    )
    assert valid_settings.ENVIRONMENT == "production"
    assert len(valid_settings.SECRET_KEY) >= 32

def test_postgres_legacy_scheme_translation():
    legacy_url = "postgres://neondb_owner:secret@db.neon.tech/neondb"
    clean_url, connect_args, engine_kwargs = normalize_database_url(legacy_url, is_production=False)
    
    assert clean_url.startswith("postgresql+asyncpg://")
    assert "ssl" in connect_args

def test_sqlite_fallback_allowed_in_development():
    sqlite_url = "sqlite:///./dev.db"
    clean_url, connect_args, engine_kwargs = normalize_database_url(sqlite_url, is_production=False)
    
    assert clean_url == "sqlite+aiosqlite:///./dev.db"
    assert connect_args.get("check_same_thread") is False
    assert "pool_size" not in engine_kwargs

def test_sqlite_fallback_forbidden_in_production():
    with pytest.raises(RuntimeError, match=r"strictly prohibited in production"):
        normalize_database_url("sqlite:///./prod.db", is_production=True)
        
    with pytest.raises(RuntimeError, match=r"strictly prohibited in production"):
        normalize_database_url("", is_production=True)

def test_all_12_models_registered_in_metadata():
    expected_tables = {
        "users",
        "saved_locations",
        "locations",
        "monitoring_stations",
        "measurements",
        "aqi_calculations",
        "alert_rules",
        "alert_events",
        "chat_sessions",
        "chat_messages",
        "environmental_reports",
        "api_usage_logs"
    }
    registered_tables = set(Base.metadata.tables.keys())
    assert expected_tables.issubset(registered_tables), f"Missing tables: {expected_tables - registered_tables}"
