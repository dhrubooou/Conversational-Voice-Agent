from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()


@router.get("")
async def get_config():
    """
    Returns the configured LiveKit Server URL so the frontend can connect to the correct server.
    """
    return {"livekit_url": settings.LIVEKIT_URL}
