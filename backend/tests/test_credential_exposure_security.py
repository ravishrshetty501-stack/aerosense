import logging
from typing import Any, List
import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock

from app.main import app
from app.core.config import settings
from app.core.redaction import install_log_redaction, format_safe_exception, redact_sensitive_text
from app.api.v1 import system as system_module
from app.services.ai_service import ai_service
from app.services.providers.waqi import WAQIProvider


DUMMY_GEMINI_KEY = "dummy-gemini-secret-key-999111"
DUMMY_WAQI_TOKEN = "dummy-waqi-secret-token-888222"
DUMMY_OPENAQ_KEY = "dummy-openaq-secret-key-777333"


@pytest.fixture(autouse=True)
def reset_network_cache():
    system_module._network_status_cache["data"] = None
    system_module._network_status_cache["expires_at"] = None
    yield
    system_module._network_status_cache["data"] = None
    system_module._network_status_cache["expires_at"] = None


@pytest.mark.asyncio
async def test_gemini_uses_header_auth_and_omits_key_from_url_across_tool_followup(monkeypatch, caplog):
    """Gemini requests must place the API key in x-goog-api-key header, never in the URL query string."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", DUMMY_GEMINI_KEY)
    captured_requests: List[httpx.Request] = []
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        captured_requests.append(request)
        if call_count == 1:
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {
                                "role": "model",
                                "parts": [
                                    {"functionCall": {"name": "get_air_quality", "args": {"location": "Tokyo"}}}
                                ],
                            }
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [{"text": "Verified Tokyo briefing completed."}],
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.services.ai_service.httpx.AsyncClient",
        lambda **kwargs: real_async_client(transport=transport, **{k: v for k, v in kwargs.items() if k != "transport"}),
    )
    monkeypatch.setattr(
        ai_service,
        "execute_tool",
        AsyncMock(return_value={"city": "Tokyo", "aqi_summary": {"aqi": 45}}),
    )

    with caplog.at_level(logging.DEBUG):
        result = await ai_service.chat("What is air quality in Tokyo?")

    assert len(captured_requests) == 2
    for req in captured_requests:
        assert "key=" not in str(req.url)
        assert DUMMY_GEMINI_KEY not in str(req.url)
        assert req.headers.get("x-goog-api-key") == DUMMY_GEMINI_KEY

    assert result["response"] == "Verified Tokyo briefing completed."
    assert DUMMY_GEMINI_KEY not in caplog.text


@pytest.mark.asyncio
async def test_gemini_http_error_and_exception_never_leak_key_and_fallback_safely(monkeypatch, caplog):
    """Gemini HTTP errors/exceptions must redact credentials from logs/responses and still fall back."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", DUMMY_GEMINI_KEY)

    def failing_handler(request: httpx.Request) -> httpx.Response:
        if "gemini-2.5-flash-lite" in str(request.url):
            return httpx.Response(403, text=f"API_KEY_INVALID key={DUMMY_GEMINI_KEY}")
        raise httpx.ConnectError(f"upstream failed with header x-goog-api-key={DUMMY_GEMINI_KEY}", request=request)

    transport = httpx.MockTransport(failing_handler)
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.services.ai_service.httpx.AsyncClient",
        lambda **kwargs: real_async_client(transport=transport, **{k: v for k, v in kwargs.items() if k != "transport"}),
    )

    with caplog.at_level(logging.DEBUG):
        api_transport = ASGITransport(app=app)
        async with AsyncClient(transport=api_transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/ai/chat",
                json={"message": "What is air quality in Tokyo?", "location_hint": "Tokyo"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["model"] == "aerosense-deterministic-grounded-engine"
    assert DUMMY_GEMINI_KEY not in resp.text
    assert DUMMY_GEMINI_KEY not in caplog.text
    for rec in caplog.records:
        assert DUMMY_GEMINI_KEY not in rec.getMessage()
        assert DUMMY_GEMINI_KEY not in (rec.exc_text or "")


@pytest.mark.asyncio
async def test_waqi_preserves_query_token_contract_while_scrubbing_logs_and_api_errors(monkeypatch, caplog):
    """WAQI status check must send ?token= as documented while never disclosing the token in responses or logs."""
    monkeypatch.setattr(settings, "WAQI_API_KEY", DUMMY_WAQI_TOKEN)
    waqi_urls: List[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if "api.waqi.info" in str(request.url):
            waqi_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "error", "data": f"Invalid key ?token={DUMMY_WAQI_TOKEN}"})
        return httpx.Response(200, json={"current": {"european_aqi": 20}})

    mock_transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.api.v1.system.httpx.AsyncClient",
        lambda **kwargs: real_async_client(
            transport=mock_transport, **{k: v for k, v in kwargs.items() if k != "transport"}
        ),
    )

    with caplog.at_level(logging.DEBUG):
        api_transport = ASGITransport(app=app)
        async with AsyncClient(transport=api_transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/system/network-status")

    assert resp.status_code == 200
    assert any(f"token={DUMMY_WAQI_TOKEN}" in u for u in waqi_urls)
    assert DUMMY_WAQI_TOKEN not in resp.text
    assert DUMMY_WAQI_TOKEN not in caplog.text


@pytest.mark.asyncio
async def test_waqi_httpx_exception_never_exposes_token_or_url_in_network_status_or_provider(monkeypatch, caplog):
    """Raw httpx timeout/connection exceptions containing WAQI token URLs must never reach API clients or logs."""
    monkeypatch.setattr(settings, "WAQI_API_KEY", DUMMY_WAQI_TOKEN)

    def error_handler(request: httpx.Request) -> httpx.Response:
        if "api.waqi.info" in str(request.url):
            raise httpx.ReadTimeout(
                f"Timed out fetching {request.url}",
                request=request,
            )
        return httpx.Response(200, json={"current": {"european_aqi": 20}})

    mock_transport = httpx.MockTransport(error_handler)
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.api.v1.system.httpx.AsyncClient",
        lambda **kwargs: real_async_client(
            transport=mock_transport, **{k: v for k, v in kwargs.items() if k != "transport"}
        ),
    )
    monkeypatch.setattr(
        "app.services.providers.waqi.httpx.AsyncClient",
        lambda **kwargs: real_async_client(
            transport=mock_transport, **{k: v for k, v in kwargs.items() if k != "transport"}
        ),
    )

    with caplog.at_level(logging.DEBUG):
        api_transport = ASGITransport(app=app)
        async with AsyncClient(transport=api_transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/system/network-status")

        provider = WAQIProvider(api_key=DUMMY_WAQI_TOKEN)
        aq = await provider.get_current_air_quality(35.68, 139.69, "Tokyo")
        stations = await provider.find_nearby_stations(35.68, 139.69)

    assert resp.status_code == 200
    payload = resp.json()
    waqi_info = payload["providers"]["waqi"]
    assert waqi_info["status"] == "unavailable"
    assert "timed out" in waqi_info["details"].lower()
    assert DUMMY_WAQI_TOKEN not in resp.text
    assert "api.waqi.info" not in waqi_info["details"]

    assert aq is None
    assert stations == []
    assert DUMMY_WAQI_TOKEN not in caplog.text
    for rec in caplog.records:
        assert DUMMY_WAQI_TOKEN not in rec.getMessage()
        assert DUMMY_WAQI_TOKEN not in (rec.exc_text or "")


def test_centralized_log_redaction_covers_httpx_urls_and_tracebacks(monkeypatch, caplog):
    """Process-wide log redaction scrubs httpx URL objects, headers, and logger.exception tracebacks."""
    install_log_redaction()
    monkeypatch.setattr(settings, "WAQI_API_KEY", DUMMY_WAQI_TOKEN)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", DUMMY_GEMINI_KEY)
    monkeypatch.setattr(settings, "OPENAQ_API_KEY", DUMMY_OPENAQ_KEY)

    httpx_logger = logging.getLogger("httpx")
    app_child_logger = logging.getLogger("app.services.test_child")

    with caplog.at_level(logging.DEBUG):
        httpx_logger.info(
            'HTTP Request: %s %s "%s %d %s"',
            "GET",
            httpx.URL(f"https://api.waqi.info/feed/here/?token={DUMMY_WAQI_TOKEN}"),
            "HTTP/1.1",
            200,
            "OK",
        )
        try:
            raise RuntimeError(
                f"Failed header x-goog-api-key: {DUMMY_GEMINI_KEY} X-API-Key: {DUMMY_OPENAQ_KEY}"
            )
        except RuntimeError as exc:
            app_child_logger.exception("Unhandled provider failure: %s", format_safe_exception(exc))

    assert DUMMY_WAQI_TOKEN not in caplog.text
    assert DUMMY_GEMINI_KEY not in caplog.text
    assert DUMMY_OPENAQ_KEY not in caplog.text
    assert "https://api.waqi.info/feed/here/?token=[REDACTED]" in caplog.text
    assert "x-goog-api-key: [REDACTED]" in redact_sensitive_text(
        f"x-goog-api-key: {DUMMY_GEMINI_KEY}"
    )
