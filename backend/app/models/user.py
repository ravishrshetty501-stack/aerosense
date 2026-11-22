from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Float
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from app.core.database import Base, utc_now

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    preferred_standard = Column(String(32), default="US_EPA") # US_EPA, INDIA_CPCB, EUROPEAN_AQI
    theme = Column(String(32), default="dark") # dark, light
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    
    saved_locations = relationship("SavedLocation", back_populates="user", cascade="all, delete-orphan")
    alert_rules = relationship("AlertRule", back_populates="user", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    reports = relationship("EnvironmentalReport", back_populates="user", cascade="all, delete-orphan")

class SavedLocation(Base):
    __tablename__ = "saved_locations"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    country = Column(String(64), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    is_favorite = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)
    
    user = relationship("User", back_populates="saved_locations")
