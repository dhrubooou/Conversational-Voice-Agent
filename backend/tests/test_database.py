import pytest
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import Base
from app.models.appointment import Appointment
from app.models.session import CallSession
from app.models.transcript import TranscriptItem
from app.schemas.session import EventPayloadSchema, TranscriptItemSchema
from app.services.database_service import (
    get_or_create_session,
    update_session,
    check_db_slot_availability,
    book_db_appointment,
    get_session_transcript,
)

# Use SQLite in-memory database for fast, isolated, self-contained testing
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(name="db_session")
def db_session_fixture():
    """
    Fixture that initializes an in-memory SQLite database,
    creates the schema, yields a session, and cleans up after tests.
    """
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create the tables
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_get_or_create_session(db_session):
    """
    Tests that a call session is created on demand if it does not exist.
    """
    room_name = "test-room-1"

    # Ensure it doesn't exist initially
    count = (
        db_session.query(CallSession).filter(CallSession.room_name == room_name).count()
    )
    assert count == 0

    # Create session
    session = get_or_create_session(db_session, room_name)
    assert session.room_name == room_name
    assert session.call_status == "connected"

    # Ensure it now exists in DB
    count = (
        db_session.query(CallSession).filter(CallSession.room_name == room_name).count()
    )
    assert count == 1


def test_update_session_with_transcript(db_session):
    """
    Tests that updating a session merges event data and saves transcript items.
    """
    room_name = "test-room-2"
    get_or_create_session(db_session, room_name)

    # Update state and append transcript item
    payload = EventPayloadSchema(
        caller_name="Alice Smith",
        agent_state="speaking",
        detected_intent="Greeting",
        transcript_item=TranscriptItemSchema(
            speaker="caller", text="Hello there!", timestamp=123.45
        ),
    )

    session = update_session(db_session, room_name, payload)

    assert session.caller_name == "Alice Smith"
    assert session.agent_state == "speaking"
    assert session.detected_intent == "Greeting"

    # Check that transcript was saved
    records = (
        db_session.query(TranscriptItem)
        .filter(TranscriptItem.room_name == room_name)
        .all()
    )
    assert len(records) == 1
    assert records[0].speaker == "caller"
    assert records[0].text == "Hello there!"
    assert records[0].timestamp == 123.45


def test_booking_slot_availability(db_session):
    """
    Tests that slot availability checks identify taken and open times correctly.
    """
    room_name = "test-room-3"
    date_time = "Friday at 10 AM"

    # Slot is open initially
    assert check_db_slot_availability(db_session, date_time) is True

    # Book the slot
    book_db_appointment(
        db=db_session,
        room_name=room_name,
        caller_name="Bob Jones",
        reason="Teeth Cleaning",
        preferred_date_time=date_time,
        contact_number="555-9876",
        confirmation_code="CONF-1234",
    )

    # Slot should now be unavailable
    assert check_db_slot_availability(db_session, date_time) is False

    # Bookings table should have 1 record
    count = db_session.query(Appointment).count()
    assert count == 1
