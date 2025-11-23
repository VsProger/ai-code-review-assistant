import json
from domain.services.ai_service import AIService
from utils.chunker import split_diff_into_chunks
from utils.prompts import REVIEW_INLINE_PROMPT

class ReviewService:

    def __init__(self):
        self.ai = AIService()

    def analyze(
    self,
    mr_changes,
    sha,
    mr_title: str = "",
    mr_description: str = ""
):
        changes = mr_changes.get("changes") or []
        chunks = split_diff_into_chunks(changes, max_chunk_size=2000)

        inline_comments = []
        summaries = []

        for chunk in chunks:
            user_prompt = REVIEW_INLINE_PROMPT.format(
                diff=chunk,
                title=mr_title or "",
                description=mr_description or ""
            )

            response = self.ai.review_chunk(user_prompt)

            try:
                parsed = json.loads(response)
            except:
                continue

            inline_comments.extend(parsed.get("inline_comments", []))
            summaries.append(parsed.get("summary", ""))

        final_summary = "### AI Review Summary\n" + "\n".join(summaries)

        return inline_comments, final_summary
