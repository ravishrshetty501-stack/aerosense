from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Any, List, Optional
from app.core.database import get_db
from app.models.user import User, SavedLocation
from app.api.deps import get_current_user

router = APIRouter(prefix="/users", tags=["User Preferences & Saved Locations"])

class SavedLocationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    country: Optional[str] = Field(None, max_length=64)
    latitude: float = Field(..., ge=-90.0, le=90.0, allow_inf_nan=False)
    longitude: float = Field(..., ge=-180.0, le=180.0, allow_inf_nan=False)
    is_favorite: bool = False

    @field_validator("name", mode="before")
    @classmethod
    def validate_and_strip_name(cls, v: Any) -> Any:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("name cannot be empty or whitespace-only")
            return stripped
        return v

class SavedLocationOut(BaseModel):
    id: str
    name: str
    country: Optional[str] = None
    latitude: float
    longitude: float
    is_favorite: bool
    
    model_config = ConfigDict(from_attributes=True)

@router.get("/saved-locations", response_model=List[SavedLocationOut])
async def get_saved_locations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(SavedLocation).where(SavedLocation.user_id == current_user.id))
    return result.scalars().all()

@router.post("/saved-locations", response_model=SavedLocationOut, status_code=status.HTTP_201_CREATED)
async def add_saved_location(
    loc_in: SavedLocationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    loc = SavedLocation(
        user_id=current_user.id,
        name=loc_in.name,
        country=loc_in.country,
        latitude=loc_in.latitude,
        longitude=loc_in.longitude,
        is_favorite=loc_in.is_favorite
    )
    db.add(loc)
    await db.commit()
    await db.refresh(loc)
    return loc

@router.delete("/saved-locations/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_saved_location(
    location_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await db.execute(
        delete(SavedLocation).where(SavedLocation.id == location_id, SavedLocation.user_id == current_user.id)
    )
    await db.commit()
    return None
