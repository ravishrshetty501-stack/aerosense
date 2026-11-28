import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import Any, Dict, List
from app.core.database import get_db
from app.core.redaction import format_safe_exception
from app.models.alert import AlertRule, AlertEvent
from app.models.user import User
from app.schemas.alert import AlertRuleCreate, AlertRuleOut, AlertEventOut
from app.api.deps import get_current_user
from app.services.alert_service import alert_service
from app.services.providers.manager import data_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["Intelligent Alerts"])


async def evaluate_active_rules_for_user(
    db: AsyncSession,
    user_id: str,
    max_locations: int = 5,
) -> List[Dict[str, Any]]:
    """Evaluates active user alert rules against live environmental telemetry with cooldown deduplication."""
    rules_res = await db.execute(
        select(AlertRule).where(AlertRule.user_id == user_id, AlertRule.is_active == True)
    )
    active_rules = rules_res.scalars().all()
    if not active_rules:
        return []

    seen_locations: Dict[str, AlertRule] = {}
    for rule in active_rules:
        key = (rule.location_name or "").strip().lower()
        if key and key not in seen_locations:
            seen_locations[key] = rule
        if len(seen_locations) >= max_locations:
            break

    triggered_all: List[Dict[str, Any]] = []
    for rule in seen_locations.values():
        try:
            aq = await data_manager.get_unified_air_quality(
                rule.latitude, rule.longitude, rule.location_name, "US_EPA"
            )
            current_aqi = (aq.aqi_standard_results.get("US_EPA") or {}).get("aqi")
            triggered = await alert_service.evaluate_rules_for_location(
                db=db,
                location_name=rule.location_name,
                current_aqi=current_aqi,
                measurements=aq.measurements,
                user_id=user_id,
            )
            triggered_all.extend(triggered)
        except Exception as exc:
            logger.warning(
                "[Alerts] Failed evaluating rule location '%s': %s",
                rule.location_name,
                format_safe_exception(exc),
            )
    return triggered_all


@router.get("/rules", response_model=List[AlertRuleOut])
async def list_alert_rules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(AlertRule).where(AlertRule.user_id == current_user.id))
    return result.scalars().all()

@router.post("/rules", response_model=AlertRuleOut, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    rule_in: AlertRuleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    rule = AlertRule(
        user_id=current_user.id,
        location_name=rule_in.location_name,
        latitude=rule_in.latitude,
        longitude=rule_in.longitude,
        threshold_aqi=rule_in.threshold_aqi,
        pollutant=rule_in.pollutant,
        severity=rule_in.severity
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    try:
        aq = await data_manager.get_unified_air_quality(
            rule.latitude, rule.longitude, rule.location_name, "US_EPA"
        )
        current_aqi = (aq.aqi_standard_results.get("US_EPA") or {}).get("aqi")
        await alert_service.evaluate_rules_for_location(
            db=db,
            location_name=rule.location_name,
            current_aqi=current_aqi,
            measurements=aq.measurements,
            user_id=current_user.id,
        )
    except Exception as exc:
        logger.warning(
            "[Alerts] Initial evaluation skipped for rule '%s': %s",
            rule.id,
            format_safe_exception(exc),
        )
    return rule


@router.post("/evaluate")
async def evaluate_my_alert_rules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    triggered = await evaluate_active_rules_for_user(db, current_user.id)
    return {"evaluated": True, "triggered_count": len(triggered), "triggered": triggered}


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_rule(
    rule_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await db.execute(
        delete(AlertRule).where(AlertRule.id == rule_id, AlertRule.user_id == current_user.id)
    )
    await db.commit()
    return None

@router.get("/events", response_model=List[AlertEventOut])
async def list_alert_events(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await evaluate_active_rules_for_user(db, current_user.id)
    query = (
        select(AlertEvent)
        .join(AlertRule, AlertEvent.rule_id == AlertRule.id)
        .where(AlertRule.user_id == current_user.id)
        .order_by(AlertEvent.triggered_at.desc())
        .limit(50)
    )
    result = await db.execute(query)
    return result.scalars().all()
