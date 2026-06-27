import logging
from typing import List, Dict
from openai import AsyncOpenAI
from app.core.config import settings

logger = logging.getLogger("summarizer-service")


class SummarizerService:
    """
    Production-grade business service wrapping OpenAI LLM summarization.
    Performs real-time, context-aware call summaries and post-call analysis.
    """

    def __init__(self):
        self._client = None
        # Always initialize client if we have OpenAI key or if using Ollama
        if settings.OPENAI_API_KEY or settings.LLM_BASE_URL:
            try:
                self._client = AsyncOpenAI(
                    api_key=settings.OPENAI_API_KEY or "ollama",
                    base_url=settings.LLM_BASE_URL,
                )
                logger.info(
                    f"LLM client initialized for summarizer service (model: {settings.LLM_MODEL})."
                )
            except Exception as e:
                logger.error(f"Failed to initialize LLM client: {e}")

    async def generate_concise_summary(self, transcript: List[Dict[str, str]]) -> str:
        """
        Generates a extremely concise 1-sentence (max 15 words) summary
        suitable for speaking to a human representative during a transfer.
        """
        if not self._client or not transcript:
            return "A caller is on the line and needs assistance."

        # Format transcript
        formatted_text = "\n".join([f"{t['speaker']}: {t['text']}" for t in transcript])

        try:
            response = await self._client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional receptionist. Summarize this conversation in exactly 1 brief, natural sentence (max 15 words) that can be spoken directly to a human agent before they take over. Focus on the main reason they are calling.",
                    },
                    {"role": "user", "content": formatted_text},
                ],
                max_tokens=60,
                temperature=0.5,
            )
            summary = response.choices[0].message.content.strip()
            logger.info(f"Generated transfer summary: {summary}")
            return summary
        except Exception as e:
            logger.error(f"Error generating transfer summary: {e}")
            return "The client has questions about booking and scheduling."

    async def generate_post_call_summary(self, transcript: List[Dict[str, str]]) -> str:
        """
        Generates a beautiful, highly detailed markdown post-call clinical summary
        incorporating Caller Details, Booking Status, and Bulleted Notes.
        """
        if not self._client or not transcript:
            return "### 📞 Call Details\n- **No conversation history recorded.**"

        formatted_text = "\n".join([f"{t['speaker']}: {t['text']}" for t in transcript])

        try:
            response = await self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a professional medical and dental assistant. Generate a highly professional, "
                            "beautifully formatted Post-Call Summary of this phone conversation in Markdown format. "
                            "Ensure it includes:\n"
                            "### 📞 Call Details\n"
                            "- **Caller Name**: (extract if mentioned, otherwise leave blank or 'Not provided')\n"
                            "- **Contact Phone**: (extract phone number)\n"
                            "- **Reason for Visit**: (extract primary complaint or symptoms)\n\n"
                            "### 📅 Booking Status\n"
                            "- **Appointment Slot**: (extract confirmed date/time or write 'Not booked')\n"
                            "- **Confirmation Code**: (extract code if booked)\n\n"
                            "### 📝 Key Highlights & Timeline\n"
                            "- (bulleted highlights including key questions asked, supervisor takeover details if applicable, or warm transfer details)\n"
                        ),
                    },
                    {"role": "user", "content": formatted_text},
                ],
                temperature=0.3,
            )
            markdown_summary = response.choices[0].message.content.strip()
            logger.info("Generated post-call clinical summary successfully.")
            return markdown_summary
        except Exception as e:
            logger.error(f"Error generating post-call summary: {e}")
            return "### 📞 Call Details\nFailed to compile clinical summary due to a backend processing error."


# Global single instance of SummarizerService
summarizer_service = SummarizerService()
