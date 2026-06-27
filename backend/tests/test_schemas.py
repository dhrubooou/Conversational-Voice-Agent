import pytest
from app.schemas.session import EventPayloadSchema, TranscriptItemSchema
from app.schemas.appointment import AppointmentCreate


def test_transcript_item_schema():
    """
    Tests that the TranscriptItemSchema correctly validates speaker and text input.
    """
    payload = {
        "speaker": "caller",
        "text": "Hello, I want to book an appointment.",
        "timestamp": 12345.67,
    }
    schema = TranscriptItemSchema(**payload)
    assert schema.speaker == "caller"
    assert schema.text == "Hello, I want to book an appointment."
    assert schema.timestamp == 12345.67


def test_event_payload_schema():
    """
    Tests that the EventPayloadSchema merges optional fields correctly.
    """
    payload = {
        "caller_name": "John Doe",
        "agent_state": "thinking",
        "transcript_item": {"speaker": "agent", "text": "Let me check availability."},
    }
    schema = EventPayloadSchema(**payload)
    assert schema.caller_name == "John Doe"
    assert schema.agent_state == "thinking"
    assert schema.transcript_item.speaker == "agent"
    assert schema.transcript_item.text == "Let me check availability."
    assert schema.is_booked is None  # Check that optional fields default to None


def test_appointment_create_schema():
    """
    Tests that the AppointmentCreate schema validates required parameters correctly.
    """
    payload = {
        "caller_name": "Alice Smith",
        "reason": "Teeth whitening",
        "preferred_date_time": "Tuesday at 2 PM",
        "contact_number": "555-1234",
        "room_name": "dental-room-1",
    }
    schema = AppointmentCreate(**payload)
    assert schema.caller_name == "Alice Smith"
    assert schema.reason == "Teeth whitening"
    assert schema.preferred_date_time == "Tuesday at 2 PM"
    assert schema.contact_number == "555-1234"
    assert schema.room_name == "dental-room-1"
