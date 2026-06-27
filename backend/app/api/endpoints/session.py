import time
import logging
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.config import settings
from openai import AsyncOpenAI
from app.schemas.session import (
    EventPayloadSchema,
    SessionStateResponse,
    TransferRequest,
)
from app.schemas.appointment import AppointmentBase
from app.services.database_service import book_db_appointment
from app.models.session import CallSession

# Extractor client (Always connects to OpenAI's Cloud for high-accuracy entity parsing)
openai_extractor_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY or "none")

# Conversation client (Connects locally to Ollama, or falls back to OpenAI)
llm_conversation_client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY or "ollama", base_url=settings.LLM_BASE_URL
)


async def extract_fields_from_transcript(text: str) -> dict:
    """
    Uses OpenAI GPT-4o-mini to intelligently extract Name, Contact Number,
    Reason, and Preferred Date/Time from the transcript text.
    """
    if not settings.OPENAI_API_KEY:
        return {}

    prompt = (
        "You are an information extraction assistant. Extract the following dental clinic appointment fields from the user text:\n"
        "- caller_name\n"
        "- contact_number\n"
        "- reason\n"
        "- preferred_date_time\n\n"
        "Return the result ONLY as a raw, single-line JSON object with keys: "
        '"caller_name", "contact_number", "reason", "preferred_date_time". '
        "If a field is not explicitly mentioned, set its value to null. Do not include markdown formatting or backticks.\n\n"
        f'User text: "{text}"'
    )

    try:
        response = await openai_extractor_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.0,
        )
        content = response.choices[0].message.content.strip()
        # Clean potential markdown backticks
        content = content.replace("```json", "").replace("```", "").strip()
        data = json.loads(content)
        # Filter out nulls
        return {k: v for k, v in data.items() if v is not None}
    except Exception as e:
        print(f"⚠️ Error in AI entity extraction: {e}")
        return {}


async def generate_ai_reply(room_name: str, caller_text: str, db: Session) -> str:
    """
    Calls Ollama (or OpenAI fallback) to generate a helpful, warm receptionist reply
    as Agent A, and appends it to the room session in the database.
    """
    if not settings.OPENAI_API_KEY and not settings.LLM_BASE_URL:
        return "I have received your request. Let me assist you."

    # Get recent transcript history to provide context
    transcript_records = get_session_transcript(db, room_name)
    history = []

    # Fetch session state to inject Doctor availability context dynamically!
    session_state = (
        db.query(CallSession).filter(CallSession.room_name == room_name).first()
    )
    booking_context = ""
    if session_state:
        if session_state.is_booked and session_state.preferred_date_time:
            conf_code = f"CONF-{abs(hash(session_state.caller_name + session_state.preferred_date_time)) % 10000:04d}"
            booking_context = (
                f"BACKGROUND CONTEXT: The doctor is AVAILABLE on {session_state.preferred_date_time}. "
                f"You have successfully proceeded and registered the appointment in MySQL database. "
                f"The booking confirmation code is {conf_code}. Read this code back to the caller and congratulate them!"
            )
        elif session_state.preferred_date_time and not session_state.is_booked:
            booking_context = (
                f"BACKGROUND CONTEXT: The doctor is NOT AVAILABLE on {session_state.preferred_date_time} (fully booked). "
                "Apologize politely, explain that the doctor is fully booked at that time, and request they try another slot."
            )

    # Add system instructions to make LLaMA highly conversational like a real open chatbot
    system_content = (
        "You are Agent A, a real, warm, intelligent, and highly conversational AI chatbot for our dental clinic. "
        "Your goal is to hold open, friendly, and natural conversations about any topic (answering general questions, "
        "telling jokes, or engaging in friendly chitchat) to make the caller feel completely comfortable and welcomed, "
        "exactly like a real human receptionist! "
        "Maintain a charming, lively, and engaging persona. "
        "If the caller wants to schedule an appointment, collect their Details (Name, Symptoms, Date/Time, and Phone) "
        "and tell them you are checking the schedule. "
        "Keep your responses snappy, conversational, and under 2-3 sentences."
    )
    if booking_context:
        system_content += f"\n\n{booking_context}"

    history.append(
        {
            "role": "system",
            "content": system_content,
        }
    )

    # Add previous history
    for item in transcript_records[-6:]:  # last 6 messages
        role = "assistant" if item["speaker"] == "agent" else "user"
        history.append({"role": role, "content": item["text"]})

    # Add current message
    history.append({"role": "user", "content": caller_text})

    try:
        response = await llm_conversation_client.chat.completions.create(
            model=settings.LLM_MODEL, messages=history, max_tokens=80, temperature=0.7
        )
        reply = response.choices[0].message.content.strip()
        return reply
    except Exception as e:
        print(f"⚠️ Error generating AI reply from local LLM: {e}")
        return "Thank you. Let me check those details for you."


