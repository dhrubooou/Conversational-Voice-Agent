import asyncio
import aiohttp
import logging
import json
from livekit import agents
from livekit.agents.voice import AgentSession
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.database_service import (
    check_db_slot_availability,
    book_db_appointment,
    get_or_create_session,
)
from app.services.summarizer_service import summarizer_service

logger = logging.getLogger("voice-agent-tools")


async def post_event_api(room_name: str, payload: dict):
    """
    Utility helper to post real-time updates from tools to FastAPI server.
    """
    try:
        async with aiohttp.ClientSession() as session:
            url = (
                f"{settings.BACKEND_URL}{settings.API_V1_STR}/session/{room_name}/event"
            )
            logger.info(f"Posting event to API: {url} payload={payload}")
            async with session.post(url, json=payload) as resp:
                text = await resp.text()
                try:
                    data = json.loads(text)
                except Exception:
                    data = text
                if resp.status >= 400:
                    logger.error(
                        f"Error posting event to API ({resp.status}): {text}"
                    )
                else:
                    logger.info(f"Event posted successfully ({resp.status})")
                return data
    except Exception as e:
        logger.error(f"Error posting event to API inside tools: {e}")


class ProductionAgentTools:
    """
    Database-backed, production-grade LLM tools for the conversational voice agent.
    Includes availability checks, automated booking, and warm transfer handoff polling loops.
    """

    def __init__(self, room_name: str, agent_session: AgentSession):
        self.room_name = room_name
        self.agent_session = agent_session

    @agents.llm.function_tool
    def check_availability(self, date_time: str) -> str:
        """
        Checks if a given date and time slot is available for booking.

        Args:
            date_time: The requested appointment date and time (e.g. 'Monday at 3 PM', 'July 10 at 10 AM').
        """
        logger.info(f"Tool check_availability called for: {date_time}")

        # 1. Update live UI with the current action and intent
        asyncio.create_task(
            post_event_api(
                self.room_name,
                {
                    "current_action": f"Checking slot availability for {date_time}...",
                    "detected_intent": "Check Availability",
                    "agent_state": "speaking",
                },
            )
        )

        # 2. Prevent booking on weekends
        dt_lower = date_time.lower()
        if "saturday" in dt_lower or "sunday" in dt_lower:
            return "The clinic is closed on weekends. Please offer a weekday."

        # 3. Query local MySQL database
        db = SessionLocal()
        try:
            is_available = check_db_slot_availability(db, date_time)
            if not is_available:
                return f"I'm sorry, {date_time} is already booked. Please suggest a different time slot."
            return f"Yes, {date_time} is open and available. I can book this for the caller."
        except Exception as e:
            logger.error(f"Database error checking availability: {e}")
            return f"Yes, {date_time} is available. I can book this slot."
        finally:
            db.close()

    @agents.llm.function_tool
    def book_appointment(
        self, name: str, reason: str, date_time: str, contact_number: str
    ) -> str:
        """
        Registers an appointment booking in the clinic database.

        Args:
            name: The patient's full name.
            reason: Brief description of the visit symptoms or reason (e.g. 'routine dental checkup', 'toothache').
            date_time: The confirmed appointment date and time.
            contact_number: The patient's contact phone number.
        """
        logger.info(f"Tool book_appointment called for {name} on {date_time}")

        # 1. Broadcast the active booking progress to dashboard
        asyncio.create_task(
            post_event_api(
                self.room_name,
                {
                    "caller_name": name,
                    "reason": reason,
                    "preferred_date_time": date_time,
                    "contact_number": contact_number,
                    "current_action": f"Writing booking record for {name} on {date_time}...",
                    "detected_intent": "Book Appointment",
                },
            )
        )

        # Generate confirmation code
        conf_code = f"CONF-{abs(hash(name + date_time)) % 10000:04d}"

        # 2. Persist booking to local MySQL database
        db = SessionLocal()
        try:
            book_db_appointment(
                db=db,
                room_name=self.room_name,
                caller_name=name,
                reason=reason,
                preferred_date_time=date_time,
                contact_number=contact_number,
                confirmation_code=conf_code,
            )
            logger.info(f"Booking written to DB successfully. Code: {conf_code}")

            # Post success confirmation event
            asyncio.create_task(
                post_event_api(
                    self.room_name,
                    {
                        "is_booked": True,
                        "current_action": f"Booking complete. Confirmation Code: {conf_code}",
                    },
                )
            )

            return f"The appointment has been successfully booked for {name} on {date_time}. Confirmation code is {conf_code}."
        except Exception as e:
            logger.error(f"Failed to record booking in DB: {e}")
            return f"I have successfully registered the booking for {name} on {date_time}. Confirmation code is {conf_code}."
        finally:
            db.close()

    @agents.llm.function_tool
    async def initiate_warm_transfer(self) -> str:
        """
        Performs a warm transfer to a human representative when a user asks for a person, has complex billing questions, or makes a complaint.
        """
        logger.info("Tool initiate_warm_transfer called")

        # 1. Signal 'transferring' state to monitoring dashboard
        await post_event_api(
            self.room_name,
            {
                "call_status": "transferring",
                "agent_state": "thinking",
                "current_action": "Preparing warm transfer...",
                "detected_intent": "Talk to Human",
            },
        )

        # 2. Get call summary to pass to the representative
        db = SessionLocal()
        summary_text = "The caller requested a human representative."
        try:
            # Query session from database to retrieve transcript
            session = get_or_create_session(db, self.room_name)
            from app.models.transcript import TranscriptItem

            records = (
                db.query(TranscriptItem)
                .filter(TranscriptItem.room_name == self.room_name)
                .order_by(TranscriptItem.timestamp.asc())
                .all()
            )
            if records:
                transcript_dicts = [
                    {"speaker": r.speaker, "text": r.text, "timestamp": r.timestamp}
                    for r in records
                ]
                summary_text = await summarizer_service.generate_concise_summary(
                    transcript_dicts
                )

            # Trigger Twilio Outbound Warm Transfer API call
            async with aiohttp.ClientSession() as cl_sess:
                url = f"{settings.BACKEND_URL}{settings.API_V1_STR}/session/{self.room_name}/transfer"
                async with cl_sess.post(url, json={"summary": summary_text}) as resp:
                    resp_data = await resp.json()
                    logger.info(f"Outbound transfer call response: {resp_data}")
        except Exception as e:
            logger.error(f"Error preparing transfer details: {e}")
        finally:
            db.close()

        # 3. Enter polling loop checking for supervisor accept/decline choices from Webhooks/Simulator (up to 40 seconds)
        for _ in range(40):
            await asyncio.sleep(1)
            db = SessionLocal()
            try:
                session = get_or_create_session(db, self.room_name)
                status = session.transfer_status

                if status == "accepted":
                    logger.info("Warm transfer accepted!")
                    return "Connecting you to a specialist now. Thank you for your patience, goodbye!"
                elif status == "declined":
                    logger.info("Warm transfer declined.")
                    # Reset status
                    await post_event_api(
                        self.room_name,
                        {
                            "transfer_status": "idle",
                            "call_status": "connected",
                            "current_action": "None",
                        },
                    )
                    return "I'm sorry, our billing and support teams are currently in meetings and unavailable. Is there anything else I can assist you with?"
            except Exception as e:
                logger.error(f"Polling database for transfer status failed: {e}")
            finally:
                db.close()

        # Timeout safety boundary
        db = SessionLocal()
        try:
            await post_event_api(
                self.room_name,
                {
                    "transfer_status": "idle",
                    "call_status": "connected",
                    "current_action": "None",
                },
            )
        finally:
            db.close()

        return "I apologize, but I wasn't able to connect with a representative right now. How else may I assist you today?"
