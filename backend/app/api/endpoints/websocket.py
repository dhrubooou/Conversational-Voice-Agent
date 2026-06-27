import json
import base64
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.core.config import settings
from app.core.websocket_manager import ws_manager
from livekit.api import AccessToken, VideoGrants
from livekit import rtc
import audioop

router = APIRouter()


@router.websocket("/monitor/{room_name}")
async def websocket_monitor_endpoint(websocket: WebSocket, room_name: str):
    """
    WebSocket endpoint that lets real-time React Monitoring Dashboards subscribe to a room.
    Pushes instantaneous, event-driven JSON updates of transcripts, actions, and timeline events.
    """
    # Accept the connection
    await ws_manager.connect(room_name, websocket)

    db = SessionLocal()
    # Send the current database session state immediately upon connecting
    try:
        from app.api.endpoints.session import get_session_state

        initial_state = await get_session_state(room_name, db)
        await websocket.send_json(initial_state)
    except Exception as e:
        print(f"⚠️ Error sending initial state on WebSocket connection: {e}")
    finally:
        db.close()

    try:
        while True:
            # Keep connection alive; look for optional messages from client
            data = await websocket.receive_text()
            # If dashboard sends any manual signals, we can process them here
    except WebSocketDisconnect:
        ws_manager.disconnect(room_name, websocket)
    except Exception as e:
        print(f"⚠️ Error in dashboard monitor WebSocket: {e}")
        ws_manager.disconnect(room_name, websocket)


@router.websocket("/stream")
async def twilio_audio_stream_endpoint(websocket: WebSocket, room: str):
    """
    WebSocket bridging Twilio raw PCMU phone audio and LiveKit Room.
    Acts as a software audio-bridge gateway (linear PCM <-> Mu-law conversion).
    """
    await websocket.accept()
    print(f"📞 Twilio PSTN Stream connected for room: {room}")

    if (
        not settings.LIVEKIT_URL
        or not settings.LIVEKIT_API_KEY
        or not settings.LIVEKIT_API_SECRET
    ):
        print("❌ LiveKit key config error for Twilio Stream")
        await websocket.close()
        return

    # Generate token for the bridge participant (Human Agent)
    token = (
        AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
        .with_identity("human_agent")
        .with_name("Human Agent (Phone)")
        .with_grants(
            VideoGrants(
                room_join=True,
                room=room,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            )
        )
    ).to_jwt()

    lk_room = rtc.Room()
    audio_source = rtc.AudioSource(16000, 1)  # 16kHz Mono PCM
    track = rtc.LocalAudioTrack.create_audio_track("human_agent_voice", audio_source)

    stream_sid = None

    # Task to handle sending LiveKit audio back to Twilio
    async def send_lk_audio_to_twilio(remote_track):
        audio_stream = rtc.AudioStream(remote_track)
        async for frame in audio_stream:
            if stream_sid is None:
                continue
            try:
                # Convert 16kHz PCM to 8kHz PCMU (Mu-law)
                pcm_8k, _ = audioop.ratecv(frame.data, 2, 1, 16000, 8000, None)
                mulaw_data = audioop.lin2ulaw(pcm_8k, 2)
                payload = base64.b64encode(mulaw_data).decode("utf-8")

                message = {
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {"payload": payload},
                }
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                print("⚠️ Error streaming LiveKit audio to Twilio:", e)
                break

    @lk_room.on("track_subscribed")
    def on_track_subscribed(
        track: rtc.RemoteTrack,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        if (
            track.kind == rtc.TrackKind.KIND_AUDIO
            and participant.identity != "human_agent"
        ):
            print(
                f"🎙️ Subscribed to {participant.identity}'s voice track, routing to Twilio handset..."
            )
            asyncio.create_task(send_lk_audio_to_twilio(track))

    try:
        # Connect to LiveKit Room
        await lk_room.connect(settings.LIVEKIT_URL, token)
        # Publish our audio source
        await lk_room.local_participant.publish_track(track)
        print(
            "✅ Audio bridge successfully joined and published voice track in LiveKit room"
        )

        # Listen to Twilio stream messages
        while True:
            message_text = await websocket.receive_text()
            data = json.loads(message_text)

            if data["event"] == "start":
                stream_sid = data["start"]["streamSid"]
                print(f"📞 Twilio Stream handshake complete. StreamSid: {stream_sid}")
            elif data["event"] == "media":
                if stream_sid is None:
                    continue
                payload = data["media"]["payload"]
                mulaw_data = base64.b64decode(payload)

                # Convert 8kHz PCMU (Mu-law) to 16kHz linear PCM
                pcm_8k = audioop.ulaw2lin(mulaw_data, 2)
                pcm_16k, _ = audioop.ratecv(pcm_8k, 2, 1, 8000, 16000, None)

                # Write PCM frame to LiveKit
                frame = rtc.AudioFrame(pcm_16k, 16000, 1, len(pcm_16k) // 2)
                await audio_source.capture_frame(frame)
            elif data["event"] == "stop":
                print("📞 Twilio Stream requested stop")
                break

    except WebSocketDisconnect:
        print("🔌 Twilio Stream WebSocket disconnected")
    except Exception as e:
        print("❌ Error in Twilio Audio Stream Bridge:", e)
    finally:
        await lk_room.disconnect()
        print("🔌 Bridge participant disconnected from LiveKit room")