from app.services.database_service import (
    get_or_create_session,
    update_session,
    reset_db_session,
    get_session_transcript,
)
from app.core.websocket_manager import ws_manager
from app.services.twilio_service import twilio_service

router = APIRouter()

logger = logging.getLogger("api-session")


@router.get("/{room_name}", response_model=SessionStateResponse)
async def get_session_state(room_name: str, db: Session = Depends(get_db)):
    """
    Fetches the current persistent call session state from the database.
    """
    session = get_or_create_session(db, room_name)
    transcript = get_session_transcript(db, room_name)

    return {
        "room_name": session.room_name,
        "caller_name": session.caller_name,
        "reason": session.reason,
        "preferred_date_time": session.preferred_date_time,
        "contact_number": session.contact_number,
        "is_booked": session.is_booked,
        "call_status": session.call_status,
        "agent_state": session.agent_state,
        "detected_intent": session.detected_intent,
        "current_action": session.current_action,
        "transcript": transcript,
        "transfer_status": session.transfer_status,
        "post_call_summary": session.post_call_summary or "",
        "takeover_active": session.takeover_active,
    }


@router.post("/{room_name}/reset")
async def post_reset_session(room_name: str, db: Session = Depends(get_db)):
    """
    Completely resets a persistent room session back to pristine empty state and clears transcripts.
    Broadcasts the newly reset state over WebSockets to all subscribed supervisors.
    """
    # 1. Reset in database
    reset_db_session(db, room_name)

    # 2. Get full state
    state = await get_session_state(room_name, db)

    # 3. Broadcast empty state to WebSockets
    await ws_manager.broadcast(room_name, state)

    return state


@router.post("/{room_name}/event")
async def post_session_event(
    room_name: str, payload: EventPayloadSchema, db: Session = Depends(get_db)
):
    """
    Receives state updates from the LiveKit voice agent, saves them to MySQL,
    and broadcasts the updated state over WebSockets to all subscribed monitoring consoles.
    """
    # If a new caller transcript item is received, intelligently extract dental form entities
    if payload.transcript_item and payload.transcript_item.speaker == "caller":
        extracted_data = await extract_fields_from_transcript(
            payload.transcript_item.text
        )
        if extracted_data:
            logger.info(
                f"Intelligently extracted fields from caller text: {extracted_data}"
            )
            # Merge extracted data into our payload
            if "caller_name" in extracted_data and not payload.caller_name:
                payload.caller_name = extracted_data["caller_name"]
            if "reason" in extracted_data and not payload.reason:
                payload.reason = extracted_data["reason"]
            if "contact_number" in extracted_data and not payload.contact_number:
                payload.contact_number = extracted_data["contact_number"]
            if (
                "preferred_date_time" in extracted_data
                and not payload.preferred_date_time
            ):
                date_time = extracted_data["preferred_date_time"]

                # Check Doctor availability in MySQL database!
                from app.services.database_service import (
                    check_db_slot_availability,
                    book_db_appointment,
                )

                is_available = check_db_slot_availability(db, date_time)

                if is_available:
                    # Proceed with booking
                    payload.preferred_date_time = date_time
                    payload.is_booked = True
                    payload.current_action = (
                        f"Doctor is available at {date_time}. Booking registered!"
                    )

                    # Persist booking to local MySQL database
                    name = (
                        payload.caller_name or session.caller_name or "Valued Patient"
                    )
                    phone = (
                        payload.contact_number or session.contact_number or "555-0100"
                    )
                    reason = payload.reason or session.reason or "Dental Checkup"
                    conf_code = f"CONF-{abs(hash(name + date_time)) % 10000:04d}"

                    book_db_appointment(
                        db=db,
                        room_name=room_name,
                        caller_name=name,
                        reason=reason,
                        preferred_date_time=date_time,
                        contact_number=phone,
                        confirmation_code=conf_code,
                    )
                else:
                    # Slot taken
                    payload.preferred_date_time = date_time
                    payload.is_booked = False
                    payload.current_action = (
                        f"Doctor is fully booked at {date_time}. Slot rejected."
                    )

    # 1. Update session state in database
    session = update_session(db, room_name, payload)

    # 1.5 If a new caller transcript was added, automatically generate a local Llama2/receptionist response!
    # (Bypasses any WebRTC voice latency for seamless, reactive chat monitoring!)
    # But ONLY do this if we are NOT in active supervisor takeover mode!
    if (
        payload.transcript_item
        and payload.transcript_item.speaker == "caller"
        and not session.takeover_active
    ):
        # Check if caller mentioned representative or billing to trigger transfer intent!
        lower_text = payload.transcript_item.text.lower()
        if (
            "human" in lower_text
            or "representative" in lower_text
            or "person" in lower_text
            or "billing" in lower_text
        ):
            # Trigger transfer intent and calling status
            payload_update = EventPayloadSchema(
                detected_intent="Talk to Human",
                transfer_status="calling",
                current_action="Dialing human representative...",
            )
            update_session(db, room_name, payload_update)

            # Start Twilio call via FastAPI
            summary_text = "The caller requested a human representative."
            twilio_service.make_outbound_call(room_name, summary_text)
        else:
            # Generate local LLM receptionist reply!
            reply_text = await generate_ai_reply(
                room_name, payload.transcript_item.text, db
            )

            # Save the receptionist's reply in the database
            from app.schemas.session import TranscriptItemSchema

            reply_payload = EventPayloadSchema(
                agent_state="speaking",
                transcript_item=TranscriptItemSchema(
                    speaker="agent", text=reply_text, timestamp=time.time()
                ),
            )
            update_session(db, room_name, reply_payload)

    # 2. Get full updated session state to broadcast
    state = await get_session_state(room_name, db)

    # 3. Broadcast the state update to all WebSocket subscribers in this room
    await ws_manager.broadcast(room_name, state)

    return state


