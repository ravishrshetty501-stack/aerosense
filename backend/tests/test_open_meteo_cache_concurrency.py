import asyncio
import inspect
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1 import system as system_api
from app.services.providers.open_meteo import OpenMeteoAirQualityProvider


def _make_open_meteo_payload(pm25_val: float = 42.0, time_str: str = "2026-11-27T12:00") -> Dict[str, Any]:
    return {
        "elevation": 216.0,
        "timezone": "UTC",
        "current": {
            "time": time_str,
            "pm2_5": pm25_val,
            "pm10": 65.0,
            "nitrogen_dioxide": 20.0,
            "ozone": 30.0,
            "us_aqi": 117,
            "european_aqi": 60,
        },
        "current_units": {
            "pm2_5": "μg/m³",
            "pm10": "μg/m³",
            "nitrogen_dioxide": "μg/m³",
            "ozone": "μg/m³",
        },
        "hourly": {
            "time": ["2026-11-27T11:00", "2026-11-27T12:00", "2026-11-27T13:00"],
            "pm2_5": [40.0, pm25_val, 45.0],
            "pm10": [60.0, 65.0, 70.0],
            "nitrogen_dioxide": [18.0, 20.0, 22.0],
            "ozone": [28.0, 30.0, 32.0],
            "us_aqi": [112, 117, 124],
        },
    }


def _mock_response(status_code: int = 200, payload: Optional[Dict[str, Any]] = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload if payload is not None else _make_open_meteo_payload()
    return resp


@pytest.mark.asyncio
async def test_same_coordinate_concurrent_requests_coalesce_to_single_fetch():
    """Concurrent callers for identical normalized coordinates trigger only one upstream HTTP call."""
    provider = OpenMeteoAirQualityProvider()
    call_count = 0
    fetch_entered = asyncio.Event()
    release_fetch = asyncio.Event()

    async def fake_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        fetch_entered.set()
        await release_fetch.wait()
        return _mock_response(200, _make_open_meteo_payload(pm25_val=55.5))

    with patch("httpx.AsyncClient.get", side_effect=fake_get):
        # Slightly different coordinates that normalize to the same 0.1-deg grid cell (28.6_77.2)
        t1 = asyncio.create_task(provider.get_current_air_quality(28.6139, 77.2090, "Delhi A"))
        await fetch_entered.wait()
        t2 = asyncio.create_task(provider.get_current_air_quality(28.63, 77.22, "Delhi B"))
        t3 = asyncio.create_task(provider.get_current_air_quality(28.60, 77.21, "Delhi C"))
        await asyncio.sleep(0)  # Let t2 & t3 enqueue on the coordinate lock
        release_fetch.set()
        results = await asyncio.gather(t1, t2, t3)

    assert call_count == 1
    assert all(r is not None for r in results)
    assert all(r["measurements"]["pm25"].value == 55.5 for r in results)
    assert provider.cache_size() == 1
    assert len(provider._coord_locks) == 0


@pytest.mark.asyncio
async def test_different_coordinates_proceed_concurrently_without_blocking():
    """A stalled or backing-off coordinate request must not serialize unrelated coordinates."""
    provider = OpenMeteoAirQualityProvider()
    coord_a_started = asyncio.Event()
    coord_a_release = asyncio.Event()
    completion_order = []

    async def fake_get(url, params=None, **kwargs):
        lat = params["latitude"]
        if round(lat, 1) == 28.6:
            coord_a_started.set()
            await coord_a_release.wait()
            completion_order.append("coord_a")
            return _mock_response(200, _make_open_meteo_payload(pm25_val=80.0))
        completion_order.append("coord_b")
        return _mock_response(200, _make_open_meteo_payload(pm25_val=15.0))

    with patch("httpx.AsyncClient.get", side_effect=fake_get):
        task_a = asyncio.create_task(provider.get_current_air_quality(28.6, 77.2, "Delhi"))
        await coord_a_started.wait()

        # Start coord_b while coord_a holds its lock; coord_b must complete first
        task_b = asyncio.create_task(provider.get_current_air_quality(35.7, 139.7, "Tokyo"))
        res_b = await asyncio.wait_for(task_b, timeout=1.0)
        assert res_b is not None and res_b["measurements"]["pm25"].value == 15.0

        coord_a_release.set()
        res_a = await task_a
        assert res_a is not None and res_a["measurements"]["pm25"].value == 80.0

    assert completion_order == ["coord_b", "coord_a"]
    assert len(provider._coord_locks) == 0


@pytest.mark.asyncio
async def test_cache_hit_miss_expiry_and_boundary_semantics():
    """Verify cache hits, misses, exact UTC expiry boundary, and non-serving of expired entries."""
    base_time = datetime(2026, 11, 27, 12, 0, 0, tzinfo=timezone.utc)
    clock = [base_time]
    provider = OpenMeteoAirQualityProvider(cache_ttl=60.0, max_cache_size=10)

    fetch_counter = 0

    async def fake_get(*args, **kwargs):
        nonlocal fetch_counter
        fetch_counter += 1
        return _mock_response(200, _make_open_meteo_payload(pm25_val=10.0 * fetch_counter))

    with (
        patch.object(provider, "_utc_now", side_effect=lambda: clock[0]),
        patch("httpx.AsyncClient.get", side_effect=fake_get),
    ):
        # Miss -> fetch #1
        res1 = await provider.get_current_air_quality(48.9, 2.4, "Paris")
        assert res1["measurements"]["pm25"].value == 10.0
        assert fetch_counter == 1
        assert provider.has_cached_data() is True

        # Just before expiry boundary (59.999999s) -> cache hit
        clock[0] = base_time + timedelta(seconds=60) - timedelta(microseconds=1)
        res_before_boundary = await provider.get_current_air_quality(48.9, 2.4, "Paris")
        assert res_before_boundary["measurements"]["pm25"].value == 10.0
        assert fetch_counter == 1
        assert provider.has_cached_data() is True

        # Exact expiry boundary (60.0s) -> expired, must NOT be returned; triggers fetch #2
        clock[0] = base_time + timedelta(seconds=60)
        assert provider.has_cached_data() is False
        res_at_boundary = await provider.get_current_air_quality(48.9, 2.4, "Paris")
        assert res_at_boundary["measurements"]["pm25"].value == 20.0
        assert fetch_counter == 2

        # Advance well past expiry; simulate upstream 500 error -> expired entry MUST NOT be served stale
        clock[0] = base_time + timedelta(seconds=200)
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_mock_response(500))):
            res_expired_err = await provider.get_current_air_quality(48.9, 2.4, "Paris")
            assert res_expired_err is None
            assert provider.cache_size() == 0
            assert provider.has_cached_data() is False


