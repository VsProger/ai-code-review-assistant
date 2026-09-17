import json

from domain.services.review_service import ReviewService


class FakeAI:
    """Replays canned completions in order, so no network or key is needed."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    async def review_chunk(self, prompt):
        self.prompts.append(prompt)
        return self.responses.pop(0) if self.responses else None


def review(file_path="a.py", line=1, comment="fix it", summary="s"):
    return json.dumps({
        "inline_comments": [{"file_path": file_path, "line": line, "comment": comment}],
        "summary": summary,
    })


def changes(n):
    return {"changes": [
        {"new_path": f"f{i}.py", "diff": "x" * 1500} for i in range(n)
    ]}


async def test_duplicate_findings_are_collapsed():
    ai = FakeAI([review(), review(), review()])
    result = await ReviewService(ai=ai).analyze(changes(3))
    assert len(result.inline_comments) == 1
    assert result.duplicates_dropped == 2


async def test_distinct_findings_are_all_kept():
    ai = FakeAI([review(line=1), review(line=2), review(line=3)])
    result = await ReviewService(ai=ai).analyze(changes(3))
    assert len(result.inline_comments) == 3
    assert result.duplicates_dropped == 0


async def test_unparseable_chunk_is_counted_not_fatal():
    ai = FakeAI([review(line=1), "not json at all", review(line=2)])
    result = await ReviewService(ai=ai).analyze(changes(3))
    assert result.chunks_failed == 1
    assert len(result.inline_comments) == 2
    assert "could not be reviewed" in result.summary


async def test_partial_coverage_is_stated_in_the_summary():
    ai = FakeAI([None, None, None])
    result = await ReviewService(ai=ai).analyze(changes(3))
    assert result.chunks_failed == 3
    assert "Reviewed 0/3" in result.summary


async def test_mr_title_and_description_reach_the_model():
    ai = FakeAI([review()])
    await ReviewService(ai=ai).analyze(changes(1), mr_title="Add retry", mr_description="Why")
    assert "Add retry" in ai.prompts[0]
    assert "Why" in ai.prompts[0]


async def test_no_changes_produces_a_summary_and_no_comments():
    ai = FakeAI([])
    result = await ReviewService(ai=ai).analyze({"changes": []})
    assert result.inline_comments == []
    assert "No reviewable changes" in result.summary
