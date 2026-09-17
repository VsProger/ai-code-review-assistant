"""
Provider-agnostic review interface.

The review logic depends on this class, not on any vendor SDK, so replacing the
provider means passing a different client in.
"""

import logging
from typing import Optional

from infrastructure.ai.openai_client import OpenAIClient
from utils.prompts import REVIEW_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self, client=None) -> None:
        self.client = client or OpenAIClient()

    async def review_chunk(self, user_prompt: str) -> Optional[str]:
        """Return the raw JSON string for one diff chunk, or None on failure."""
        return await self.client.complete_json(REVIEW_SYSTEM_PROMPT, user_prompt)