@pytest.mark.asyncio
async def test_lru_eviction_and_atomic_cache_entry_consistency():
    """Verify bounded LRU eviction removes least-recently-used key when capacity is exceeded."""
    clock = [datetime(2026, 11, 27, 12, 0, 0, tzinfo=timezone.utc)]
    provider = OpenMeteoAirQualityProvider(cache_ttl=1800.0, max_cache_size=2)

    async def fake_get(url, params=None, **kwargs):
        return _mock_response(200, _make_open_meteo_payload(pm25_val=float(params["latitude"])))

    with (
        patch.object(provider, "_utc_now", side_effect=lambda: clock[0]),
        patch("httpx.AsyncClient.get", side_effect=fake_get),
    ):
        await provider.get_current_air_quality(10.0, 10.0, "City A")
        await provider.get_current_air_quality(20.0, 20.0, "City B")
        assert list(provider._cache.keys()) == ["10.0_10.0", "20.0_20.0"]

        # Access City A so City B becomes the least-recently-used entry
        await provider.get_current_air_quality(10.0, 10.0, "City A")
        assert list(provider._cache.keys()) == ["20.0_20.0", "10.0_10.0"]

        # Insert City C -> City B must be evicted; cache stays bounded at 2
        await provider.get_current_air_quality(30.0, 30.0, "City C")
        assert provider.cache_size() == 2
        assert "20.0_20.0" not in provider._cache
        assert "10.0_10.0" in provider._cache
        assert "30.0_30.0" in provider._cache

        # Atomic entry structure guarantees every cached item carries timezone-aware UTC expiry
        for entry in provider._cache.values():
            assert entry.expires_at.tzinfo == timezone.utc
            assert entry.expires_at == clock[0] + timedelta(seconds=1800.0)


