import pymysql
from app.core.config import settings
from app.db.session import engine, Base

# Import models to ensure they register on metadata
from app.models import Appointment, CallSession, TranscriptItem


def initialize_database():
    """
    Initializes the MySQL database.
    First connects to MySQL server, creates the schema if it does not exist,
    and then issues SQLAlchemy metadata create_all to generate database tables cleanly.
    """
    # 1. Establish raw connection to verify/create database schema
    try:
        conn = pymysql.connect(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD,
        )
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {settings.MYSQL_DB}")
            print(f"Schema check: Database '{settings.MYSQL_DB}' verified/created.")
        conn.close()
    except Exception as e:
        print(f"Raw MySQL connection failed during database initialization: {e}")
        print(
            "Application will attempt to run, but may fail if the database schema is missing."
        )
        return False

    # 2. Use SQLAlchemy metadata to declare tables
    try:
        Base.metadata.create_all(bind=engine)
        print("Database tables mapped and synchronized successfully.")
        return True
    except Exception as e:
        print(f"SQLAlchemy metadata tables creation failed: {e}")
        return False
