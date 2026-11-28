import math
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import utc_now
from app.models.alert import AlertRule, AlertEvent
from app.models.user import User


def _escape_like_pattern(value: str) -> str:
    """Escapes SQL LIKE wildcards so literal location names cannot trigger unintended pattern matches."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

class AlertService:
    """
    Intelligent environmental alert system.
    Detects pollution spikes, checks against user-defined threshold rules,
    and logs alert events without duplication.
    """

    @staticmethod
    def classify_severity(aqi_or_val: float, threshold: float) -> str:
        ratio = aqi_or_val / max(threshold, 1.0)
        if ratio >= 2.0 or aqi_or_val >= 250:
            return "critical"
        elif ratio >= 1.3 or aqi_or_val >= 150:
            return "warning"
        return "advisory"

    @staticmethod
    def _extract_finite_number(raw: Any) -> Optional[float]:
        """Returns a finite float for numeric inputs, rejecting None, booleans, NaN, infinities, and overflows."""
        if raw is None or isinstance(raw, bool) or not isinstance(raw, (int, float)):
            return None
        try:
            val = float(raw)
            return val if math.isfinite(val) else None
        except (OverflowError, ValueError):
            return None

    @classmethod
    def _extract_measurement_value(cls, entry: Any) -> Optional[float]:
        """Safely extracts a finite numeric value from dict or NormalizedMeasurement-like objects."""
        if entry is None:
            return None
        if isinstance(entry, dict):
            raw = entry.get("value")
        elif hasattr(entry, "value"):
            raw = getattr(entry, "value")
        else:
            raw = entry
        return cls._extract_finite_number(raw)

    @staticmethod
    def detect_spike(history_records: List[Dict[str, Any]], current_val: Optional[float], pollutant: str = "pm25") -> Optional[Dict[str, Any]]:
        """
        Detects if current value represents an abnormal surge compared to recent 6-12 hour average.
        """
        valid_current = AlertService._extract_finite_number(current_val)
        if valid_current is None or not history_records or len(history_records) < 6:
            return None

        recent = [
            val
            for val in (AlertService._extract_finite_number(r.get(pollutant)) for r in history_records[-6:])
            if val is not None
        ]
        if not recent:
            return None

        avg_recent = sum(recent) / len(recent)
        if avg_recent > 0 and (valid_current / avg_recent) >= 1.6 and (valid_current - avg_recent) >= 15.0:
            return {
                "pollutant": pollutant.upper(),
                "current_val": valid_current,
                "recent_average": round(avg_recent, 1),
                "spike_ratio": round(valid_current / avg_recent, 2),
                "message": f"Pollution Spike Detected: {pollutant.upper()} increased by {round((valid_current/avg_recent - 1)*100)}% over recent 6-hour baseline."
            }
        return None

    async def evaluate_rules_for_location(
        self,
        db: AsyncSession,
        location_name: str,
        current_aqi: Optional[float],
        measurements: Optional[Dict[str, Any]],
        user_id: Optional[str] = None,
        cooldown_minutes: int = 30,
    ) -> List[Dict[str, Any]]:
        clean_location = (location_name or "").strip()
        if not clean_location:
            return []

        escaped_location = _escape_like_pattern(clean_location)
        query = select(AlertRule).where(
            AlertRule.location_name.ilike(f"%{escaped_location}%", escape="\\"),
            AlertRule.is_active == True
        )
        if user_id:
            query = query.where(AlertRule.user_id == user_id)

        result = await db.execute(query)
        rules = result.scalars().all()
        measurements_map = measurements if isinstance(measurements, dict) else {}
        normalized_measurements = {
            str(k).lower(): v for k, v in measurements_map.items()
        }
        triggered = []
        cooldown_cutoff = (
            utc_now() - timedelta(minutes=cooldown_minutes)
            if cooldown_minutes and cooldown_minutes > 0
            else None
        )

        for rule in rules:
            pollutant_key = (rule.pollutant or "aqi").lower()
            if pollutant_key == "aqi":
                target_val = self._extract_finite_number(current_aqi)
            else:
                entry = normalized_measurements.get(pollutant_key)
                target_val = self._extract_measurement_value(entry)

            threshold_val = self._extract_finite_number(rule.threshold_aqi)
            if target_val is None or threshold_val is None:
                continue

            if target_val >= threshold_val:
                if cooldown_cutoff is not None:
                    recent_q = await db.execute(
                        select(AlertEvent.id).where(
                            AlertEvent.rule_id == rule.id,
                            AlertEvent.triggered_at >= cooldown_cutoff,
                        ).limit(1)
                    )
                    if recent_q.scalar_one_or_none() is not None:
                        continue

                severity = self.classify_severity(target_val, threshold_val)
                msg = f"Air Quality Alert for {rule.location_name}: {pollutant_key.upper()} is {target_val} (Threshold: {rule.threshold_aqi})"

                event = AlertEvent(
                    rule_id=rule.id,
                    location_name=rule.location_name,
                    trigger_value=float(target_val),
                    threshold_value=float(threshold_val),
                    pollutant=rule.pollutant,
                    severity=severity,
                    message=msg
                )
                db.add(event)
                triggered.append({
                    "rule_id": rule.id,
                    "location": rule.location_name,
                    "severity": severity,
                    "message": msg,
                    "trigger_value": target_val,
                    "threshold": rule.threshold_aqi
                })

        if triggered:
            await db.commit()

        return triggered

alert_service = AlertService()
