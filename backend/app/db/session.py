from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# Create engine with pool_pre_ping enabled to auto-reconnect on socket drops
engine = create_engine(
    settings.DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    Dependency helper that yields a thread-safe database session
    and closes it when the request is complete.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
