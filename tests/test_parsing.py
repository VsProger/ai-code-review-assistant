import json

from utils.parsing import parse_chunk_review

VALID = {
    "inline_comments": [{"file_path": "a.py", "line": 12, "comment": "handle the error"}],
    "summary": "One issue found.",
}


def test_plain_json_is_parsed():
    review = parse_chunk_review(json.dumps(VALID))
    assert review is not None
    assert review.summary == "One issue found."
    assert review.inline_comments[0].line == 12


def test_json_wrapped_in_a_markdown_fence_is_parsed():
    review = parse_chunk_review(f"```json\n{json.dumps(VALID)}\n```")
    assert review is not None
    assert review.inline_comments[0].file_path == "a.py"


def test_json_padded_with_prose_is_parsed():
    review = parse_chunk_review(f"Sure, here you go:\n{json.dumps(VALID)}\nHope that helps!")
    assert review is not None


def test_unparseable_response_returns_none():
    assert parse_chunk_review("I could not review this diff.") is None


def test_empty_response_returns_none():
    assert parse_chunk_review("") is None
    assert parse_chunk_review(None) is None


def test_malformed_comment_entries_are_dropped_not_fatal():
    payload = {"inline_comments": ["not a dict"], "summary": "ok"}
    review = parse_chunk_review(json.dumps(payload))
    assert review is not None
    assert review.inline_comments == []
