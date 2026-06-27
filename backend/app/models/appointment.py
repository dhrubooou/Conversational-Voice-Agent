from sqlalchemy import Column, Integer, String, DateTime, text as sa_text
from app.db.session import Base


class Appointment(Base):
    """
    SQLAlchemy model representing an appointment booking.
    """

    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    room_name = Column(String(255), nullable=False)
    caller_name = Column(String(255), nullable=False)
    reason = Column(String(500), nullable=True)
    preferred_date_time = Column(String(255), nullable=False, index=True)
    contact_number = Column(String(50), nullable=False)
    confirmation_code = Column(String(50), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, server_default=sa_text("CURRENT_TIMESTAMP"))
