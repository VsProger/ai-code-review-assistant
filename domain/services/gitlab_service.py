"""Merge-request operations expressed in GitLab's API."""

import logging
from typing import Any, Dict, List, Optional

from domain.models.merge_request import DiffSHAs
from infrastructure.gitlab.gitlab_client import GitLabClient

logger = logging.getLogger(__name__)


class GitLabService:
    def __init__(self, client: GitLabClient) -> None:
        self.client = client

    def _mr_path(self, project_id: int, mr_iid: int) -> str:
        return f"/projects/{project_id}/merge_requests/{mr_iid}"

    async def get_merge_request(self, project_id: int, mr_iid: int) -> Dict[str, Any]:
        return await self.client.get(self._mr_path(project_id, mr_iid))

    async def get_merge_request_changes(self, project_id: int, mr_iid: int) -> Dict[str, Any]:
        """Returns an object whose 'changes' key holds the per-file diffs."""
        return await self.client.get(f"{self._mr_path(project_id, mr_iid)}/changes")

    async def post_summary_comment(self, project_id: int, mr_iid: int,
                                   body: str) -> Optional[Dict[str, Any]]:
        return await self.client.post(
            f"{self._mr_path(project_id, mr_iid)}/discussions", {"body": body}
        )

    async def post_inline_comment(self, project_id: int, mr_iid: int, file_path: str,
                                  line_number: int, body: str,
                                  sha: DiffSHAs) -> Optional[Dict[str, Any]]:
        """
        Anchor a comment to one line of the diff.

        GitLab answers 400 when the position does not resolve to a line of the
        diff -- a line the model invented, or a line in an unchanged region.
        That is expected often enough that it is tolerated rather than raised.
        """
        if not sha.complete:
            logger.warning("Skipping inline comment: incomplete SHAs for MR !%s", mr_iid)
            return None
        if not isinstance(line_number, int) or line_number < 1:
            logger.warning("Skipping inline comment: invalid line %r", line_number)
            return None

        payload = {
            "body": body,
            "position": {
                "position_type": "text",
                "base_sha": sha.base_sha,
                "start_sha": sha.start_sha,
                "head_sha": sha.head_sha,
                "new_path": file_path,
                "new_line": line_number,
            },
        }
        return await self.client.post(
            f"{self._mr_path(project_id, mr_iid)}/discussions", payload, tolerate=(400, 404)
        )

    async def add_label(self, project_id: int, mr_iid: int, label: str) -> Dict[str, Any]:
        """Add a label without dropping the ones already set."""
        mr = await self.get_merge_request(project_id, mr_iid)
        existing: List[str] = mr.get("labels") or []
        if label in existing:
            return mr
        return await self.client.put(
            self._mr_path(project_id, mr_iid), {"labels": ",".join(existing + [label])}
        )
