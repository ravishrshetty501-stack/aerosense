"""
SQLAlchemy models registration package for AeroSense AI.
Ensures all 12 database models and their table definitions are registered on Base.metadata.
"""
from app.core.database import Base
from app.models.user import User, SavedLocation
from app.models.measurement import Location, MonitoringStation, Measurement, AQICalculation
from app.models.alert import AlertRule, AlertEvent
from app.models.chat import ChatSession, ChatMessage
from app.models.report import EnvironmentalReport, APIUsageLog

__all__ = [
    "Base",
    "User",
    "SavedLocation",
    "Location",
    "MonitoringStation",
    "Measurement",
    "AQICalculation",
    "AlertRule",
    "AlertEvent",
    "ChatSession",
    "ChatMessage",
    "EnvironmentalReport",
    "APIUsageLog",
]
