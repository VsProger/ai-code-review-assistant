"""Turning a model completion into structured findings."""

import json
import logging
import re
from typing import Optional

from domain.models.merge_request import ChunkReview

logger = logging.getLogger(__name__)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def parse_chunk_review(raw: Optional[str]) -> Optional[ChunkReview]:
    """
    Parse one model response.

    Tolerates a JSON object wrapped in a markdown fence or padded with prose,
    which models still emit occasionally even in JSON mode. Returns None when
    nothing parseable is found, so the caller can count the failure.
    """
    if not raw:
        return None

    candidates = [raw]
    fenced = _FENCE.search(raw)
    if fenced:
        candidates.insert(0, fenced.group(1))
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        candidates.append(raw[start:end + 1])

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        try:
            return ChunkReview.model_validate(
                {
                    "inline_comments": [
                        c for c in (data.get("inline_comments") or [])
                        if isinstance(c, dict)
                    ],
                    "summary": data.get("summary") or "",
                }
            )
        except Exception as exc:  # noqa: BLE001 - malformed field types
            logger.debug("Chunk review failed validation: %s", exc)
            continue

    logger.warning("Could not parse a review object from the model response")
    return None
