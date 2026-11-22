import pytest
import uuid
from app.services.alert_service import AlertService, alert_service
from app.core.database import engine, Base, AsyncSessionLocal
from app.models.user import User
from app.models.alert import AlertRule, AlertEvent
from sqlalchemy import select

@pytest.fixture(autouse=True)
async def init_test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

def test_classify_severity_thresholds():
    """Verifies severity classification for advisory, warning, and critical thresholds."""
    # Under 1.3 ratio and under 150 -> advisory
    assert AlertService.classify_severity(50, 100) == "advisory"
    assert AlertService.classify_severity(120, 100) == "advisory"

    # Ratio >= 1.3 -> warning
    assert AlertService.classify_severity(135, 100) == "warning"

    # Absolute value >= 150 even if ratio is lower -> warning
    assert AlertService.classify_severity(160, 200) == "warning"

    # Ratio >= 2.0 -> critical
    assert AlertService.classify_severity(210, 100) == "critical"

    # Absolute value >= 250 -> critical
    assert AlertService.classify_severity(260, 300) == "critical"

    # Edge cases: 0 or negative threshold protected by max(threshold, 1.0)
    assert AlertService.classify_severity(10, 0) == "critical"
    assert AlertService.classify_severity(50, -10) == "critical"

def test_detect_spike_conditions():
    """Verifies surge / spike detection across varying history windows and thresholds."""
    # Insufficient records (< 6)
    assert AlertService.detect_spike([], 50.0, "pm25") is None
    short_history = [{"pm25": 20.0} for _ in range(5)]
    assert AlertService.detect_spike(short_history, 50.0, "pm25") is None

    # Missing pollutant in records
    missing_pol_history = [{"pm10": 30.0} for _ in range(10)]
    assert AlertService.detect_spike(missing_pol_history, 50.0, "pm25") is None

    # Normal baseline fluctuation (baseline 25, current 30: ratio 1.2, diff 5)
    normal_history = [{"pm25": 25.0} for _ in range(8)]
    assert AlertService.detect_spike(normal_history, 30.0, "pm25") is None

    # High ratio (1.8x) but small absolute difference (< 15 ug/m3)
    low_diff_history = [{"pm25": 10.0} for _ in range(8)]
    assert AlertService.detect_spike(low_diff_history, 18.0, "pm25") is None

    # Valid spike: baseline 20, current 50 (ratio 2.5x >= 1.6 and diff 30 >= 15)
    spike_history = [{"pm25": 20.0} for _ in range(8)]
    spike = AlertService.detect_spike(spike_history, 50.0, "pm25")
    assert spike is not None
    assert spike["pollutant"] == "PM25"
    assert spike["current_val"] == 50.0
    assert spike["recent_average"] == 20.0
    assert spike["spike_ratio"] == 2.5
    assert "Pollution Spike Detected: PM25" in spike["message"]

    # Valid spike for NO2
    no2_history = [{"no2": 30.0} for _ in range(6)]
    no2_spike = AlertService.detect_spike(no2_history, 75.0, "no2")
    assert no2_spike is not None
    assert no2_spike["pollutant"] == "NO2"
    assert no2_spike["current_val"] == 75.0

@pytest.mark.asyncio
async def test_evaluate_rules_for_location():
    """Verifies evaluation of user alert rules against current environmental readings."""
    test_uid = f"user_{uuid.uuid4().hex[:8]}"

    async with AsyncSessionLocal() as session:
        # Create test user
        user = User(
            id=test_uid,
            email=f"{test_uid}@test.ai",
            hashed_password="fakehashedpassword",
            full_name="Alert Tester"
        )
        session.add(user)

        # Create active rule for Berlin AQI threshold 100
        rule1 = AlertRule(
            id=f"rule_{uuid.uuid4().hex[:8]}",
            user_id=test_uid,
            location_name="Berlin",
            latitude=52.52,
            longitude=13.40,
            threshold_aqi=100.0,
            pollutant="aqi",
            severity="warning",
            is_active=True
        )
        # Create inactive rule for Berlin (should not trigger)
        rule_inactive = AlertRule(
            id=f"rule_{uuid.uuid4().hex[:8]}",
            user_id=test_uid,
            location_name="Berlin",
            latitude=52.52,
            longitude=13.40,
            threshold_aqi=50.0,
            pollutant="aqi",
            severity="advisory",
            is_active=False
        )
        # Create rule for Tokyo (should not trigger on Berlin evaluation)
        rule_tokyo = AlertRule(
            id=f"rule_{uuid.uuid4().hex[:8]}",
            user_id=test_uid,
            location_name="Tokyo",
            latitude=35.68,
            longitude=139.69,
            threshold_aqi=150.0,
            pollutant="aqi",
            severity="warning",
            is_active=True
        )
        session.add_all([rule1, rule_inactive, rule_tokyo])
        await session.commit()

        # Evaluate Berlin with AQI 135 (exceeds threshold 100)
        triggered = await alert_service.evaluate_rules_for_location(
            db=session,
            location_name="Berlin",
            current_aqi=135.0,
            measurements={},
            user_id=test_uid
        )
        assert len(triggered) == 1
        assert triggered[0]["rule_id"] == rule1.id
        assert triggered[0]["severity"] == "warning"
        assert triggered[0]["trigger_value"] == 135.0

        # Verify AlertEvent was saved in database
        event_res = await session.execute(
            select(AlertEvent).where(AlertEvent.rule_id == rule1.id)
        )
        events = event_res.scalars().all()
        assert len(events) >= 1
        assert events[0].location_name == "Berlin"
        assert events[0].trigger_value == 135.0

        # Evaluate Berlin with AQI 80 (below threshold 100) -> 0 triggered
        sub_triggered = await alert_service.evaluate_rules_for_location(
            db=session,
            location_name="Berlin",
            current_aqi=80.0,
            measurements={},
            user_id=test_uid
        )
        assert len(sub_triggered) == 0
