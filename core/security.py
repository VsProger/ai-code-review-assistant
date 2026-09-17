"""Webhook authentication."""

import hmac
from typing import Optional

from core.config import settings


def verify_gitlab_token(received: Optional[str]) -> bool:
    """
    Check the X-Gitlab-Token header against the configured secret.

    Uses a constant-time comparison: a plain `!=` leaks the length of the
    matching prefix through timing, which is enough to recover a secret one
    character at a time.
    """
    if not received or not settings.gitlab_secret:
        return False
    return hmac.compare_digest(received, settings.gitlab_secret)
