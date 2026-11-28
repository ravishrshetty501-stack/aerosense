import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.security import verify_password, get_password_hash, create_access_token, decode_access_token
from app.core.rate_limit import InMemoryRateLimiter
from fastapi import Request

@pytest.mark.asyncio
async def test_security_headers_enforced():
    """Verify that all defensive HTTP security headers are populated on responses."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. API endpoint on HTTP (should NOT emit HSTS on local HTTP)
        resp = await client.get("/api/v1/system/health")
        assert resp.status_code == 200
        headers = resp.headers
        assert headers.get("x-content-type-options") == "nosniff"
        assert headers.get("x-frame-options") == "DENY"
        assert headers.get("x-xss-protection") == "1; mode=block"
        assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"
        assert "geolocation" in headers.get("permissions-policy", "")
        assert "default-src 'none'" in headers.get("content-security-policy", "")
        assert "strict-transport-security" not in headers

        # 2. API endpoint through HTTPS reverse-proxy (should emit production HSTS)
        resp_https = await client.get("/api/v1/system/health", headers={"X-Forwarded-Proto": "https"})
        assert resp_https.status_code == 200
        assert resp_https.headers.get("strict-transport-security") == "max-age=31536000"

        # 3. Swagger documentation endpoint (should emit Swagger UI specific CSP)
        docs_resp = await client.get("/docs")
        assert docs_resp.status_code == 200
        docs_csp = docs_resp.headers.get("content-security-policy", "")
        assert "cdn.jsdelivr.net" in docs_csp
        assert "unsafe-eval" not in docs_csp

@pytest.mark.asyncio
async def test_unauthorized_endpoints_rejected():
    """Verify that endpoints requiring authentication reject unauthenticated requests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Without authorization header
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code in [401, 403]

        # With invalid/tampered bearer token
        resp_tampered = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.payload"})
        assert resp_tampered.status_code in [401, 403]

@pytest.mark.asyncio
async def test_jwt_lifecycle_and_tampering():
    """Verify JWT access token creation, decoding, and tamper detection."""
    test_sub = "analyst-uuid-999"
    token = create_access_token(test_sub)
    assert token is not None

    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded.get("sub") == test_sub

    # Tampered token verification
    tampered_token = token[:-4] + "fake"
    tampered_decoded = decode_access_token(tampered_token)
    assert tampered_decoded is None

def test_bcrypt_72_byte_boundary_safety():
    """Verify that passwords exceeding 72 bytes are safely hashed without internal exceptions."""
    long_password = "A" * 150  # 150 characters, well beyond the 72-byte bcrypt limit
    hashed = get_password_hash(long_password)
    assert hashed is not None
    assert hashed.startswith("$2b$")

    # Correct password matches
    assert verify_password(long_password, hashed) is True
    # Altered prefix fails
    assert verify_password("B" * 150, hashed) is False

