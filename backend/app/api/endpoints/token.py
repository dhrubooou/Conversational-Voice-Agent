from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.core.config import settings
from livekit.api import AccessToken, VideoGrants

router = APIRouter()


@router.get("")
async def get_token(room: str, identity: str, name: Optional[str] = None):
    """
    Generates a secure LiveKit Access Token for a room participant.
    """
    if not settings.LIVEKIT_API_KEY or not settings.LIVEKIT_API_SECRET:
        raise HTTPException(
            status_code=500, detail="LiveKit keys are not configured in backend."
        )

    try:
        token = (
            AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
            .with_identity(identity)
            .with_name(name or identity)
            .with_grants(
                VideoGrants(
                    room_join=True,
                    room=room,
                    can_publish=True,
                    can_subscribe=True,
                    can_publish_data=True,
                )
            )
        )
        return {"token": token.to_jwt()}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate AccessToken: {str(e)}"
        )
