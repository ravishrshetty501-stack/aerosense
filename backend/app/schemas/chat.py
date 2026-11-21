from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class ChatRequest(BaseModel):
    message: str
    location_hint: Optional[str] = "Tokyo"
    conversation_history: Optional[List[Dict[str, str]]] = None

class ChatResponse(BaseModel):
    response: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    grounding_data: Optional[Dict[str, Any]] = None
    model: str