@router.post("/{room_name}/book")
async def post_manual_book_appointment(
    room_name: str, payload: AppointmentBase, db: Session = Depends(get_db)
):
    """
    Manually books an appointment submitted by the Watcher/Supervisor.
    Saves the appointment to MySQL, updates the CallSession booking state,
    and broadcasts the updated state over WebSockets to sync all monitoring consoles.
    """
    conf_code = f"CONF-{abs(hash(payload.caller_name + payload.preferred_date_time)) % 10000:04d}"

    # 1. Save booking to MySQL and update session state
    book_db_appointment(
        db=db,
        room_name=room_name,
        caller_name=payload.caller_name,
        reason=payload.reason or "",
        preferred_date_time=payload.preferred_date_time,
        contact_number=payload.contact_number,
        confirmation_code=conf_code,
    )

    # 2. Get full updated state to broadcast
    state = await get_session_state(room_name, db)

    # 3. Broadcast to all WebSockets
    await ws_manager.broadcast(room_name, state)

    return state


@router.post("/{room_name}/takeover")
async def post_takeover(room_name: str, db: Session = Depends(get_db)):
    """
    Signals that a supervisor has taken over the conversation.
    Saves state in DB and broadcasts update over WebSockets.
    """
    payload = EventPayloadSchema(
        takeover_active=True,
        agent_state="monitoring",
        current_action="Watcher took over conversation",
    )
    return await post_session_event(room_name, payload, db)


@router.post("/{room_name}/transfer")
async def post_transfer(
    room_name: str, payload: TransferRequest, db: Session = Depends(get_db)
):
    """
    Agent triggers a warm transfer outbound call to the supervisor phone.
    """
    # 1. Update session DB to 'calling'
    event_payload = EventPayloadSchema(
        transfer_status="calling", current_action=f"Dialing human agent..."
    )
    await post_session_event(room_name, event_payload, db)

    # Save the summary in session so we can read it during Twilio webhook TwiML
    session = get_or_create_session(db, room_name)
    session.post_call_summary = payload.summary
    db.commit()

    # 2. Trigger Outbound Twilio call
    success = twilio_service.make_outbound_call(room_name, payload.summary)
    if not success:
        # Fallback to simulated calling if Twilio fails or is not set up
        event_payload = EventPayloadSchema(
            transfer_status="calling",
            current_action="Dialing human agent (simulator fallback)...",
        )
        await post_session_event(room_name, event_payload, db)
        return {
            "status": "simulated",
            "message": "Twilio not fully configured. Using simulation fallback.",
        }

    return {"status": "success"}


@router.post("/{room_name}/simulate-transfer")
async def post_simulate_transfer(
    room_name: str, decision: str = Query(...), db: Session = Depends(get_db)
):
    """
    Simulates the warm transfer acceptance or decline for local sandbox environments.
    """
    if decision == "accept":
        payload = EventPayloadSchema(
            transfer_status="accepted",
            call_status="transferring",
            current_action="Bridge completed (simulated human connected)",
        )
    else:
        payload = EventPayloadSchema(
            transfer_status="declined",
            call_status="connected",
            current_action="Human declined (simulated). Returning to caller.",
        )

    return await post_session_event(room_name, payload, db)
