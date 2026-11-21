from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from app.core.database import get_db
from app.models.user import User, SavedLocation
from app.api.deps import get_current_user

router = APIRouter(prefix="/users", tags=["User Preferences & Saved Locations"])

class SavedLocationCreate(BaseModel):
    name: str
    country: Optional[str] = None
    latitude: float
    longitude: float
    is_favorite: bool = False

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
