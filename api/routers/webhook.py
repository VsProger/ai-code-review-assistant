"""GitLab webhook endpoint."""

import logging

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status

from core.config import settings
from core.security import verify_gitlab_token
from domain.models.merge_request import MergeRequestEvent
from domain.services.gitlab_service import GitLabService
from domain.services.review_service import ReviewService
from infrastructure.gitlab.gitlab_client import GitLabClient

router = APIRouter()
logger = logging.getLogger(__name__)

IGNORED_ACTIONS = {"close", "closed", "merge", "merged"}
REVIEWED_LABEL = "ai-reviewed"


async def run_review(event: MergeRequestEvent) -> None:
    """
    Perform the review and publish it.

    Runs as a background task: a full review is many model calls and takes far
    longer than GitLab's webhook timeout, so the endpoint answers first and
    this runs afterwards. Exceptions are contained here -- an unhandled one in
    a background task would otherwise vanish without a trace.
    """
    try:
        async with GitLabClient() as client:
            gitlab = GitLabService(client)
            changes = await gitlab.get_merge_request_changes(event.project_id, event.mr_iid)

            result = await ReviewService().analyze(
                mr_changes=changes,
                mr_title=event.title,
                mr_description=event.description,
            )

            posted = 0
            for comment in result.inline_comments:
                response = await gitlab.post_inline_comment(
                    project_id=event.project_id,
                    mr_iid=event.mr_iid,
                    file_path=comment.file_path,
                    line_number=comment.line,
                    body=comment.comment,
                    sha=event.sha,
                )
                posted += response is not None

            await gitlab.post_summary_comment(event.project_id, event.mr_iid, result.summary)
            await gitlab.add_label(event.project_id, event.mr_iid, REVIEWED_LABEL)

            logger.info(
                "Reviewed MR !%s in project %s: %s/%s chunks, %s inline comments posted "
                "(%s rejected by GitLab, %s duplicates dropped)",
                event.mr_iid, event.project_id,
                result.chunks_total - result.chunks_failed, result.chunks_total,
                posted, len(result.inline_comments) - posted, result.duplicates_dropped,
            )
    except Exception:
        logger.exception("Review failed for MR !%s in project %s",
                         event.mr_iid, event.project_id)


@router.post("/webhook", status_code=status.HTTP_202_ACCEPTED)
async def gitlab_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_gitlab_token: str = Header(None),
    x_gitlab_event: str = Header(None),
):
    """Accept a Merge Request Hook and schedule the review."""
    if not verify_gitlab_token(x_gitlab_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid GitLab token")

    if "Merge Request" not in (x_gitlab_event or ""):
        return {"status": "ignored", "reason": f"unsupported event {x_gitlab_event}"}

    payload = await request.json()
    event = MergeRequestEvent.from_payload(payload)

    if event.action in IGNORED_ACTIONS:
        return {"status": "ignored", "reason": f"MR action={event.action}"}

    # The bot's own summary comment would otherwise retrigger this webhook.
    if settings.gitlab_bot_user_id is not None and event.author_id == settings.gitlab_bot_user_id:
        return {"status": "ignored", "reason": "bot triggered event"}

    if not event.project_id or not event.mr_iid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Missing project_id or merge_request_iid")

    background_tasks.add_task(run_review, event)
    logger.info("Scheduled review for MR !%s in project %s", event.mr_iid, event.project_id)
    return {"status": "accepted", "merge_request_iid": event.mr_iid}
