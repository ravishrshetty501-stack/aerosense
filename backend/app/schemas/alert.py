from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class AlertRuleCreate(BaseModel):
    location_name: str
    latitude: float
    longitude: float
    threshold_aqi: float = 100.0
    pollutant: str = "aqi"
    severity: str = "warning"

class AlertRuleOut(AlertRuleCreate):
    id: str
    is_active: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class AlertEventOut(BaseModel):
    id: str
    rule_id: str
    location_name: str
    trigger_value: float
    threshold_value: float
    pollutant: str
    severity: str
    message: str
    acknowledged: bool
    triggered_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
