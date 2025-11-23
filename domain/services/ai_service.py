import httpx
import logging

from core.config import settings
from utils.prompts import REVIEW_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class AIService:
    """
    Сервис для общения с LLM (OpenAI или другой провайдер).
    Сейчас — простой HTTP-клиент к OpenAI Chat Completions API.
    """

    def __init__(self):
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model

    def review_chunk(self, user_prompt: str) -> str:
        """
        Отправляет один чанк diff + контекст в LLM и возвращает текст ответа.
        """

        if not self.api_key:
            logger.warning("OPENAI_API_KEY not configured, returning stub text.")
            return "AI is not configured (missing OPENAI_API_KEY)."

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }

        with httpx.Client(timeout=60) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        return content.strip() if content else "AI did not return any content."
