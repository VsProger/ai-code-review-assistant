"""
Async HTTP client for the GitLab REST API.

Holds one connection pool for the lifetime of the client and knows nothing
about reviews -- it only speaks GitLab.
"""

import logging
from typing import Any, Dict, Optional, Tuple

import httpx

from core.config import settings

logger = logging.getLogger(__name__)


class GitLabClient:
    def __init__(self, timeout: float = 30.0) -> None:
        self.base_url = settings.gitlab_base_url.rstrip("/")
        self.headers = {"PRIVATE-TOKEN": settings.gitlab_token}
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "GitLabClient":
        self._client = httpx.AsyncClient(timeout=self.timeout, headers=self.headers)
        return self

    async def __aexit__(self, *exc_info) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("GitLabClient must be used as an async context manager")
        return self._client

    def url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    async def get(self, path: str) -> Dict[str, Any]:
        resp = await self.client.get(self.url(path))
        resp.raise_for_status()
        return resp.json()

    async def post(self, path: str, json: Dict[str, Any],
                   tolerate: Tuple[int, ...] = ()) -> Optional[Dict[str, Any]]:
        """POST, returning None for status codes listed in `tolerate`."""
        resp = await self.client.post(self.url(path), json=json)
        if resp.status_code in tolerate:
            logger.warning("GitLab rejected POST %s with %s: %s",
                           path, resp.status_code, resp.text[:300])
            return None
        resp.raise_for_status()
        return resp.json()

    async def put(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        resp = await self.client.put(self.url(path), data=data)
        resp.raise_for_status()
        return resp.json()
