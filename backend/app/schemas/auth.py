from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=255)
    preferred_standard: Optional[str] = "US_EPA"
    theme: Optional[str] = "dark"

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=256)

    @field_validator("password")
    @classmethod
    def reject_whitespace_only_password(cls, v: str) -> str:
        # Preserve exact password characters (including intentional spaces) while blocking blank passwords.
        if not v.strip():
            raise ValueError("Password cannot be empty or whitespace-only")
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=256)

class UserOut(UserBase):
    id: str
    is_active: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

class TokenPayload(BaseModel):
    sub: Optional[str] = None
