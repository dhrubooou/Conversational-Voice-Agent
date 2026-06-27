from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.config import settings
from app.services.database_service import get_or_create_session, update_session
from app.schemas.session import EventPayloadSchema
from app.api.endpoints.session import post_session_event
from twilio.twiml.voice_response import VoiceResponse, Gather

router = APIRouter()


def twiml_response(response: VoiceResponse) -> Response:
    """
    Utility to format a Twilio VoiceResponse into a FastAPI XML Response.
    """
    return Response(content=str(response), media_type="application/xml")


@router.post("/welcome/{room_name}")
async def twilio_welcome(room_name: str, db: Session = Depends(get_db)):
    """
    Twilio Outbound webhook: Speaks the call summary to the human representative,
    and prompts them to accept or decline the call transfer.
    """
    session = get_or_create_session(db, room_name)
    summary = (
        session.post_call_summary
        or "A client needs assistance with booking an appointment."
    )

    response = VoiceResponse()
    response.say(
        "Hello. This is OpenVoice AI. I am initiating a warm transfer on behalf of a dental caller.",
        voice="alice",
    )
    response.say(
        f"Here is a short AI summary of their conversation: {summary}", voice="alice"
    )

    gather = Gather(
        num_digits=1,
        action=f"{settings.PUBLIC_BACKEND_URL}/api/v1/twilio/gather/{room_name}",
        timeout=10,
    )
    gather.say(
        "To accept this transfer and connect to the caller, press 1. To decline, press 2.",
        voice="alice",
    )
    response.append(gather)

    # Timeout / No input fallback
    response.say("I did not receive any input. Hanging up now.", voice="alice")
    response.hangup()

    return twiml_response(response)


@router.post("/gather/{room_name}")
async def twilio_gather(
    room_name: str, Digits: str = Query(...), db: Session = Depends(get_db)
):
    """
    Processes the supervisor's DTMF digits.
    If 1 (Accept): Bridges the phone line to the LiveKit Room Audio via WebSocket streams.
    If 2 (Decline): Signals a refusal back to the Agent.
    """
    response = VoiceResponse()

    if Digits == "1":
        # Supervisor accepted call
        payload = EventPayloadSchema(
            transfer_status="accepted",
            call_status="transferring",
            current_action="Representative connected! Bridging call...",
        )
        await post_session_event(room_name, payload, db)

        response.say(
            "Thank you. Bridging you into the caller's audio stream now.", voice="alice"
        )

        # Connect phone audio stream to our WebSocket `/api/v1/twilio/stream`
        ws_host = settings.PUBLIC_BACKEND_URL.replace("http://", "ws://").replace(
            "https://", "wss://"
        )
        connect = response.connect()
        connect.stream(url=f"{ws_host}/api/v1/twilio/stream?room={room_name}")

    else:
        # Supervisor declined call
        payload = EventPayloadSchema(
            transfer_status="declined",
            call_status="connected",
            current_action="Representative unavailable. Returning to caller.",
        )
        await post_session_event(room_name, payload, db)

        response.say("Thank you. The transfer has been cancelled.", voice="alice")
        response.hangup()

    return twiml_response(response)
