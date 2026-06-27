import time
from app.core.config import settings
from twilio.rest import Client


class TwilioService:
    """
    Production-grade business service wrapping Twilio APIs.
    Includes robust error boundaries, logging, and exponential backoff retry policies.
    """

    def __init__(self):
        self._client = None
        self._init_client()

    def _init_client(self):
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            try:
                self._client = Client(
                    settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN
                )
                print("✅ Twilio REST API Client initialized.")
            except Exception as e:
                print(f"❌ Failed to initialize Twilio Client: {e}")

    def make_outbound_call(self, room_name: str, summary: str) -> bool:
        """
        Dials the human agent's phone number via Twilio REST API.
        Implements an exponential backoff policy for handling transient connection errors.
        """
        if (
            not self._client
            or not settings.TWILIO_PHONE_NUMBER
            or not settings.HUMAN_AGENT_PHONE_NUMBER
        ):
            print(
                "⚠️ Twilio credentials or telephone numbers are missing from configurations. Outbound call skipped."
            )
            return False

        max_retries = 3
        backoff_factor = 2  # Exponent factor

        for attempt in range(max_retries):
            try:
                print(
                    f"📞 Attempting outbound call to {settings.HUMAN_AGENT_PHONE_NUMBER} (Attempt {attempt + 1}/{max_retries})..."
                )

                call = self._client.calls.create(
                    to=settings.HUMAN_AGENT_PHONE_NUMBER,
                    from_=settings.TWILIO_PHONE_NUMBER,
                    url=f"{settings.PUBLIC_BACKEND_URL}/api/v1/twilio/welcome/{room_name}",
                )

                print(f"✅ Call placed successfully. Twilio CallSid: {call.sid}")
                return True
            except Exception as e:
                print(f"⚠️ Twilio API Outbound Call attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    sleep_time = backoff_factor**attempt
                    print(
                        f"⏱️ Retrying in {sleep_time} seconds (exponential backoff)..."
                    )
                    time.sleep(sleep_time)
                else:
                    print("❌ Max Twilio call retries reached. Warm transfer failed.")
                    return False
        return False


# Global single instance of TwilioService
twilio_service = TwilioService()
