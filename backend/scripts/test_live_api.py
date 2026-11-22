import asyncio
import httpx
import uuid

async def test_live_api():
    print("Testing live FastAPI API against Neon PostgreSQL backend...")
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=15.0) as client:
        # 1. Health
        health_resp = await client.get("/api/v1/system/health")
        print(f"[Health Check] Status: {health_resp.status_code}")
        assert health_resp.status_code == 200

        # 2. Register a unique test user
        unique_suffix = uuid.uuid4().hex[:6]
        user_email = f"neon_tester_{unique_suffix}@aerosense.ai"
        user_pw = "SecureNeonTest123!"
        reg_payload = {
            "email": user_email,
            "password": user_pw,
            "full_name": "Neon Integration Tester",
            "preferred_standard": "US_EPA",
            "theme": "dark"
        }
        reg_resp = await client.post("/api/v1/auth/register", json=reg_payload)
        print(f"[Register User] Status: {reg_resp.status_code}, Email: {user_email}")
        assert reg_resp.status_code == 201

        # 3. Login
        login_resp = await client.post("/api/v1/auth/login", json={"email": user_email, "password": user_pw})
        print(f"[Login User] Status: {login_resp.status_code}")
        assert login_resp.status_code == 200
        tokens = login_resp.json()
        access_token = tokens["access_token"]
        auth_headers = {"Authorization": f"Bearer {access_token}"}

        # 4. Get Current User Profile
        me_resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        print(f"[Get /auth/me] Status: {me_resp.status_code}, User ID: {me_resp.json().get('id')}")
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == user_email

        # 5. Saved Locations CRUD
        add_loc_payload = {
            "name": "Marina Bay, Singapore",
            "country": "Singapore",
            "latitude": 1.2868,
            "longitude": 103.8545,
            "is_favorite": True
        }
        add_loc_resp = await client.post("/api/v1/users/saved-locations", json=add_loc_payload, headers=auth_headers)
        print(f"[Add Saved Location] Status: {add_loc_resp.status_code}")
        assert add_loc_resp.status_code == 201
        loc_data = add_loc_resp.json()
        loc_id = loc_data["id"]

        # List saved locations
        list_loc_resp = await client.get("/api/v1/users/saved-locations", headers=auth_headers)
        saved_items = list_loc_resp.json()
        print(f"[List Saved Locations] Status: {list_loc_resp.status_code}, Count: {len(saved_items)}")
        assert list_loc_resp.status_code == 200
        assert any(l["id"] == loc_id for l in saved_items)

        # Delete saved location
        del_loc_resp = await client.delete(f"/api/v1/users/saved-locations/{loc_id}", headers=auth_headers)
        print(f"[Delete Saved Location] Status: {del_loc_resp.status_code}")
        assert del_loc_resp.status_code == 204

        # 6. AQI Calculate endpoint
        aqi_calc_resp = await client.post("/api/v1/aqi/calculate?standard=US_EPA", json={"pm25": 35.4, "pm10": 50.0})
        print(f"[AQI Calculate] Status: {aqi_calc_resp.status_code}, AQI: {aqi_calc_resp.json().get('aqi')}")
        assert aqi_calc_resp.status_code == 200

        print("\n" + "=" * 60)
        print("ALL LIVE NEON BACKEND API TESTS 100% PASSED!")
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_live_api())
