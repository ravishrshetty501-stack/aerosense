from fastapi import APIRouter
from datetime import datetime, timezone
from app.core.config import settings

router = APIRouter(prefix="/system", tags=["System & Health"])

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "providers": {
            "openaq_configured": bool(settings.OPENAQ_API_KEY),
            "open_meteo": "active",
            "gemini_ai_configured": bool(settings.GEMINI_API_KEY)
        },
        "standards_supported": ["US_EPA", "INDIA_CPCB", "EUROPEAN_AQI"]
    }
