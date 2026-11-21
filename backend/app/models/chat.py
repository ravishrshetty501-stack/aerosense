from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from app.core.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    title = Column(String(255), default="Environmental Consultation")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(32), nullable=False) # 'user', 'assistant', 'system', 'tool'
    content = Column(Text, nullable=False)
    tool_calls_json = Column(Text, nullable=True) # Serialized tool calls if any
    tool_results_json = Column(Text, nullable=True) # Serialized tool results
    grounding_data_json = Column(Text, nullable=True) # Grounded sources, timestamps, stations
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    session = relationship("ChatSession", back_populates="messages")
