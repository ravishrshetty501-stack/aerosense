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

    # 4th call must raise HTTPException 429
    with pytest.raises(Exception) as exc_info:
        await limiter(req)
    assert "429" in str(exc_info.value)
