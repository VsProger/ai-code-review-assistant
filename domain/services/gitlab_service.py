import httpx
from typing import Any, Dict, List

from core.config import settings


class GitLabService:
    def __init__(self):
        self.base_url = settings.gitlab_base_url.rstrip("/")
        self.headers = {
            "PRIVATE-TOKEN": settings.gitlab_token,
        }

    def get_merge_request(self, project_id: int, mr_iid: int) -> Dict[str, Any]:
        url = f"{self.base_url}/projects/{project_id}/merge_requests/{mr_iid}"
        with httpx.Client(timeout=15) as client:
            resp = client.get(url, headers=self.headers)
            resp.raise_for_status()
            return resp.json()

    def get_merge_request_changes(self, project_id: int, mr_iid: int) -> Dict[str, Any]:
        """
        Возвращает объект с ключом 'changes' — список изменений файлов.
        """
        url = f"{self.base_url}/projects/{project_id}/merge_requests/{mr_iid}/changes"
        with httpx.Client(timeout=30) as client:
            resp = client.get(url, headers=self.headers)
            resp.raise_for_status()
            return resp.json()

    def post_summary_comment(self, project_id: int, mr_iid: int, body: str) -> Dict[str, Any]:
        """
        Создаёт обсуждение (discussion) с одним комментарием в MR.
        """
        url = f"{self.base_url}/projects/{project_id}/merge_requests/{mr_iid}/discussions"
        payload = {
            "body": body,
        }
        with httpx.Client(timeout=15) as client:
            resp = client.post(url, headers=self.headers, json=payload)
            resp.raise_for_status()
            return resp.json()

    def add_label(self, project_id: int, mr_iid: int, label: str) -> Dict[str, Any]:
        """
        Добавляет label к MR, не теряя существующие.
        """
        mr = self.get_merge_request(project_id, mr_iid)
        existing_labels: List[str] = mr.get("labels") or []

        if label in existing_labels:
            return mr  # уже есть, ничего не делаем

        new_labels = existing_labels + [label]
        labels_str = ",".join(new_labels)

        url = f"{self.base_url}/projects/{project_id}/merge_requests/{mr_iid}"
        data = {
            "labels": labels_str,
        }
        with httpx.Client(timeout=15) as client:
            resp = client.put(url, headers=self.headers, data=data)
            resp.raise_for_status()
            return resp.json()
    
    def post_inline_comment(self, project_id, mr_iid, file_path, line, body, sha):
        url = f"{self.base_url}/projects/{project_id}/merge_requests/{mr_iid}/discussions"
        payload = {
            "body": body,
            "position": {
                "base_sha": sha["base_sha"],
                "start_sha": sha["start_sha"],
                "head_sha": sha["head_sha"],
                "new_path": file_path,
                "new_line": line
            }
        }

        with httpx.Client(timeout=20) as client:
            resp = client.post(url, headers=self.headers, json=payload)
            resp.raise_for_status()
