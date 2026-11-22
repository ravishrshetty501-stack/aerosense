"""
Pre-Deployment Verification Script for AeroSense AI on Render + Neon PostgreSQL.
Executes all required pre-flight checks:
1. Production dependency check.
2. Production startup & security configuration validation.
3. Health endpoints test (/health, /api/v1/system/health).
4. Neon PostgreSQL connectivity & Render pooling check (pool_size=5, max_overflow=5, timeout=30).
5. User authentication & JWT flow against Neon.
6. Real WAQI API ground station integration check.
7. Real Google Gemini GenAI integration check.
"""
import sys
import os
import uuid
import asyncio
from pathlib import Path

# Add backend directory to path
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ROOT_DIR = _BACKEND_DIR.parent
sys.path.insert(0, str(_BACKEND_DIR))

import httpx
from sqlalchemy import text
from app.core.config import settings, Settings
from app.core.database import engine, AsyncSessionLocal, normalize_database_url
from app.main import app

async def run_pre_deployment_checks():
    print("=" * 80)
    print("AEROSENSE AI — PRE-DEPLOYMENT VERIFICATION SUITE FOR RENDER FREE TIER")
    print("=" * 80)
    results = {}

    # 1. Production Dependency Import Check
    print("\n[Check 1/7] Verifying Production Dependency Availability...")
    required_modules = [
        "fastapi", "uvicorn", "pydantic", "pydantic_settings",
        "sqlalchemy", "greenlet", "aiosqlite", "asyncpg", "httpx",
        "jwt", "passlib", "bcrypt", "certifi", "dns.resolver",
        "dotenv", "reportlab"
    ]
    missing = []
    for mod in required_modules:
        try:
            __import__(mod)
        except ImportError as e:
            missing.append(f"{mod} ({e})")
    
    if missing:
        print(f"  [FAIL] Missing dependencies: {missing}")
        results["dependencies"] = False
    else:
        print(f"  [PASS] All {len(required_modules)} required production packages verified.")
        results["dependencies"] = True

    # 2. Production Security & Startup Validation
    print("\n[Check 2/7] Verifying Production Configuration Guards...")
    try:
        # A. SQLite rejection in production
        try:
            normalize_database_url("sqlite:///./prod_test.db", is_production=True)
            print("  [FAIL] SQLite was not rejected in production mode!")
            results["sqlite_guard"] = False
        except RuntimeError:
            print("  [PASS] SQLite fallback strictly rejected when ENVIRONMENT=production.")
            results["sqlite_guard"] = True

        # B. Insecure SECRET_KEY rejection in production
        try:
            Settings(
                ENVIRONMENT="production",
                SECRET_KEY="short_key",
                DATABASE_URL=settings.DATABASE_URL
            )
            print("  [FAIL] Insecure SECRET_KEY was not rejected in production!")
            results["secret_key_guard"] = False
        except ValueError:
            print("  [PASS] Insecure SECRET_KEY (<32 chars) strictly rejected when ENVIRONMENT=production.")
            results["secret_key_guard"] = True

        # C. Valid production configuration initialization
        prod_test_settings = Settings(
            ENVIRONMENT="production",
            SECRET_KEY="aerosense-production-verified-secret-key-64-bytes-token-secure",
            DATABASE_URL=settings.DATABASE_URL
        )
        print("  [PASS] Production settings successfully validated with secure key.")
        results["prod_config"] = True
    except Exception as e:
        print(f"  [FAIL] Production configuration check failed: {e}")
        results["prod_config"] = False

    # 3. Health Endpoint Verification (ASGI Transport)
    print("\n[Check 3/7] Testing Health Check Endpoints...")
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Test /health
            resp1 = await client.get("/health")
            assert resp1.status_code == 200, f"/health returned {resp1.status_code}"
            assert resp1.json()["status"] == "healthy"
            print("  [PASS] GET /health returned 200 OK (Fast root health check)")

            # Test /api/v1/system/health
            resp2 = await client.get("/api/v1/system/health")
            assert resp2.status_code == 200, f"/api/v1/system/health returned {resp2.status_code}"
            h_data = resp2.json()
            assert h_data["status"] == "healthy"
            print(f"  [PASS] GET /api/v1/system/health returned 200 OK (Full telemetry check)")
            print(f"         Providers: {h_data.get('providers')}")
        results["health_endpoints"] = True
    except Exception as e:
        print(f"  [FAIL] Health endpoint check failed: {e}")
        results["health_endpoints"] = False

    # 4. Database Connectivity & Render Pooling Check against Neon
    print("\n[Check 4/7] Testing Database Connectivity & Connection Pool Sizing...")
    try:
        clean_url, connect_args, engine_kwargs = normalize_database_url(settings.DATABASE_URL, is_production=False)
        print(f"  [INFO] Engine Pool Sizing: pool_size={engine_kwargs.get('pool_size')}, "
              f"max_overflow={engine_kwargs.get('max_overflow')}, "
              f"timeout={engine_kwargs.get('pool_timeout')}s, "
              f"pre_ping={engine_kwargs.get('pool_pre_ping')}")
        assert engine_kwargs.get("pool_size") == 5, f"Expected pool_size=5, got {engine_kwargs.get('pool_size')}"
        assert engine_kwargs.get("max_overflow") == 5, f"Expected max_overflow=5, got {engine_kwargs.get('max_overflow')}"
        assert engine_kwargs.get("pool_timeout") == 30, f"Expected pool_timeout=30, got {engine_kwargs.get('pool_timeout')}"
        
        async with AsyncSessionLocal() as session:
            db_ver = (await session.execute(text("SELECT version();"))).scalar()
            db_name = (await session.execute(text("SELECT current_database();"))).scalar()
            print(f"  [PASS] Connected to Neon PostgreSQL: {db_name}")
            print(f"         PostgreSQL Version: {db_ver.split(',')[0] if db_ver else 'Unknown'}")
        results["database"] = True
    except Exception as e:
        print(f"  [FAIL] Database check failed: {e}")
        results["database"] = False

    # 5. User Authentication Flow against Live Neon Database
    print("\n[Check 5/7] Testing User Registration & Authentication Flow...")
    test_user_id = None
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            rand_suffix = uuid.uuid4().hex[:6]
            test_email = f"render_deploy_tester_{rand_suffix}@aerosense.ai"
            test_password = "RenderSecurePass2026!"
            
            # Register
            reg_resp = await client.post("/api/v1/auth/register", json={
                "email": test_email,
                "password": test_password,
                "full_name": "Render Deployment Test Agent",
                "preferred_standard": "US_EPA",
                "theme": "dark"
            })
            assert reg_resp.status_code == 201, f"Registration returned {reg_resp.status_code}: {reg_resp.text}"
            reg_data = reg_resp.json()
            test_user_id = reg_data.get("user", {}).get("id")
            print(f"  [PASS] User registration succeeded in Neon (ID: {str(test_user_id)[:8]}...)")

            # Login
            login_resp = await client.post("/api/v1/auth/login", json={
                "email": test_email,
                "password": test_password
            })
            assert login_resp.status_code == 200, f"Login returned {login_resp.status_code}"
            token = login_resp.json().get("access_token")
            assert token, "Access token missing"
            print("  [PASS] User authentication succeeded (JWT token generated)")

            # /auth/me
            me_resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
            assert me_resp.status_code == 200
            assert me_resp.json()["email"] == test_email
            print("  [PASS] User profile retrieved via authenticated Bearer token")

        # Cleanup test user
        if test_user_id:
            async with AsyncSessionLocal() as session:
                await session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": test_user_id})
                await session.commit()
            print("  [PASS] Test user safely purged from Neon (Zero leftover artifacts)")
        results["auth"] = True
    except Exception as e:
        print(f"  [FAIL] Authentication check failed: {e}")
        # Best effort cleanup
        if test_user_id:
            try:
                async with AsyncSessionLocal() as session:
                    await session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": test_user_id})
                    await session.commit()
            except Exception:
                pass
        results["auth"] = False

    # 6. WAQI Live Environmental Provider Integration
    print("\n[Check 6/7] Testing WAQI (World Air Quality Index) Integration...")
    waqi_key = getattr(settings, "WAQI_API_KEY", "")
    if waqi_key:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                # Query Singapore station feed
                waqi_url = f"https://api.waqi.info/feed/geo:1.2868;103.8545/?token={waqi_key}"
                resp = await client.get(waqi_url)
                if resp.status_code == 200 and resp.json().get("status") == "ok":
                    data = resp.json().get("data", {})
                    station_city = data.get("city", {}).get("name", "Singapore")
                    aqi_val = data.get("aqi")
                    print(f"  [PASS] REAL LIVE WAQI Integration Verified!")
                    print(f"         Station: {station_city}")
                    print(f"         Physical Ground AQI: {aqi_val}")
                    print(f"         Attribution: {data.get('attributions', [{}])[0].get('name', 'EPA / NEA')}")
                    results["waqi"] = "REAL_LIVE_PASS"
                else:
                    print(f"  [WARN] WAQI returned status={resp.status_code}, data={resp.text[:80]}")
                    results["waqi"] = "DEGRADED"
        except Exception as e:
            print(f"  [WARN] WAQI query failed with network exception: {e}")
            results["waqi"] = "NETWORK_ERROR"
    else:
        print("  [INFO] WAQI_API_KEY not set. Open-Meteo CAMS fallback active.")
        results["waqi"] = "FALLBACK_ACTIVE"

    # 7. Google Gemini GenAI Live Integration
    print("\n[Check 7/7] Testing Google Gemini GenAI Integration...")
    gemini_key = getattr(settings, "GEMINI_API_KEY", "")
    if gemini_key:
        try:
            from app.services.ai_service import ai_service
            # Direct quick grounded query
            gemini_resp = await ai_service.chat("Briefly define PM2.5 in one short sentence.")
            if gemini_resp and "response" in gemini_resp and len(gemini_resp["response"]) > 10:
                print("  [PASS] REAL LIVE Gemini GenAI Integration Verified!")
                print(f"         Model Output Preview: {gemini_resp['response'][:90]}...")
                results["gemini"] = "REAL_LIVE_PASS"
            else:
                print("  [WARN] Gemini returned empty response; fallback engine active.")
                results["gemini"] = "FALLBACK_ACTIVE"
        except Exception as e:
            print(f"  [WARN] Gemini request failed or quota exceeded: {e}")
            print("         Deterministic AI rule engine remains active as seamless fallback.")
            results["gemini"] = "FALLBACK_ACTIVE"
    else:
        print("  [INFO] GEMINI_API_KEY not configured. Deterministic AI rule engine active.")
        results["gemini"] = "FALLBACK_ACTIVE"

    print("\n" + "=" * 80)
    print("PRE-DEPLOYMENT VERIFICATION SUMMARY")
    print("=" * 80)
    for k, v in results.items():
        print(f"  - {k:<25}: {v}")
    
    all_core_passed = (
        results.get("dependencies") and
        results.get("sqlite_guard") and
        results.get("secret_key_guard") and
        results.get("prod_config") and
        results.get("health_endpoints") and
        results.get("database") and
        results.get("auth")
    )
    
    if all_core_passed:
        print("\nOVERALL STATUS: READY FOR RENDER FREE WEB SERVICE DEPLOYMENT!")
        return True
    else:
        print("\nOVERALL STATUS: PRE-DEPLOYMENT CHECKS FAILED! Review errors above.")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_pre_deployment_checks())
    sys.exit(0 if success else 1)
