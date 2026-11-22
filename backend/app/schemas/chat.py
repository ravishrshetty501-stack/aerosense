from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="User query prompt")
    location_hint: Optional[str] = Field("Tokyo", max_length=128, description="Target city context")
    conversation_history: Optional[List[Dict[str, str]]] = Field(None, max_length=30, description="Recent conversation turns")

class ChatResponse(BaseModel):
    response: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    grounding_data: Optional[Dict[str, Any]] = None
    model: str
