from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    text as sa_text,
    ForeignKey,
    DateTime,
)
from app.db.session import Base


class TranscriptItem(Base):
    """
    SQLAlchemy model representing a single transcript message in a conversation.
    """

    __tablename__ = "transcript_items"

    id = Column(Integer, primary_key=True, index=True)
    room_name = Column(String(255), nullable=False, index=True)
    speaker = Column(String(50), nullable=False)  # caller, agent, watcher
    text = Column(String(1000), nullable=False)
    timestamp = Column(Float, nullable=False)
    created_at = Column(DateTime, server_default=sa_text("CURRENT_TIMESTAMP"))