@pytest.mark.asyncio
async def test_ai_chat_input_validation_boundary():
    """Verify that chat prompts exceeding maximum character limits are rejected with 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Prompt exceeding 2000 characters
        overflow_message = "Test pollution inquiry " * 150
        payload = {"message": overflow_message, "location_hint": "Tokyo"}
        resp = await client.post("/api/v1/ai/chat", json=payload)
        assert resp.status_code == 422  # Unprocessable Entity due to Field max_length constraint

@pytest.mark.asyncio
async def test_in_memory_rate_limiter_unit():
    """Verify sliding-window rate limiter triggers 429 when threshold exceeded."""
    limiter = InMemoryRateLimiter(requests_limit=3, window_seconds=10)

    class MockRequest:
        headers = {}
        client = type("Client", (), {"host": "192.168.1.100"})()

    req = MockRequest()
    # 3 allowed calls
    await limiter(req)
    await limiter(req)
    await limiter(req)

    # 4th call must raise HTTPException 429 with Retry-After header
    with pytest.raises(Exception) as exc_info:
        await limiter(req)
    assert "429" in str(exc_info.value)
    assert exc_info.value.status_code == 429
    assert int(exc_info.value.headers["Retry-After"]) >= 1


def _make_mock_request(peer_host: str | None, headers: dict | None = None):
    class MockRequest:
        def __init__(self, host, hdrs):
            self.headers = hdrs or {}
            self.client = type("Client", (), {"host": host})() if host is not None else None

    return MockRequest(peer_host, headers)


@pytest.mark.asyncio
async def test_rate_limiter_ignores_spoofed_headers_from_untrusted_peer():
    """Requests from untrusted peers must ignore X-Forwarded-For / X-Real-IP and enforce limit on peer IP."""
    limiter = InMemoryRateLimiter(requests_limit=2, window_seconds=30, trusted_proxies=["10.0.0.0/8"])

    # Rotating spoofed X-Forwarded-For and X-Real-IP values from same untrusted peer
    await limiter(_make_mock_request("198.51.100.25", {"x-forwarded-for": "1.1.1.1"}))
    await limiter(_make_mock_request("198.51.100.25", {"x-forwarded-for": "2.2.2.2", "x-real-ip": "3.3.3.3"}))

    with pytest.raises(Exception) as exc_info:
        await limiter(_make_mock_request("198.51.100.25", {"x-forwarded-for": "4.4.4.4"}))
    assert exc_info.value.status_code == 429
    assert int(exc_info.value.headers["Retry-After"]) >= 1
    assert list(limiter._history.keys()) == ["198.51.100.25"]


@pytest.mark.asyncio
async def test_rate_limiter_trusted_proxy_rightmost_untrusted_ip_and_fail_closed():
    """Trusted proxy resolves rightmost non-proxy XFF IP, ignores X-Real-IP, and fails closed on malformed/missing XFF."""
    limiter = InMemoryRateLimiter(requests_limit=2, window_seconds=30, trusted_proxies=["10.0.0.0/8", "172.16.0.0/12"])

    # 1. Missing forwarding headers from trusted proxy falls back to peer IP
    await limiter(_make_mock_request("10.0.0.5", {}))
    assert "10.0.0.5" in limiter._history

    # 2. Trusted peer with spoofed X-Real-IP and missing XFF must ignore X-Real-IP
    await limiter(_make_mock_request("10.0.0.5", {"x-real-ip": "203.0.113.99"}))
    assert "203.0.113.99" not in limiter._history

    # Now peer 10.0.0.5 itself is at requests_limit=2; next fail-closed request raises 429
    with pytest.raises(Exception) as exc_info:
        await limiter(_make_mock_request("10.0.0.5", {"x-forwarded-for": "not-an-ip", "x-real-ip": "203.0.113.11"}))
    assert exc_info.value.status_code == 429
    assert "203.0.113.11" not in limiter._history

    # Fresh trusted peer IP 10.0.0.6 for remaining header-validation cases
    # 3. Malformed XFF without X-Real-IP fails closed to peer IP (not garbage or forged left-hand IP)
    await limiter(_make_mock_request("10.0.0.6", {"x-forwarded-for": "203.0.113.55, bad;ip"}))
    assert "bad;ip" not in limiter._history
    assert "203.0.113.55" not in limiter._history
    assert "10.0.0.6" in limiter._history

    # 4. Malformed rightmost XFF after trailing trusted proxy hop cannot expose forged left-hand IP
    await limiter(_make_mock_request("10.0.0.6", {"x-forwarded-for": "203.0.113.55, not-an-ip, 172.16.0.2"}))
    assert "203.0.113.55" not in limiter._history
    assert len(limiter._history["10.0.0.6"]) == 2

    # 5. All-trusted XFF chain falls back to peer IP (10.0.0.7) instead of trusting X-Real-IP
    await limiter(_make_mock_request("10.0.0.7", {"x-forwarded-for": "172.16.0.2, 10.0.0.2", "x-real-ip": "203.0.113.88"}))
    assert "203.0.113.88" not in limiter._history
    assert "10.0.0.7" in limiter._history

    # 6. Multiple trusted hops followed by an untrusted hop stop at the rightmost untrusted hop
    await limiter(
        _make_mock_request(
            "10.0.0.5",
            {"x-forwarded-for": "1.1.1.1, 198.51.100.77, 172.16.0.4, 10.0.0.2"},
        )
    )
    assert "198.51.100.77" in limiter._history
    assert "1.1.1.1" not in limiter._history
    assert "172.16.0.4" not in limiter._history
    assert "10.0.0.2" not in limiter._history

    # Enforcement for extracted client 198.51.100.77 reaches limit independently
    await limiter(_make_mock_request("10.0.0.5", {"x-forwarded-for": "198.51.100.77, 10.0.0.2"}))
    with pytest.raises(Exception) as exc_info:
        await limiter(_make_mock_request("10.0.0.5", {"x-forwarded-for": "198.51.100.77"}))
    assert exc_info.value.status_code == 429
    assert int(exc_info.value.headers["Retry-After"]) >= 1


@pytest.mark.asyncio
async def test_rate_limiter_capacity_preserves_active_quotas_uses_overflow_and_avoids_scan_churn(monkeypatch):
    """High-cardinality floods cannot evict active quotas, saturate O(1) without per-request scans, and obey overflow policy."""
    monkeypatch.setenv("TRUSTED_PROXIES", "invalid-cidr, 172.16.0.0/12")
    fake_now = 1_000_000.0
    monkeypatch.setattr("app.core.rate_limit.time.time", lambda: fake_now)

    limiter = InMemoryRateLimiter(requests_limit=2, window_seconds=30, max_clients=3)

    purge_calls = 0
    orig_purge = limiter._purge_expired_records

    def counted_purge(now: float):
        nonlocal purge_calls
        purge_calls += 1
        return orig_purge(now)

    monkeypatch.setattr(limiter, "_purge_expired_records", counted_purge)

    # Active Client A reaches its limit (already blocked); Client B uses 1 of 2 quota; Client C uses 1 of 2
    await limiter(_make_mock_request("172.16.0.10", {"x-forwarded-for": "198.51.100.1"}))
    await limiter(_make_mock_request("172.16.0.10", {"x-forwarded-for": "198.51.100.1"}))
    await limiter(_make_mock_request("172.16.0.10", {"x-forwarded-for": "198.51.100.2"}))
    await limiter(_make_mock_request("172.16.0.10", {"x-forwarded-for": "198.51.100.3"}))
    assert len(limiter._history) == 3

    # High-cardinality flood of 25 unseen IPs within cooldown triggers at most 1 full cleanup scan
    # and routes unseen IPs into the bounded overflow bucket instead of evicting .1/.2/.3
    allowed_overflow = 0
    blocked_overflow = 0
    for last_octet in range(10, 35):
        req = _make_mock_request("172.16.0.10", {"x-forwarded-for": f"198.51.100.{last_octet}"})
        try:
            await limiter(req)
            allowed_overflow += 1
        except Exception as exc:
            assert exc.status_code == 429
            assert int(exc.headers["Retry-After"]) >= 1
            blocked_overflow += 1

    assert purge_calls == 1
    assert allowed_overflow == 2  # Matches requests_limit=2 shared overflow policy
    assert blocked_overflow == 23
    assert len(limiter._history) == 3
    assert set(limiter._history.keys()) == {"198.51.100.1", "198.51.100.2", "198.51.100.3"}

    # Already rate-limited Client A MUST still be blocked with 429; repeated blocked requests trigger zero scan churn
    for _ in range(5):
        with pytest.raises(Exception) as exc_info:
            await limiter(_make_mock_request("172.16.0.10", {"x-forwarded-for": "198.51.100.1"}))
        assert exc_info.value.status_code == 429
    assert purge_calls == 1

    # Partially used Client B still has strictly 1 remaining slot, then hits 429 (quota not reset!)
    await limiter(_make_mock_request("172.16.0.10", {"x-forwarded-for": "198.51.100.2"}))
    with pytest.raises(Exception) as exc_info:
        await limiter(_make_mock_request("172.16.0.10", {"x-forwarded-for": "198.51.100.2"}))
    assert exc_info.value.status_code == 429

    # Once active windows actually expire past 30s, periodic cleanup frees capacity for new clients
    fake_now += 31.0
    await limiter(_make_mock_request("172.16.0.10", {"x-forwarded-for": "198.51.100.99"}))
    assert "198.51.100.99" in limiter._history
    assert "198.51.100.1" not in limiter._history


@pytest.mark.asyncio
async def test_fastapi_asgi_rate_limiter_integration(monkeypatch):
    """End-to-end ASGI test exercising real FastAPI app middleware stack and production auth_limiter."""
    from collections import OrderedDict
    from app.core.database import get_db
    from app.core.rate_limit import auth_limiter

    class _FakeScalarResult:
        def scalar_one_or_none(self):
            return None

    class _FakeAsyncSession:
        async def execute(self, *_args, **_kwargs):
            return _FakeScalarResult()

    async def _override_get_db():
        yield _FakeAsyncSession()

    monkeypatch.setattr(auth_limiter, "requests_limit", 2)
    monkeypatch.setattr(auth_limiter, "_trusted_networks", ())
    monkeypatch.setattr(auth_limiter, "_history", OrderedDict())
    monkeypatch.setattr(auth_limiter, "_overflow_timestamps", [])

    app.dependency_overrides[get_db] = _override_get_db
    try:
        transport = ASGITransport(app=app, client=("198.51.100.50", 12345))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            for idx in range(2):
                resp = await client.post(
                    "/api/v1/auth/login",
                    json={"email": "nonexistent@example.com", "password": "wrong"},
                    headers={"X-Forwarded-For": f"1.2.3.{idx + 1}", "X-Real-IP": f"5.6.7.{idx + 1}"},
                )
                assert resp.status_code == 400
                assert resp.headers.get("x-content-type-options") == "nosniff"

            # 3rd request from same untrusted peer with rotated spoofed headers must hit 429
            blocked_resp = await client.post(
                "/api/v1/auth/login",
                json={"email": "nonexistent@example.com", "password": "wrong"},
                headers={"X-Forwarded-For": "9.9.9.9", "X-Real-IP": "8.8.8.8"},
            )
            assert blocked_resp.status_code == 429
            assert int(blocked_resp.headers["Retry-After"]) >= 1
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_rate_limiter_constructor_validation_and_valid_numeric_configs(monkeypatch):
    """Constructor must fail fast with ValueError on invalid configs while honoring valid ints/floats."""
    from app.core.rate_limit import ai_chat_limiter, auth_limiter, report_limiter

    # Preserve existing module-level instance defaults
    assert (ai_chat_limiter.requests_limit, ai_chat_limiter.window_seconds, ai_chat_limiter.max_clients) == (25, 60, 10000)
    assert (auth_limiter.requests_limit, auth_limiter.window_seconds, auth_limiter.max_clients) == (10, 60, 10000)
    assert (report_limiter.requests_limit, report_limiter.window_seconds, report_limiter.max_clients) == (15, 60, 10000)

    # Invalid requests_limit: bool, zero, negative, floats (including integral floats), strings, None, non-finite
    for bad_limit in (True, False, 0, -1, 10.0, 2.5, float("inf"), float("nan"), "10", None, [5]):
        with pytest.raises(ValueError, match="requests_limit"):
            InMemoryRateLimiter(requests_limit=bad_limit)

    # Invalid window_seconds: bool, zero, negative, NaN, +/-inf, overflow int, strings, None, other types
    for bad_window in (True, False, 0, 0.0, -5, -0.5, float("nan"), float("inf"), float("-inf"), 10**400, "60", None, {}):
        with pytest.raises(ValueError, match="window_seconds"):
            InMemoryRateLimiter(window_seconds=bad_window)

    # Invalid max_clients: bool, zero, negative, floats (including integral floats), strings, None
    for bad_max_clients in (True, False, 0, -10, 100.0, 10.5, float("inf"), float("nan"), "100", None, (10,)):
        with pytest.raises(ValueError, match="max_clients"):
            InMemoryRateLimiter(max_clients=bad_max_clients)

    # Valid float window_seconds and positive integer configs still enforce sliding-window limits cleanly
    now = 2_000_000.0
    monkeypatch.setattr("app.core.rate_limit.time.time", lambda: now)

    float_limiter = InMemoryRateLimiter(requests_limit=2, window_seconds=2.5, max_clients=5)
    req = _make_mock_request("198.51.100.44")
    await float_limiter(req)
    await float_limiter(req)
    with pytest.raises(Exception) as exc_info:
        await float_limiter(req)
    assert exc_info.value.status_code == 429
    assert int(exc_info.value.headers["Retry-After"]) >= 1

    # Window slides cleanly once > 2.5s elapse
    now += 2.6
    await float_limiter(req)


@pytest.mark.asyncio
async def test_reports_and_ai_tool_routes_enforce_rate_limits_and_hide_internal_errors(monkeypatch, caplog):
    """Verify report_limiter and ai_chat_limiter execute via ASGI and raw internal errors are never leaked."""
    import logging
    from collections import OrderedDict
    from unittest.mock import AsyncMock
    from app.core.rate_limit import ai_chat_limiter, report_limiter
    from app.services.ai_service import ai_service
    from app.services.providers.manager import data_manager
    from app.services.report_service import report_service

    # Reset limiters cleanly under deterministic limits
    monkeypatch.setattr(report_limiter, "requests_limit", 2)
    monkeypatch.setattr(report_limiter, "_trusted_networks", ())
    monkeypatch.setattr(report_limiter, "_history", OrderedDict())
    monkeypatch.setattr(report_limiter, "_overflow_timestamps", [])

    monkeypatch.setattr(ai_chat_limiter, "requests_limit", 2)
    monkeypatch.setattr(ai_chat_limiter, "_trusted_networks", ())
    monkeypatch.setattr(ai_chat_limiter, "_history", OrderedDict())
    monkeypatch.setattr(ai_chat_limiter, "_overflow_timestamps", [])

    mock_city = [{"name": "Tokyo", "latitude": 35.6895, "longitude": 139.6917}]
    mock_report = {
        "city": "Tokyo",
        "period": "Daily Summary",
        "generated_at": "2026-11-27 12:00 UTC",
        "aqi_value": 40,
        "aqi_category": "Good",
        "dominant_pollutant": "PM25",
        "primary_source": "WAQI",
        "is_ground_observation": True,
        "measurements": {"pm25": {"value": 10.0, "unit": "ug/m3", "type": "ground_observation", "source": "WAQI"}},
        "health_advisory": "Safe.",
    }

    monkeypatch.setattr(data_manager, "search_cities", AsyncMock(return_value=mock_city))
    monkeypatch.setattr(report_service, "generate_report_data", AsyncMock(return_value=mock_report))

    transport = ASGITransport(app=app, client=("198.51.100.77", 12345))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Reports routes share report_limiter (1 call to /data + 1 call to /export/pdf -> 3rd gets 429)
        r1 = await client.get("/api/v1/reports/data?city=Tokyo")
        assert r1.status_code == 200
        r2 = await client.get("/api/v1/reports/export/pdf?city=Tokyo")
        assert r2.status_code == 200
        assert r2.content.startswith(b"%PDF")
        r3 = await client.get("/api/v1/reports/export/pdf?city=Tokyo")
        assert r3.status_code == 429
        assert int(r3.headers["Retry-After"]) >= 1

        # 2. /api/v1/ai/tool allows unauthenticated access (preserving optional auth) and enforces ai_chat_limiter
        with caplog.at_level(logging.ERROR):
            monkeypatch.setattr(
                data_manager,
                "get_unified_air_quality",
                AsyncMock(side_effect=RuntimeError("db_secret=xyz https://provider.internal/?token=SECRET_KEY")),
            )
            ai_res1 = await client.post(
                "/api/v1/ai/tool",
                json={"tool_name": "get_air_quality", "arguments": {"location": "Tokyo"}},
            )
            assert ai_res1.status_code == 200
            err_body = ai_res1.json()
            assert err_body == {"error": "Tool execution failed due to an internal service error."}
            assert "SECRET_KEY" not in err_body["error"]
            assert "provider.internal" not in err_body["error"]

        # Expected server-side log captured without returning secrets publicly
        assert any("Unexpected error executing tool 'get_air_quality'" in rec.message for rec in caplog.records)

        # Validation error for unknown tool stays clear
        ai_res2 = await client.post(
            "/api/v1/ai/tool",
            json={"tool_name": "invalid_tool_name", "arguments": {}},
        )
        assert ai_res2.status_code == 200
        assert "Unknown tool" in ai_res2.json()["error"]

        # 3rd call hits ai_chat_limiter -> 429 with Retry-After
        ai_res3 = await client.post(
            "/api/v1/ai/tool",
            json={"tool_name": "get_air_quality", "arguments": {"location": "Tokyo"}},
        )
        assert ai_res3.status_code == 429
        assert int(ai_res3.headers["Retry-After"]) >= 1

    # Direct execute_tool validation sanity
    invalid_args_res = await ai_service.execute_tool("get_air_quality", "not-a-dict")  # type: ignore[arg-type]
    assert "Invalid tool arguments" in invalid_args_res["error"]
