"""
Async HTTP client for the OpenAI Chat Completions API.

This is the only module that knows the provider's wire format. Swapping vendors
means writing another client with the same `complete_json` signature.
"""

import asyncio
import logging
from typing import Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

API_URL = "https://api.openai.com/v1/chat/completions"
MAX_ATTEMPTS = 3
RETRY_STATUS = {429, 500, 502, 503, 504}


class OpenAIClient:
    def __init__(self, timeout: float = 60.0) -> None:
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.timeout = timeout

    async def complete_json(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """
        Ask the model for a single JSON object.

        `response_format=json_object` makes the provider enforce syntactically
        valid JSON, which removes the most common cause of a dropped chunk.
        Returns None when the call could not be completed.
        """
        if not self.api_key:
            logger.warning("OPENAI_API_KEY is not configured; skipping AI call")
            return None

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    resp = await client.post(API_URL, headers=headers, json=payload)
                except httpx.RequestError as exc:
                    logger.warning("OpenAI request failed (attempt %s/%s): %s",
                                   attempt, MAX_ATTEMPTS, exc)
                else:
                    if resp.status_code not in RETRY_STATUS:
                        resp.raise_for_status()
                        data = resp.json()
                        choices = data.get("choices") or [{}]
                        content = (choices[0].get("message") or {}).get("content") or ""
                        return content.strip() or None
                    logger.warning("OpenAI returned %s (attempt %s/%s)",
                                   resp.status_code, attempt, MAX_ATTEMPTS)

                if attempt < MAX_ATTEMPTS:
                    await asyncio.sleep(2 ** (attempt - 1))  # 1s, 2s

        logger.error("OpenAI call gave up after %s attempts", MAX_ATTEMPTS)
        return None
