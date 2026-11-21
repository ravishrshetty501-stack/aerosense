from fastapi import APIRouter, Depends, Body
from typing import Dict, Any
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.ai_service import ai_service
from app.api.deps import get_current_user_optional
from app.models.user import User

router = APIRouter(prefix="/ai", tags=["GenAI Assistant"])

@router.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(
    request: ChatRequest,
    current_user: User = Depends(get_current_user_optional)
):
    result = await ai_service.chat(
        user_message=request.message,
        conversation_history=request.conversation_history,
        location_hint=request.location_hint or "Tokyo"
    )
    return ChatResponse(
        response=result.get("response", ""),
        tool_calls=result.get("tool_calls"),
        grounding_data=result.get("grounding_data"),
        model=result.get("model", "gemini-1.5-flash")
    )

@router.post("/tool")
async def execute_tool_direct(
    tool_name: str = Body(..., embed=True),
    arguments: Dict[str, Any] = Body(..., embed=True)
):
    return await ai_service.execute_tool(tool_name, arguments)
