from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from app.core.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class EnvironmentalReport(Base):
    __tablename__ = "environmental_reports"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    location_name = Column(String(255), nullable=False)
    report_type = Column(String(32), default="daily") # daily, weekly, custom
    reporting_period = Column(String(64), nullable=False)
    aqi_standard = Column(String(32), default="US_EPA")
    summary_markdown = Column(Text, nullable=False)
    metrics_json = Column(Text, nullable=False) # JSON data for all chart trends and pollutants
    recommendations_json = Column(Text, nullable=True)
    sources_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", back_populates="reports")

class APIUsageLog(Base):
    __tablename__ = "api_usage_logs"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    endpoint = Column(String(128), nullable=False, index=True)
    method = Column(String(16), nullable=False)
    status_code = Column(String(8), nullable=False)
    response_time_ms = Column(Float, nullable=False)
    client_ip = Column(String(64), nullable=True)
    user_id = Column(String(36), nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
