from fastapi import APIRouter, Request, Header, HTTPException, status
import logging

from core.config import settings
from domain.services.gitlab_service import GitLabService
from domain.services.review_service import ReviewService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/webhook", status_code=200)
async def gitlab_webhook(
    request: Request,
    x_gitlab_token: str = Header(None),
    x_gitlab_event: str = Header(None),
):
    """
    Основной Webhook:
    - принимает событие из GitLab
    - фильтрует лишние
    - вызывает AI review
    - оставляет inline комментарии
    - пишет короткий summary
    """

    # 1. Проверка секретного токена
    if x_gitlab_token != settings.gitlab_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid GitLab token"
        )

    # 2. Чтение payload
    payload = await request.json()

    # === Защита от бесконечного цикла ===
    # Обрабатываем только Merge Request Hook
    if "Merge Request" not in (x_gitlab_event or ""):
        return {"status": "ignored", "reason": f"unsupported event {x_gitlab_event}"}

    logger.info(f"Webhook received: {x_gitlab_event}")

    project = payload.get("project", {})
    object_attrs = payload.get("object_attributes", {})
    user = payload.get("user", {})

    project_id = project.get("id")
    mr_iid = object_attrs.get("iid")


    action = object_attrs.get("action")
    if action in ("close", "closed", "merge", "merged"):
        return {"status": "ignored", "reason": f"MR action={action}"}   

    # Защищаем от циклов: если коммент оставил бот → игнорируем
    if user.get("id") == getattr(settings, "gitlab_bot_user_id", None):
        return {"status": "ignored", "reason": "bot triggered event"}

    if not project_id or not mr_iid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing project_id or merge_request_iid"
        )

    mr_title = object_attrs.get("title", "")
    mr_description = object_attrs.get("description", "")

    # SHA — обязательны для inline комментариев
    sha_info = {
        "base_sha": object_attrs.get("base_sha"),
        "start_sha": object_attrs.get("start_sha"),
        "head_sha": object_attrs.get("head_sha"),
    }

    # 3. Инициализация сервисов
    gitlab = GitLabService()
    review_service = ReviewService()

    # 4. Получаем diff MR
    mr_changes = gitlab.get_merge_request_changes(project_id, mr_iid)

    # 5. Генерируем AI обратную связь (inline + summary)
    inline_comments, summary_text = review_service.analyze(
        mr_changes=mr_changes,
        sha=sha_info,
        mr_title=mr_title,
        mr_description=mr_description,
    )

    # 6. Публикуем inline комментарии
    for comment in inline_comments:
        gitlab.post_inline_comment(
            project_id=project_id,
            mr_iid=mr_iid,
            file_path=comment["file_path"],
            line_number=comment["line"],
            body=comment["comment"],
            sha=sha_info
        )


    # 7. Публикуем общий summary
    gitlab.post_summary_comment(
        project_id=project_id,
        mr_iid=mr_iid,
        body=summary_text
    )

    # 8. Добавляем label
    gitlab.add_label(project_id, mr_iid, "ai-reviewed")

    return {"status": "ok", "inline_comments": len(inline_comments)}
