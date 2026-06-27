from pydantic import BaseModel
from typing import List, Optional


class TranscriptItemSchema(BaseModel):
    speaker: str
    text: str
    timestamp: Optional[float] = None

    class Config:
        from_attributes = True


class SessionStateResponse(BaseModel):
    room_name: str
    caller_name: str = ""
    reason: str = ""
    preferred_date_time: str = ""
    contact_number: str = ""
    is_booked: bool = False
    call_status: str = "connected"
    agent_state: str = "listening"
    detected_intent: str = "None"
    current_action: str = "None"
    transcript: List[TranscriptItemSchema] = []
    transfer_status: str = "idle"
    post_call_summary: str = ""
    takeover_active: bool = False

    class Config:
        from_attributes = True


class EventPayloadSchema(BaseModel):
    caller_name: Optional[str] = None
    reason: Optional[str] = None
    preferred_date_time: Optional[str] = None
    contact_number: Optional[str] = None
    is_booked: Optional[bool] = None
    call_status: Optional[str] = None
    agent_state: Optional[str] = None
    detected_intent: Optional[str] = None
    current_action: Optional[str] = None
    transcript_item: Optional[TranscriptItemSchema] = None
    transfer_status: Optional[str] = None
    post_call_summary: Optional[str] = None
    takeover_active: Optional[bool] = None


class TransferRequest(BaseModel):
    summary: str
