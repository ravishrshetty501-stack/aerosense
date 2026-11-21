import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import engine, Base

@pytest.fixture(autouse=True)
async def init_test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/system/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "providers" in data

@pytest.mark.asyncio
async def test_location_search_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/locations/search?q=Paris")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        assert data[0]["name"] == "Paris"

@pytest.mark.asyncio
async def test_aqi_calculate_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"pm25": 12.0, "pm10": 20.0}
        resp = await client.post("/api/v1/aqi/calculate?standard=US_EPA", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["aqi"] == 50
        assert data["category"] == "Good"

@pytest.mark.asyncio
async def test_auth_registration_and_me():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        test_email = "tester@aerosense.ai"
        reg_payload = {
            "email": test_email,
            "password": "SecurePassword123!",
            "full_name": "Environmental Researcher",
            "preferred_standard": "US_EPA",
            "theme": "dark"
        }
        reg_resp = await client.post("/api/v1/auth/register", json=reg_payload)
        assert reg_resp.status_code in [201, 400] # 400 if already exists in test run
        
        login_resp = await client.post("/api/v1/auth/login", json={"email": test_email, "password": "SecurePassword123!"})
        assert login_resp.status_code == 200
        token_data = login_resp.json()
        token = token_data["access_token"]
        assert token is not None
        
        # Test me
        me_resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["email"] == test_email
