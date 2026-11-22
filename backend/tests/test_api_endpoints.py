import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import engine, Base

@pytest.fixture(autouse=True)
async def init_test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/system/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "providers" in data

        net_resp = await client.get("/api/v1/system/network-status")
        assert net_resp.status_code == 200
        net_data = net_resp.json()
        assert "status" in net_data
        assert "providers" in net_data

@pytest.mark.asyncio
async def test_locations_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Search
        resp = await client.get("/api/v1/locations/search?q=Paris")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        assert data[0]["name"] == "Paris"

        # Popular
        pop_resp = await client.get("/api/v1/locations/popular")
        assert pop_resp.status_code == 200
        pop_data = pop_resp.json()
        assert len(pop_data) >= 10
        assert any(c["name"] == "Tokyo" for c in pop_data)

        # Stations
        stat_resp = await client.get("/api/v1/locations/stations?lat=35.6895&lon=139.6917&radius=40000")
        assert stat_resp.status_code == 200
        stat_data = stat_resp.json()
        assert "stations" in stat_data
        assert "count" in stat_data

@pytest.mark.asyncio
async def test_air_quality_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Current by city
        curr_resp = await client.get("/api/v1/air-quality/current?city=Tokyo&standard=US_EPA")
        assert curr_resp.status_code == 200
        curr_data = curr_resp.json()
        assert "aqi_standard_results" in curr_data
        assert "measurements" in curr_data

        # Current by coordinates
        coord_resp = await client.get("/api/v1/air-quality/current?lat=51.5074&lon=-0.1278&standard=EUROPEAN_AQI")
        assert coord_resp.status_code == 200
        coord_data = coord_resp.json()
        assert "aqi_standard_results" in coord_data

        # History
        hist_resp = await client.get("/api/v1/air-quality/history?lat=35.6895&lon=139.6917")
        assert hist_resp.status_code == 200
        hist_data = hist_resp.json()
        assert "history" in hist_data

        # Forecast
        fc_resp = await client.get("/api/v1/air-quality/forecast?lat=35.6895&lon=139.6917")
        assert fc_resp.status_code == 200
        fc_data = fc_resp.json()
        assert "forecast" in fc_data

@pytest.mark.asyncio
async def test_analytics_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Compare cities
        comp_resp = await client.get("/api/v1/analytics/compare?cities=London&cities=Tokyo&standard=US_EPA")
        assert comp_resp.status_code == 200
        comp_data = comp_resp.json()
        assert "comparison" in comp_data
        assert len(comp_data["comparison"]) == 2

        # Trends
        trends_resp = await client.get("/api/v1/analytics/trends?lat=35.6895&lon=139.6917&city=Tokyo")
        assert trends_resp.status_code == 200
        trends_data = trends_resp.json()
        assert trends_data["city"] == "Tokyo"
        assert "spike_detected" in trends_data

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
async def test_reports_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Report data
        rep_resp = await client.get("/api/v1/reports/data?city=London&period=Daily Summary&standard=US_EPA")
        assert rep_resp.status_code == 200
        rep_data = rep_resp.json()
        assert rep_data["city"] == "London"
        assert "aqi_value" in rep_data
        assert "measurements" in rep_data

        # Export PDF
        pdf_resp = await client.get("/api/v1/reports/export/pdf?city=London&period=Daily Summary&standard=US_EPA")
        assert pdf_resp.status_code == 200
        assert pdf_resp.headers["content-type"] == "application/pdf"
        assert pdf_resp.content.startswith(b"%PDF")
        assert len(pdf_resp.content) > 1000

@pytest.mark.asyncio
async def test_auth_and_alert_crud_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        test_email = f"auth_test_{uuid.uuid4().hex[:8]}@aerosense.ai"
        reg_payload = {
            "email": test_email,
            "password": "SecurePassword123!",
            "full_name": "Environmental Researcher",
            "preferred_standard": "US_EPA",
            "theme": "dark"
        }
        # Registration
        reg_resp = await client.post("/api/v1/auth/register", json=reg_payload)
        assert reg_resp.status_code == 201

        # Duplicate registration rejected with 400
        dup_resp = await client.post("/api/v1/auth/register", json=reg_payload)
        assert dup_resp.status_code == 400

        # Login failure (wrong password) rejected with 400
        bad_login = await client.post("/api/v1/auth/login", json={"email": test_email, "password": "WrongPassword!"})
        assert bad_login.status_code == 400
        assert "Incorrect email or password" in bad_login.json()["detail"]

        # Successful Login
        login_resp = await client.post("/api/v1/auth/login", json={"email": test_email, "password": "SecurePassword123!"})
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Profile / Me
        me_resp = await client.get("/api/v1/auth/me", headers=headers)
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == test_email

        # Create Alert Rule
        rule_payload = {
            "location_name": "Berlin",
            "latitude": 52.52,
            "longitude": 13.40,
            "threshold_aqi": 120.0,
            "pollutant": "pm25",
            "severity": "warning"
        }
        create_rule_resp = await client.post("/api/v1/alerts/rules", headers=headers, json=rule_payload)
        assert create_rule_resp.status_code == 201
        created_rule = create_rule_resp.json()
        rule_id = created_rule["id"]
        assert created_rule["location_name"] == "Berlin"

        # List Alert Rules
        list_rules_resp = await client.get("/api/v1/alerts/rules", headers=headers)
        assert list_rules_resp.status_code == 200
        rules = list_rules_resp.json()
        assert any(r["id"] == rule_id for r in rules)

        # List Alert Events
        events_resp = await client.get("/api/v1/alerts/events", headers=headers)
        assert events_resp.status_code == 200
        assert isinstance(events_resp.json(), list)

        # Delete Alert Rule
        del_rule_resp = await client.delete(f"/api/v1/alerts/rules/{rule_id}", headers=headers)
        assert del_rule_resp.status_code == 204

        # Verify deletion
        list_after = await client.get("/api/v1/alerts/rules", headers=headers)
        assert not any(r["id"] == rule_id for r in list_after.json())

        # Saved Locations CRUD
        loc_payload = {
            "name": "Kyoto Station",
            "country": "Japan",
            "latitude": 34.985,
            "longitude": 135.758,
            "is_favorite": True
        }
        create_loc = await client.post("/api/v1/users/saved-locations", headers=headers, json=loc_payload)
        assert create_loc.status_code == 201
        created_loc_data = create_loc.json()
        loc_id = created_loc_data["id"]
        assert created_loc_data["name"] == "Kyoto Station"

        get_locs = await client.get("/api/v1/users/saved-locations", headers=headers)
        assert get_locs.status_code == 200
        assert any(l["id"] == loc_id for l in get_locs.json())

        del_loc = await client.delete(f"/api/v1/users/saved-locations/{loc_id}", headers=headers)
        assert del_loc.status_code == 204
