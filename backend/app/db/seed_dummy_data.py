import time
from datetime import datetime, timedelta
from app.db.session import SessionLocal
from app.db.init_db import initialize_database
from app.models.appointment import Appointment
from app.models.session import CallSession
from app.models.transcript import TranscriptItem


def seed_data():
    """
    Seeds the database with realistic dummy appointments, sessions, and transcripts
    to help populate the database for demonstration and testing.
    """
    print("Verifying database schema...")
    initialize_database()

    db = SessionLocal()
    try:
        # Check if database is already populated
        if db.query(Appointment).count() > 0:
            print("Database already contains seeding data. Skipping.")
            return

        print("Seeding realistic dummy data into database...")

        # 1. Seed some dummy appointments
        appointments = [
            Appointment(
                room_name="dental-clinic-session-101",
                caller_name="Sarah Jenkins",
                reason="Regular dental cleanup and polishing",
                preferred_date_time="Monday at 9:00 AM",
                contact_number="555-0143",
                confirmation_code="CONF-4821",
            ),
            Appointment(
                room_name="dental-clinic-session-102",
                caller_name="Marcus Vance",
                reason="Severe wisdom toothache in back lower left jaw",
                preferred_date_time="Wednesday at 2:30 PM",
                contact_number="555-0192",
                confirmation_code="CONF-9023",
            ),
            Appointment(
                room_name="dental-clinic-session-103",
                caller_name="Emily Zhao",
                reason="Invisalign consultation and fitting check",
                preferred_date_time="Thursday at 11:00 AM",
                contact_number="555-0155",
                confirmation_code="CONF-3829",
            ),
        ]
        db.add_all(appointments)
        print("Seeded 3 dental appointments.")

        # 2. Seed some completed call sessions
        sessions = [
            CallSession(
                room_name="dental-clinic-session-101",
                caller_name="Sarah Jenkins",
                reason="Regular dental cleanup and polishing",
                preferred_date_time="Monday at 9:00 AM",
                contact_number="555-0143",
                is_booked=True,
                call_status="ended",
                agent_state="idle",
                detected_intent="Book Appointment",
                current_action="Call ended",
                transfer_status="idle",
                takeover_active=False,
                post_call_summary=(
                    "### 📞 Call Details\n"
                    "- **Caller Name**: Sarah Jenkins\n"
                    "- **Contact Phone**: 555-0143\n"
                    "- **Reason for Visit**: Regular dental cleanup and polishing\n\n"
                    "### 📅 Booking Status\n"
                    "- **Appointment Slot**: Monday at 9:00 AM\n"
                    "- **Confirmation Code**: CONF-4821\n\n"
                    "### 📝 Key Highlights & Timeline\n"
                    "- Caller booked a routine dental checkup successfully.\n"
                    "- Appointment details were read back and confirmed.\n"
                    "- Caller expressed high satisfaction with Agent A's response speed."
                ),
            ),
            CallSession(
                room_name="dental-clinic-session-102",
                caller_name="Marcus Vance",
                reason="Severe wisdom toothache in back lower left jaw",
                preferred_date_time="Wednesday at 2:30 PM",
                contact_number="555-0192",
                is_booked=True,
                call_status="ended",
                agent_state="idle",
                detected_intent="Talk to Human",
                current_action="Call ended",
                transfer_status="accepted",
                takeover_active=True,
                post_call_summary=(
                    "### 📞 Call Details\n"
                    "- **Caller Name**: Marcus Vance\n"
                    "- **Contact Phone**: 555-0192\n"
                    "- **Reason for Visit**: Severe wisdom toothache\n\n"
                    "### 📅 Booking Status\n"
                    "- **Appointment Slot**: Wednesday at 2:30 PM (pre-booked)\n"
                    "- **Confirmation Code**: CONF-9023\n\n"
                    "### 📝 Key Highlights & Timeline\n"
                    "- Caller booked an emergency slot for severe wisdom toothache.\n"
                    "- Caller requested to speak with a human agent to discuss payment plans.\n"
                    "- Warm transfer was initiated via Twilio and accepted by the clinic receptionist.\n"
                    "- Conversation successfully bridged over phone audio."
                ),
            ),
        ]
        db.add_all(sessions)
        print("Seeded 2 call sessions.")

        # 3. Seed some transcript messages
        now = time.time()
        transcripts = [
            # Session 101 transcripts
            TranscriptItem(
                room_name="dental-clinic-session-101",
                speaker="caller",
                text="Hi! I would like to schedule my annual dental cleaning please.",
                timestamp=now - 300,
            ),
            TranscriptItem(
                room_name="dental-clinic-session-101",
                speaker="agent",
                text="Hello! I would be happy to assist you with scheduling your dental cleaning. May I start by getting your name?",
                timestamp=now - 280,
            ),
            TranscriptItem(
                room_name="dental-clinic-session-101",
                speaker="caller",
                text="My name is Sarah Jenkins.",
                timestamp=now - 260,
            ),
            TranscriptItem(
                room_name="dental-clinic-session-101",
                speaker="agent",
                text="Thank you, Sarah. What is a good contact phone number for your booking?",
                timestamp=now - 245,
            ),
            TranscriptItem(
                room_name="dental-clinic-session-101",
                speaker="caller",
                text="It is 555-0143.",
                timestamp=now - 230,
            ),
            TranscriptItem(
                room_name="dental-clinic-session-101",
                speaker="agent",
                text="Great. And do you have a preferred date and time for your cleaning?",
                timestamp=now - 215,
            ),
            TranscriptItem(
                room_name="dental-clinic-session-101",
                speaker="caller",
                text="Do you have anything open on Monday at 9:00 AM?",
                timestamp=now - 200,
            ),
            TranscriptItem(
                room_name="dental-clinic-session-101",
                speaker="agent",
                text="Let me check availability for Monday at 9:00 AM...",
                timestamp=now - 190,
            ),
            TranscriptItem(
                room_name="dental-clinic-session-101",
                speaker="agent",
                text="Yes! That slot is available. I have booked your cleaning for Monday at 9:00 AM. Your confirmation code is CONF-4821.",
                timestamp=now - 175,
            ),
            TranscriptItem(
                room_name="dental-clinic-session-101",
                speaker="caller",
                text="Wonderful, thank you so much! Goodbye.",
                timestamp=now - 160,
            ),
            # Session 102 transcripts
            TranscriptItem(
                room_name="dental-clinic-session-102",
                speaker="caller",
                text="Hi, I have a really bad toothache in my lower wisdom teeth. Can I get an emergency appointment?",
                timestamp=now - 120,
            ),
            TranscriptItem(
                room_name="dental-clinic-session-102",
                speaker="agent",
                text="Oh, I'm sorry to hear you're in pain. Let's get an emergency appointment set up. May I have your name and contact phone?",
                timestamp=now - 105,
            ),
            TranscriptItem(
                room_name="dental-clinic-session-102",
                speaker="caller",
                text="I am Marcus Vance, phone is 555-0192.",
                timestamp=now - 90,
            ),
            TranscriptItem(
                room_name="dental-clinic-session-102",
                speaker="agent",
                text="Thank you, Marcus. I have an emergency slot open this Wednesday at 2:30 PM. Shall I book that for you?",
                timestamp=now - 75,
            ),
            TranscriptItem(
                room_name="dental-clinic-session-102",
                speaker="caller",
                text="Yes please, book that. Also, I have a quick question. Do you accept financing plans for wisdom extractions?",
                timestamp=now - 60,
            ),
            TranscriptItem(
                room_name="dental-clinic-session-102",
                speaker="agent",
                text="I've confirmed your booking! For detailed financing plans, let me connect you to our clinic billing representative. Please hold on...",
                timestamp=now - 45,
            ),
            TranscriptItem(
                room_name="dental-clinic-session-102",
                speaker="watcher",
                text="Hi Marcus, this is the clinic receptionist taking over. Yes, we work with CareCredit and offer 0% interest financing plans. Let me walk you through the options...",
                timestamp=now - 20,
            ),
        ]
        db.add_all(transcripts)
        db.commit()
        print("Seeded 17 realistic transcript items.")
        print("Database successfully seeded with dummy data!")

    except Exception as e:
        print(f"Database seeding failed: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()
