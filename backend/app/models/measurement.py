from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Index, Text, Enum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from app.core.database import Base, utc_now

def generate_uuid():
    return str(uuid.uuid4())

class Location(Base):
    __tablename__ = "locations"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False, index=True)
    city = Column(String(255), nullable=True, index=True)
    country = Column(String(64), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    timezone = Column(String(64), default="UTC")
    created_at = Column(DateTime, default=utc_now)

class MonitoringStation(Base):
    __tablename__ = "monitoring_stations"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    external_id = Column(String(128), unique=True, index=True)
    name = Column(String(255), nullable=False)
    provider = Column(String(64), default="OpenAQ") # OpenAQ, Government, etc.
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    country = Column(String(64), nullable=True)
    city = Column(String(255), nullable=True)
    is_active = Column(String(32), default="active")
    last_updated = Column(DateTime, nullable=True)

class Measurement(Base):
    __tablename__ = "measurements"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    location_name = Column(String(255), index=True, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    pollutant = Column(String(32), nullable=False, index=True) # pm25, pm10, no2, so2, co, o3
    value = Column(Float, nullable=False)
    unit = Column(String(32), nullable=False) # ug/m3, ppm, ppb
    measurement_type = Column(String(32), default="ground_observation") 
    # Types: ground_observation, model_estimate, forecast, historical, stale
    source = Column(String(128), nullable=False) # "OpenAQ / Station #1234", "Open-Meteo CAMS"
    data_quality = Column(String(32), default="verified") # verified, provisional, estimated
    observation_timestamp = Column(DateTime, nullable=False, index=True)
    retrieval_timestamp = Column(DateTime, default=utc_now)
    
    __table_args__ = (
        Index("idx_pollutant_time", "pollutant", "observation_timestamp"),
        Index("idx_loc_pollutant_time", "location_name", "pollutant", "observation_timestamp"),
    )

class AQICalculation(Base):
    __tablename__ = "aqi_calculations"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    location_name = Column(String(255), index=True, nullable=False)
    standard = Column(String(32), nullable=False) # US_EPA, INDIA_CPCB, EUROPEAN_AQI
    aqi_value = Column(Float, nullable=False)
    category = Column(String(64), nullable=False) # Good, Moderate, Unhealthy, etc.
    dominant_pollutant = Column(String(32), nullable=False)
    pollutant_subindices = Column(Text, nullable=True) # JSON serialized dictionary of subindices
    calculation_timestamp = Column(DateTime, default=utc_now)
    is_reliable = Column(String(16), default="true") # true or false
