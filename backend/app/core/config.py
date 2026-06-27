import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App Settings
    PROJECT_NAME: str = "OpenVoice AI Agent Platform"
    API_V1_STR: str = "/api/v1"

    # Environment config
    model_config = SettingsConfigDict(
        env_file=os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LiveKit API Configuration
    LIVEKIT_URL: str
    LIVEKIT_API_KEY: str
    LIVEKIT_API_SECRET: str

    # LLM & STT/TTS Providers
    OPENAI_API_KEY: Optional[str] = ""
    DEEPGRAM_API_KEY: str

    # Custom LLM / Ollama configuration
    LLM_BASE_URL: Optional[str] = None  # Set to http://localhost:11434/v1 for Ollama
    LLM_MODEL: str = "gpt-4o-mini"  # Set to llama3, mistral, etc., for Ollama

    # Twilio API Credentials
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    HUMAN_AGENT_PHONE_NUMBER: str = ""

    # Connection URLs
    PUBLIC_BACKEND_URL: str = "http://localhost:8000"
    BACKEND_URL: str = "http://localhost:8000"

    # MySQL Database Connection (SQLAlchemy format)
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "254131"
    MYSQL_DB: str = "dental_clinic"

    @property
    def DATABASE_URL(self) -> str:
        """
        Generates the SQLAlchemy compatible database connection URL.
        """
        return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"


# Global instance of settings
settings = Settings()
