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
        
        
    def post_inline_comment(
        self,
        project_id: int,
        mr_iid: int,
        file_path: str,
        line_number: int,
        body: str,
        sha: dict
    ):
        """
        Создаёт inline-комментарий для ДЕЙСТВИТЕЛЬНО существующих строк.
        Игнорирует некорректные случаи, чтобы не ломать приложение.
        """

        # SHA должны существовать
        if not sha.get("base_sha") or not sha.get("start_sha") or not sha.get("head_sha"):
            print("⚠️ SKIP inline comment — missing SHA:", sha)
            return None

        # line_number должен быть >= 1
        if not isinstance(line_number, int) or line_number < 1:
            print("⚠️ SKIP inline comment — invalid line:", line_number)
            return None

        url = f"{self.base_url}/projects/{project_id}/merge_requests/{mr_iid}/discussions"

        payload = {
            "body": body,
            "position": {
                "base_sha": sha["base_sha"],
                "start_sha": sha["start_sha"],
                "head_sha": sha["head_sha"],
                "new_path": file_path,
                "new_line": line_number
            }
        }

        print("INLINE PAYLOAD:", payload)

        with httpx.Client(timeout=20) as client:
            resp = client.post(url, headers=self.headers, json=payload)

            # Если GitLab всё ещё отвечает 400 → не ломаем приложение
            if resp.status_code == 400:
                print("❌ GitLab rejected inline comment:", resp.text)
                return None

            resp.raise_for_status()
            return resp.json()