@pytest.mark.asyncio
async def test_lock_cleanup_and_429_retry_backoff_recovery():
    """Verify HTTP 429 retry backoff, failure cleanup, and subsequent request recovery."""
    provider = OpenMeteoAirQualityProvider()

    # Case 1: 429 followed by 200 succeeds after 1.5s sleep backoff and cleans up lock
    sleep_mock = AsyncMock()
    get_mock = AsyncMock(side_effect=[_mock_response(429), _mock_response(200, _make_open_meteo_payload(33.0))])
    with (
        patch("app.services.providers.open_meteo.asyncio.sleep", sleep_mock),
        patch("httpx.AsyncClient.get", get_mock),
    ):
        res = await provider.get_current_air_quality(51.5, -0.1, "London")

    assert res is not None
    assert res["measurements"]["pm25"].value == 33.0
    sleep_mock.assert_awaited_once_with(1.5)
    assert get_mock.await_count == 2
    assert len(provider._coord_locks) == 0

    # Case 2: Exception leaves lock registry empty and allows subsequent request to succeed
    provider2 = OpenMeteoAirQualityProvider()
    with patch("httpx.AsyncClient.get", side_effect=RuntimeError("network drop")):
        failed = await provider2.get_current_air_quality(40.7, -74.0, "NYC")
    assert failed is None
    assert len(provider2._coord_locks) == 0
    assert provider2.has_cached_data() is False

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_mock_response(200, _make_open_meteo_payload(19.0)))):
        recovered = await provider2.get_current_air_quality(40.7, -74.0, "NYC")
    assert recovered is not None
    assert recovered["measurements"]["pm25"].value == 19.0
    assert len(provider2._coord_locks) == 0


@pytest.mark.asyncio
async def test_public_cache_interface_and_system_endpoint_decoupling():
    """system.py must use has_cached_data() rather than accessing private _cache directly."""
    source = inspect.getsource(system_api)
    assert "._cache" not in source
    assert "has_cached_data()" in source

    # Exercise get_network_status with fresh cache reset and mocked provider status
    system_api._network_status_cache["data"] = None
    system_api._network_status_cache["expires_at"] = None

    with (
        patch("app.services.providers.open_meteo.open_meteo_provider.has_cached_data", return_value=True) as mock_has_cache,
        patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_mock_response(200, {"status": "ok"}))),
    ):
        status_payload = await system_api.get_network_status()

    mock_has_cache.assert_called_once()
    assert status_payload["providers"]["open_meteo"]["status"] == "connected"
    assert "cached" in status_payload["providers"]["open_meteo"]["details"]
    assert isinstance(status_payload["timestamp"], str)

    # Clear test cache state cleanly
    system_api._network_status_cache["data"] = None
    system_api._network_status_cache["expires_at"] = None


