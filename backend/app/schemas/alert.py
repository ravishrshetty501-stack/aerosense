from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Any, Optional
from datetime import datetime

class AlertRuleCreate(BaseModel):
    location_name: str = Field(..., min_length=1, max_length=255)
    latitude: float = Field(..., ge=-90.0, le=90.0, allow_inf_nan=False)
    longitude: float = Field(..., ge=-180.0, le=180.0, allow_inf_nan=False)
    threshold_aqi: float = Field(100.0, ge=0.0, allow_inf_nan=False)
    pollutant: str = "aqi"
    severity: str = "warning"

    @field_validator("location_name", mode="before")
    @classmethod
    def validate_and_strip_location_name(cls, v: Any) -> Any:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("location_name cannot be empty or whitespace-only")
            return stripped
        return v

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
