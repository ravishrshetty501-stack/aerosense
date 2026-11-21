from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.alert import AlertRule, AlertEvent
from app.models.user import User

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
    def detect_spike(history_records: List[Dict[str, Any]], current_val: float, pollutant: str = "pm25") -> Optional[Dict[str, Any]]:
        """
        Detects if current value represents an abnormal surge compared to recent 6-12 hour average.
        """
        if not history_records or len(history_records) < 6:
            return None
            
        recent = [r.get(pollutant) for r in history_records[-6:] if r.get(pollutant) is not None]
        if not recent:
            return None
            
        avg_recent = sum(recent) / len(recent)
        if avg_recent > 0 and (current_val / avg_recent) >= 1.6 and (current_val - avg_recent) >= 15.0:
            return {
                "pollutant": pollutant.upper(),
                "current_val": current_val,
                "recent_average": round(avg_recent, 1),
                "spike_ratio": round(current_val / avg_recent, 2),
                "message": f"Pollution Spike Detected: {pollutant.upper()} increased by {round((current_val/avg_recent - 1)*100)}% over recent 6-hour baseline."
            }
        return None

    async def evaluate_rules_for_location(
        self,
        db: AsyncSession,
        location_name: str,
        current_aqi: float,
        measurements: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query = select(AlertRule).where(
            AlertRule.location_name.ilike(f"%{location_name}%"),
            AlertRule.is_active == True
        )
        if user_id:
            query = query.where(AlertRule.user_id == user_id)
            
        result = await db.execute(query)
        rules = result.scalars().all()
        triggered = []

        for rule in rules:
            target_val = current_aqi
            if rule.pollutant != "aqi" and rule.pollutant in measurements:
                target_val = measurements[rule.pollutant].get("value", current_aqi)
                
            if target_val >= rule.threshold_aqi:
                severity = self.classify_severity(target_val, rule.threshold_aqi)
                msg = f"Air Quality Alert for {rule.location_name}: {rule.pollutant.upper()} is {target_val} (Threshold: {rule.threshold_aqi})"
                
                event = AlertEvent(
                    rule_id=rule.id,
                    location_name=rule.location_name,
                    trigger_value=float(target_val),
                    threshold_value=float(rule.threshold_aqi),
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
