from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal, Optional, List, Dict, Any

MAX_HISTORY_TURNS = 12
MAX_HISTORY_MESSAGE_CHARS = 1500
MAX_HISTORY_TOTAL_CHARS = 6000


class ChatHistoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=MAX_HISTORY_MESSAGE_CHARS)

    @field_validator("content")
    @classmethod
    def validate_non_empty_content(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Conversation history content cannot be empty.")
        return value.strip()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="User query prompt")
    location_hint: Optional[str] = Field("Tokyo", max_length=128, description="Target city context")
    conversation_history: Optional[List[ChatHistoryMessage]] = Field(
        None,
        max_length=MAX_HISTORY_TURNS,
        description="Recent conversation turns",
    )

    @field_validator("conversation_history")
    @classmethod
    def validate_total_history_size(
        cls, value: Optional[List[ChatHistoryMessage]]
    ) -> Optional[List[ChatHistoryMessage]]:
        if value:
            total_chars = sum(len(item.content) for item in value)
            if total_chars > MAX_HISTORY_TOTAL_CHARS:
                raise ValueError(
                    f"Total conversation_history size exceeds {MAX_HISTORY_TOTAL_CHARS} characters."
                )
        return value


class ChatResponse(BaseModel):
    response: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    grounding_data: Optional[Dict[str, Any]] = None
    model: str
