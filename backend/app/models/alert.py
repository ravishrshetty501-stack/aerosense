from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from app.core.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class AlertRule(Base):
    __tablename__ = "alert_rules"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    location_name = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    threshold_aqi = Column(Float, default=100.0) # Trigger if AQI exceeds this
    pollutant = Column(String(32), default="aqi") # 'aqi', 'pm25', 'pm10', 'o3'
    severity = Column(String(32), default="warning") # advisory, warning, critical
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", back_populates="alert_rules")
    events = relationship("AlertEvent", back_populates="rule", cascade="all, delete-orphan")

class AlertEvent(Base):
    __tablename__ = "alert_events"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    rule_id = Column(String(36), ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    location_name = Column(String(255), nullable=False)
    trigger_value = Column(Float, nullable=False)
    threshold_value = Column(Float, nullable=False)
    pollutant = Column(String(32), nullable=False)
    severity = Column(String(32), nullable=False)
    message = Column(Text, nullable=False)
    acknowledged = Column(Boolean, default=False)
    triggered_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    rule = relationship("AlertRule", back_populates="events")
