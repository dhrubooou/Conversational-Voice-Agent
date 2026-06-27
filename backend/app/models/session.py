from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Text,
    text as sa_text,
    func,
)
from app.db.session import Base


class CallSession(Base):
    """
    SQLAlchemy model representing a real-time call session state.
    """

    __tablename__ = "call_sessions"

    id = Column(Integer, primary_key=True, index=True)
    room_name = Column(String(255), nullable=False, unique=True, index=True)
    caller_name = Column(String(255), default="")
    reason = Column(String(500), default="")
    preferred_date_time = Column(String(255), default="")
    contact_number = Column(String(50), default="")
    is_booked = Column(Boolean, default=False)
    call_status = Column(
        String(100), default="connected"
    )  # connected -> transferring -> ended
    agent_state = Column(
        String(100), default="listening"
    )  # listening -> thinking -> speaking -> monitoring
    detected_intent = Column(String(255), default="None")
    current_action = Column(String(255), default="None")
    transfer_status = Column(
        String(100), default="idle"
    )  # idle -> calling -> accepted -> declined
    post_call_summary = Column(Text, nullable=True)
    takeover_active = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=sa_text("CURRENT_TIMESTAMP"))
    updated_at = Column(
        DateTime, server_default=sa_text("CURRENT_TIMESTAMP"), onupdate=func.now()
    )
