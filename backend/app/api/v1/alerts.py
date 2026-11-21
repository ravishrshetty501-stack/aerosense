from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List
from app.core.database import get_db
from app.models.alert import AlertRule, AlertEvent
from app.models.user import User
from app.schemas.alert import AlertRuleCreate, AlertRuleOut, AlertEventOut
from app.api.deps import get_current_user

router = APIRouter(prefix="/alerts", tags=["Intelligent Alerts"])

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
    return rule

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
    query = (
        select(AlertEvent)
        .join(AlertRule, AlertEvent.rule_id == AlertRule.id)
        .where(AlertRule.user_id == current_user.id)
        .order_by(AlertEvent.triggered_at.desc())
        .limit(50)
    )
    result = await db.execute(query)
    return result.scalars().all()
