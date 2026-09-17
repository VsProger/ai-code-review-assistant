"""Orchestrates a merge-request review: chunk, prompt, parse, assemble."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from domain.models.merge_request import InlineComment
from domain.services.ai_service import AIService
from utils.chunker import split_diff_into_chunks
from utils.parsing import parse_chunk_review
from utils.prompts import REVIEW_INLINE_PROMPT

logger = logging.getLogger(__name__)

MAX_CHUNK_SIZE = 2000
MAX_CONCURRENT_CHUNKS = 4


@dataclass
class ReviewResult:
    inline_comments: List[InlineComment] = field(default_factory=list)
    summary: str = ""
    chunks_total: int = 0
    chunks_failed: int = 0
    duplicates_dropped: int = 0


def _dedupe(comments: List[InlineComment]) -> Tuple[List[InlineComment], int]:
    """
    Collapse findings that repeat across chunks.

    A file touched by several hunks lands in more than one chunk, so the same
    issue comes back more than once; posting each copy would spam the MR.
    """
    seen: Dict[Tuple, InlineComment] = {}
    dropped = 0
    for comment in comments:
        key = (comment.file_path, comment.line, comment.comment.strip().lower())
        if key in seen:
            dropped += 1
            continue
        seen[key] = comment
    return list(seen.values()), dropped


class ReviewService:
    def __init__(self, ai: Optional[AIService] = None) -> None:
        self.ai = ai or AIService()

    async def analyze(self, mr_changes: dict, mr_title: str = "",
                      mr_description: str = "") -> ReviewResult:
        changes = mr_changes.get("changes") or []
        chunks = split_diff_into_chunks(changes, max_chunk_size=MAX_CHUNK_SIZE)
        result = ReviewResult(chunks_total=len(chunks))

        if not chunks:
            result.summary = "### AI Review Summary\n\nNo reviewable changes found."
            return result

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHUNKS)

        async def review_one(chunk: str):
            async with semaphore:
                prompt = REVIEW_INLINE_PROMPT.format(
                    diff=chunk, title=mr_title or "-", description=mr_description or "-"
                )
                return parse_chunk_review(await self.ai.review_chunk(prompt))

        reviews = await asyncio.gather(
            *(review_one(chunk) for chunk in chunks), return_exceptions=True
        )

        summaries: List[str] = []
        comments: List[InlineComment] = []
        for review in reviews:
            if isinstance(review, Exception):
                logger.warning("Chunk review raised: %s", review)
                result.chunks_failed += 1
                continue
            if review is None:
                result.chunks_failed += 1
                continue
            comments.extend(review.inline_comments)
            if review.summary:
                summaries.append(review.summary)

        result.inline_comments, result.duplicates_dropped = _dedupe(comments)
        result.summary = self._render_summary(result, summaries)
        return result

    @staticmethod
    def _render_summary(result: ReviewResult, summaries: List[str]) -> str:
        lines = ["### AI Review Summary", ""]
        lines.extend(summaries or ["No issues reported for the reviewed chunks."])
        reviewed = result.chunks_total - result.chunks_failed
        lines += ["", f"_Reviewed {reviewed}/{result.chunks_total} diff chunks; "
                      f"{len(result.inline_comments)} inline comments._"]
        if result.chunks_failed:
            # Stated rather than hidden: a silently dropped chunk is an
            # unreviewed chunk, and the reader needs to know coverage was partial.
            lines.append(f"_{result.chunks_failed} chunk(s) could not be reviewed._")
        return "\n".join(lines)