def test_cache_ttl_and_size_validation():
    """Constructor preserves 1800s default and rejects invalid TTL or cache size inputs."""
    default_provider = OpenMeteoAirQualityProvider()
    assert default_provider._cache_ttl == 1800.0
    assert default_provider._max_cache_size == 256

    int_provider = OpenMeteoAirQualityProvider(cache_ttl=60, max_cache_size=4)
    assert isinstance(int_provider._cache_ttl, float)
    assert int_provider._cache_ttl == 60.0

    small_provider = OpenMeteoAirQualityProvider(cache_ttl=0.25)
    assert small_provider._cache_ttl == 0.25

    for invalid_ttl_value in (0, 0.0, -1, -0.001, float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            OpenMeteoAirQualityProvider(cache_ttl=invalid_ttl_value)

    for invalid_ttl_type in (True, False, None, "1800", ["1800"]):
        with pytest.raises(TypeError):
            OpenMeteoAirQualityProvider(cache_ttl=invalid_ttl_type)  # type: ignore[arg-type]

    for invalid_size_type in (True, False, 1.5, "10", None):
        with pytest.raises(TypeError):
            OpenMeteoAirQualityProvider(max_cache_size=invalid_size_type)  # type: ignore[arg-type]

    for invalid_size_val in (0, -5):
        with pytest.raises(ValueError):
            OpenMeteoAirQualityProvider(max_cache_size=invalid_size_val)


@pytest.mark.asyncio
async def test_same_coordinate_concurrent_non_200_sequential_requests_and_recovery():
    """
    When upstream returns non-200, failed calls do not populate the cache.
    Queued same-coordinate callers remain serialized by the lock, each seeing a cache miss
    and issuing sequential upstream requests, then later independent requests recover cleanly.
    """
    provider = OpenMeteoAirQualityProvider()
    call_count = 0
    active_fetches = 0
    max_active_fetches = 0
    first_entered = asyncio.Event()
    release_first = asyncio.Event()

    async def fake_get(*args, **kwargs):
        nonlocal call_count, active_fetches, max_active_fetches
        call_count += 1
        active_fetches += 1
        max_active_fetches = max(max_active_fetches, active_fetches)
        try:
            if call_count == 1:
                first_entered.set()
                await release_first.wait()
            return _mock_response(503)
        finally:
            active_fetches -= 1

    with patch("httpx.AsyncClient.get", side_effect=fake_get):
        t1 = asyncio.create_task(provider.get_current_air_quality(28.6139, 77.2090, "Delhi 1"))
        await first_entered.wait()
        t2 = asyncio.create_task(provider.get_current_air_quality(28.62, 77.21, "Delhi 2"))
        t3 = asyncio.create_task(provider.get_current_air_quality(28.60, 77.22, "Delhi 3"))
        await asyncio.sleep(0)
        assert len(provider._coord_locks) == 1
        release_first.set()
        results = await asyncio.gather(t1, t2, t3)

    assert results == [None, None, None]
    assert max_active_fetches == 1
    assert call_count == 3
    assert len(provider._coord_locks) == 0
    assert provider.has_cached_data() is False

    # If a later queued caller succeeds, subsequent queued callers coalesce on the populated cache
    mixed_calls = 0
    mixed_entered = asyncio.Event()
    release_mixed = asyncio.Event()

    async def fake_mixed_get(*args, **kwargs):
        nonlocal mixed_calls
        mixed_calls += 1
        if mixed_calls == 1:
            mixed_entered.set()
            await release_mixed.wait()
            return _mock_response(500)
        return _mock_response(200, _make_open_meteo_payload(pm25_val=41.0))

    with patch("httpx.AsyncClient.get", side_effect=fake_mixed_get):
        m1 = asyncio.create_task(provider.get_current_air_quality(28.61, 77.21, "Mix 1"))
        await mixed_entered.wait()
        m2 = asyncio.create_task(provider.get_current_air_quality(28.62, 77.22, "Mix 2"))
        m3 = asyncio.create_task(provider.get_current_air_quality(28.63, 77.23, "Mix 3"))
        await asyncio.sleep(0)
        release_mixed.set()
        mixed_results = await asyncio.gather(m1, m2, m3)

    assert mixed_results[0] is None
    assert mixed_results[1] is not None and mixed_results[1]["measurements"]["pm25"].value == 41.0
    assert mixed_results[2] is not None and mixed_results[2]["measurements"]["pm25"].value == 41.0
    assert mixed_calls == 2
    assert len(provider._coord_locks) == 0


@pytest.mark.asyncio
async def test_same_coordinate_concurrent_exceptions_and_429_exhaustion():
    """Concurrent exceptions and 429 retry exhaustion serialize per coordinate, clean up locks, and allow recovery."""
    # Case 1: Concurrent upstream exceptions
    provider_exc = OpenMeteoAirQualityProvider()
    exc_calls = 0
    exc_active = 0
    max_exc_active = 0
    first_exc_entered = asyncio.Event()
    release_first_exc = asyncio.Event()

    async def fake_exc_get(*args, **kwargs):
        nonlocal exc_calls, exc_active, max_exc_active
        exc_calls += 1
        exc_active += 1
        max_exc_active = max(max_exc_active, exc_active)
        try:
            if exc_calls == 1:
                first_exc_entered.set()
                await release_first_exc.wait()
            raise RuntimeError("upstream socket reset")
        finally:
            exc_active -= 1

    with patch("httpx.AsyncClient.get", side_effect=fake_exc_get):
        e1 = asyncio.create_task(provider_exc.get_current_air_quality(19.1, 72.9, "Mumbai 1"))
        await first_exc_entered.wait()
        e2 = asyncio.create_task(provider_exc.get_current_air_quality(19.12, 72.88, "Mumbai 2"))
        await asyncio.sleep(0)
        release_first_exc.set()
        exc_results = await asyncio.gather(e1, e2)

    assert exc_results == [None, None]
    assert max_exc_active == 1
    assert exc_calls == 2
    assert len(provider_exc._coord_locks) == 0
    assert provider_exc.has_cached_data() is False

    # Case 2: Concurrent 429 retries eventually fail (429 -> backoff 1.5s -> 429 for each caller)
    provider_429 = OpenMeteoAirQualityProvider()
    rl_calls = 0
    first_rl_entered = asyncio.Event()
    release_first_rl_sleep = asyncio.Event()
    sleep_delays = []

    orig_sleep = asyncio.sleep

    async def fake_sleep(delay: float):
        sleep_delays.append(delay)
        if len(sleep_delays) == 1:
            first_rl_entered.set()
            await release_first_rl_sleep.wait()

    async def fake_429_get(*args, **kwargs):
        nonlocal rl_calls
        rl_calls += 1
        return _mock_response(429)

    with (
        patch("app.services.providers.open_meteo.asyncio.sleep", side_effect=fake_sleep),
        patch("httpx.AsyncClient.get", side_effect=fake_429_get),
    ):
        r1 = asyncio.create_task(provider_429.get_current_air_quality(12.9, 77.6, "Bengaluru 1"))
        await first_rl_entered.wait()
        r2 = asyncio.create_task(provider_429.get_current_air_quality(12.91, 77.61, "Bengaluru 2"))
        await orig_sleep(0)
        assert len(provider_429._coord_locks) == 1
        release_first_rl_sleep.set()
        rl_results = await asyncio.gather(r1, r2)

    assert rl_results == [None, None]
    assert rl_calls == 4  # 2 attempts per sequential caller
    assert sleep_delays == [1.5, 1.5]
    assert len(provider_429._coord_locks) == 0
    assert provider_429.has_cached_data() is False

    # Subsequent independent request succeeds cleanly
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_mock_response(200, _make_open_meteo_payload(27.5)))):
        recovered = await provider_429.get_current_air_quality(12.9, 77.6, "Bengaluru")
    assert recovered is not None and recovered["measurements"]["pm25"].value == 27.5
    assert len(provider_429._coord_locks) == 0


