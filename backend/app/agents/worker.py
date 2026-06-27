import os
import json
import asyncio
import aiohttp
import logging
from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import openai, deepgram, silero

# Load environment variables from backend/.env so worker picks up LIVEKIT_URL
load_dotenv()

# Ensure configurations are imported
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.summarizer_service import summarizer_service
from app.agents.tools import ProductionAgentTools, post_event_api

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice-agent-worker")


async def reset_session_api(room_name: str):
    """
    Calls the FastAPI reset endpoint to wipe database states and broadcast a fresh empty slate.
    """
    try:
        async with aiohttp.ClientSession() as session:
            url = (
                f"{settings.BACKEND_URL}{settings.API_V1_STR}/session/{room_name}/reset"
            )
            async with session.post(url) as resp:
                await resp.json()
    except Exception as e:
        logger.error(f"Error resetting session via API: {e}")


async def entrypoint(ctx: JobContext):
    logger.info(f"🚀 Job process allocated. Joining LiveKit room: {ctx.room.name}")
    await ctx.connect()

    # Reset old session details to ensure fresh starting slate on every connect
    await reset_session_api(ctx.room.name)

    session = AgentSession()
    tools = ProductionAgentTools(ctx.room.name, session)

    # Configure production voice agent pipelines
    agent = Agent(
        instructions=(
            "You are Agent A, a real, warm, intelligent, and highly conversational AI chatbot receptionist for a dental clinic.\n"
            "Your goals are:\n"
            "1. Hold open, friendly, and natural conversations about any topic (answering general questions, "
            "telling jokes, or engaging in friendly chitchat) to make the caller feel completely comfortable and welcomed!\n"
            "2. If they are ready to schedule an appointment, collect: Name, Symptoms, Date/Time, and Contact Number.\n"
            "3. BEFORE booking, you MUST check slot availability using check_availability. Suggest another slot if taken.\n"
            "4. ONCE available, call book_appointment to confirm, and speak the confirmation code back clearly.\n"
            "5. If they request a person, call initiate_warm_transfer. Let them know you are checking availability first. "
            "If accepted, say goodbye and go silent. If declined, explain they are currently unavailable and offer other help.\n"
            "Keep your responses snappy, conversational, and under 2-3 sentences."
        ),
        stt=deepgram.STT(),
        llm=openai.LLM(
            model=settings.LLM_MODEL,
            base_url=settings.LLM_BASE_URL,
            api_key=settings.OPENAI_API_KEY or "ollama",
        ),
        tts=deepgram.TTS(),
        vad=silero.VAD.load(),
        tools=[tools],
        allow_interruptions=True,
    )

    # Event listeners on the session to push live monitoring data
    @session.on("agent_state_changed")
    def on_agent_state_changed(ev: agents.voice.events.AgentStateChangedEvent):
        # Map LiveKit states ('initializing', 'idle', 'listening', 'thinking', 'speaking') to dashboard states
        state_map = {
            "initializing": "listening",
            "idle": "listening",
            "listening": "listening",
            "thinking": "thinking",
            "speaking": "speaking",
        }

        async def verify_and_post():
            db = SessionLocal()
            try:
                # If takeover is active, prevent changing state away from 'monitoring'
                from app.services.database_service import get_or_create_session

                s_data = get_or_create_session(db, ctx.room.name)
                if s_data.takeover_active:
                    return
                ui_state = state_map.get(ev.new_state, "listening")
                await post_event_api(ctx.room.name, {"agent_state": ui_state})
            except Exception:
                pass
            finally:
                db.close()

        asyncio.create_task(verify_and_post())

    @session.on("user_input_transcribed")
    def on_user_transcribed(ev: agents.voice.events.UserInputTranscribedEvent):
        if ev.transcript.strip():
            logger.info(f"User transcription received: {ev.transcript}")
            asyncio.create_task(
                post_event_api(
                    ctx.room.name,
                    {"transcript_item": {"speaker": "caller", "text": ev.transcript}},
                )
            )

    @session.on("conversation_item_added")
    def on_item_added(ev: agents.voice.events.ConversationItemAddedEvent):
        role = getattr(ev.item, "role", None)
        content = getattr(ev.item, "content", None)
        if role == "assistant" and isinstance(content, str) and content.strip():
            logger.info(f"Agent reply received: {content}")
            asyncio.create_task(
                post_event_api(
                    ctx.room.name,
                    {"transcript_item": {"speaker": "agent", "text": content}},
                )
            )

    # Handle supervisor takeover signaled over WebRTC room data channel
    @ctx.room.on("data_received")
    def on_data_received(data_packet: rtc.DataPacket):
        try:
            payload = json.loads(data_packet.data.decode("utf-8"))
            if payload.get("type") == "take_over":
                logger.info(
                    "🚨 Takeover message caught on WebRTC! Transitioning agent to silent observer..."
                )

                # 1. Mute local agent audio track immediately at source
                for (
                    publication
                ) in ctx.room.local_participant.track_publications.values():
                    if (
                        publication.track
                        and publication.track.kind == rtc.TrackKind.KIND_AUDIO
                    ):
                        publication.track.mute()

                # 2. Update agent instructions so LLM stops generating text replies
                agent.update_instructions(
                    "A HUMAN SUPERVISOR HAS TAKEN OVER THIS CONVERSATION. "
                    "YOU ARE IN SILENT OBSERVER MODE. "
                    "DO NOT SPEAK, CHAT, OR GENERATE ANY RESPONSE under any circumstances. REMAIN SILENT."
                )

                # 3. Post state update to FastAPI (saving to DB and broadcasting to UI)
                asyncio.create_task(
                    post_event_api(
                        ctx.room.name,
                        {
                            "takeover_active": True,
                            "agent_state": "monitoring",
                            "current_action": "Supervisor took over call",
                        },
                    )
                )
            elif payload.get("type") == "chat":
                text = payload.get("text")
                logger.info(f"💬 Received chat text message from caller: {text}")

                # 1. Append message to chat context
                session.chat_ctx.append(role="user", text=text)

                # 2. Trigger response generation
                asyncio.create_task(session.generate_reply())
        except Exception as e:
            logger.error(f"Error handling room data packet: {e}")

    # Launch the agent session
    await session.start(agent, room=ctx.room)
    logger.info("✅ Agent session active in room")

    # Monitor room state; loop keeps the connection alive
    try:
        while ctx.room.connection_state == rtc.ConnectionState.CONNECTED:
            await asyncio.sleep(1)

            # Double check takeover state syncing
            db = SessionLocal()
            try:
                from app.services.database_service import get_or_create_session

                s_data = get_or_create_session(db, ctx.room.name)
                if s_data.takeover_active:
                    # Confirm track is muted
                    for (
                        publication
                    ) in ctx.room.local_participant.track_publications.values():
                        if (
                            publication.track
                            and publication.track.kind == rtc.TrackKind.KIND_AUDIO
                        ):
                            if not publication.track.muted:
                                publication.track.mute()
            except Exception:
                pass
            finally:
                db.close()
    except Exception as e:
        logger.error(f"Error in room loop: {e}")

    logger.info("🔌 Caller hung up. Generating post-call clinical summary...")

    # Generate detailed clinical summary on session close using OpenAI Async summarizer service
    db = SessionLocal()
    try:
        from app.models.transcript import TranscriptItem

        records = (
            db.query(TranscriptItem)
            .filter(TranscriptItem.room_name == ctx.room.name)
            .order_by(TranscriptItem.timestamp.asc())
            .all()
        )
        if records:
            transcript_dicts = [
                {"speaker": r.speaker, "text": r.text, "timestamp": r.timestamp}
                for r in records
            ]
            markdown_summary = await summarizer_service.generate_post_call_summary(
                transcript_dicts
            )
        else:
            markdown_summary = (
                "### 📞 Call Details\n- **No voice transcript registered.**"
            )

        await post_event_api(
            ctx.room.name,
            {
                "call_status": "ended",
                "post_call_summary": markdown_summary,
                "current_action": "Call ended",
            },
        )
        logger.info("✅ Post-call summary saved and broadcasted successfully.")
    except Exception as e:
        logger.error(f"Error generating final post-call summary: {e}")
        await post_event_api(
            ctx.room.name, {"call_status": "ended", "current_action": "Call ended"}
        )
    finally:
        db.close()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