@pytest.mark.asyncio
async def test_cancellation_while_waiting_or_fetching_releases_lock_without_leaks():
    """Task cancellation waiting for a lock or mid-fetch must never leak locks or stall waiters."""
    # Subcase A: Cancelled while waiting on coordinate lock
    provider_a = OpenMeteoAirQualityProvider()
    calls_a = 0
    entered_a = asyncio.Event()
    release_a = asyncio.Event()

    async def fake_get_a(*args, **kwargs):
        nonlocal calls_a
        calls_a += 1
        entered_a.set()
        await release_a.wait()
        return _mock_response(200, _make_open_meteo_payload(pm25_val=64.0))

    with patch("httpx.AsyncClient.get", side_effect=fake_get_a):
        holder = asyncio.create_task(provider_a.get_current_air_quality(35.7, 139.7, "Tokyo Holder"))
        await entered_a.wait()
        waiter = asyncio.create_task(provider_a.get_current_air_quality(35.71, 139.72, "Tokyo Waiter"))
        await asyncio.sleep(0)
        assert provider_a._coord_locks["35.7_139.7"].ref_count == 2

        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter

        assert provider_a._coord_locks["35.7_139.7"].ref_count == 1
        release_a.set()
        holder_res = await holder

    assert holder_res is not None and holder_res["measurements"]["pm25"].value == 64.0
    assert calls_a == 1
    assert len(provider_a._coord_locks) == 0
    assert provider_a.cache_size() == 1

    # Subcase B: Cancelled in-flight during upstream fetch while another caller waits
    provider_b = OpenMeteoAirQualityProvider()
    calls_b = 0
    first_in_flight = asyncio.Event()
    hang_forever = asyncio.Event()

    async def fake_get_b(*args, **kwargs):
        nonlocal calls_b
        calls_b += 1
        if calls_b == 1:
            first_in_flight.set()
            await hang_forever.wait()
        return _mock_response(200, _make_open_meteo_payload(pm25_val=52.0))

    with patch("httpx.AsyncClient.get", side_effect=fake_get_b):
        in_flight = asyncio.create_task(provider_b.get_current_air_quality(48.9, 2.4, "Paris 1"))
        await first_in_flight.wait()
        queued = asyncio.create_task(provider_b.get_current_air_quality(48.91, 2.41, "Paris 2"))
        await asyncio.sleep(0)

        in_flight.cancel()
        with pytest.raises(asyncio.CancelledError):
            await in_flight

        queued_res = await asyncio.wait_for(queued, timeout=1.0)

    assert queued_res is not None and queued_res["measurements"]["pm25"].value == 52.0
    assert calls_b == 2
    assert len(provider_b._coord_locks) == 0
    assert provider_b.cache_size() == 1

    # Subcase C: Solo caller cancelled during 429 retry sleep cleans up lock completely
    provider_c = OpenMeteoAirQualityProvider()
    sleep_entered = asyncio.Event()
    never_wake = asyncio.Event()

    async def fake_sleep_hang(_delay: float):
        sleep_entered.set()
        await never_wake.wait()

    with (
        patch("app.services.providers.open_meteo.asyncio.sleep", side_effect=fake_sleep_hang),
        patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_mock_response(429))),
    ):
        solo = asyncio.create_task(provider_c.get_current_air_quality(52.5, 13.4, "Berlin"))
        await sleep_entered.wait()
        solo.cancel()
        with pytest.raises(asyncio.CancelledError):
            await solo

    assert len(provider_c._coord_locks) == 0
    assert provider_c.has_cached_data() is False

