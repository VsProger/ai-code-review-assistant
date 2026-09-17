# AI Code Review Assistant

A FastAPI service that reviews GitLab merge requests with an LLM: it receives the MR webhook, fetches the diff, asks the model for structured findings, and posts them back as inline comments anchored to the changed lines, plus a summary.

## Overview

Review backlog is the usual bottleneck in a team: mechanical issues — an unhandled error path, a missing validation, a naming inconsistency — consume senior reviewers' attention before anyone looks at the design. This service takes the mechanical pass, so a human reviewer opens the MR with the obvious problems already annotated.

It is a bot with write access to merge requests, so the design is shaped mostly by the ways that can go wrong: a webhook that anyone can call, diffs larger than the model's context, model output that is not valid JSON, and a bot whose own comments retrigger it.

## Technical Approach

**Webhook hardening.** Every request is checked against the shared `X-Gitlab-Token` secret and rejected with 403 on mismatch. Only `Merge Request` events proceed; `close` and `merge` actions are dropped, as are events attributed to the bot's own user id — without that last check the bot's summary comment would retrigger the webhook and loop.

**Diff chunking.** `split_diff_into_chunks` packs per-file diffs into chunks under a character budget, keeping each file's `File: <path>` header attached to its hunks so the model always knows which file it is reading. Files are never split mid-block unless a single file exceeds the budget, so the model does not receive orphaned hunks.

**Structured model output.** The prompt asks for JSON containing `inline_comments` (each with file path, line and comment) and a `summary`. Parsing is guarded: a chunk whose response is not valid JSON is skipped rather than allowed to abort the review, so one bad completion costs one chunk instead of the whole MR.

**Inline anchoring.** GitLab requires `base_sha`, `start_sha` and `head_sha` to attach a comment to a specific line of a diff. These are taken from the webhook payload and passed through to the discussions API, which is what makes the output inline review rather than a wall of text. Reviewed MRs are labelled `ai-reviewed`.

**Layering.** `api/` handles HTTP, `domain/services/` holds review orchestration and GitLab operations, `infrastructure/` wraps the OpenAI and GitLab clients, and `utils/` holds chunking and prompts. The review logic depends on an AI service interface rather than on the OpenAI client directly, so the provider is replaceable.

## Technologies

Python · FastAPI · Uvicorn · httpx · Pydantic / pydantic-settings · OpenAI API · GitLab REST API (webhooks, merge request changes, discussions)

## Architecture

```
GitLab MR event
      │  POST /webhook  (X-Gitlab-Token, X-Gitlab-Event)
      ▼
api/routers/webhook.py     token check · event filter · bot-loop guard
      │
      ├─► GitLabService.get_merge_request_changes()      diff for the MR
      │
      ▼
ReviewService.analyze()
      │   split_diff_into_chunks()      per-file chunks under a size budget
      │   REVIEW_INLINE_PROMPT          diff + MR title/description
      │   AIService.review_chunk()      -> JSON {inline_comments[], summary}
      ▼
GitLabService
      ├─► post_inline_comment()   one per finding, anchored via base/start/head SHA
      ├─► post_summary_comment()  aggregated summary
      └─► add_label("ai-reviewed")
```

```
├── main.py                        application entry point
├── api/routers/webhook.py         webhook endpoint and event filtering
├── core/
│   ├── config.py                      settings from environment
│   ├── logging.py
│   └── security.py
├── domain/
│   ├── models/merge_request.py        MR payload model
│   └── services/
│       ├── review_service.py          chunking, prompting, response assembly
│       ├── gitlab_service.py          MR reads and comment writes
│       └── ai_service.py              provider-agnostic review interface
├── infrastructure/
│   ├── ai/openai_client.py
│   └── gitlab/gitlab_client.py
└── utils/
    ├── chunker.py                     diff -> size-bounded chunks
    └── prompts.py                     review prompt templates
```

## How to Run

```bash
git clone https://github.com/VsProger/ai-code-review-assistant.git
cd ai-code-review-assistant

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill it in:

```
GITLAB_SECRET=        # shared secret, must match the webhook's Secret token
GITLAB_TOKEN=         # personal access token with api scope
GITLAB_BASE_URL=      # https://gitlab.com or your self-hosted instance
OPENAI_API_KEY=
OPENAI_MODEL=
APP_ENV=
LOG_LEVEL=
```

```bash
uvicorn main:app --reload --port 8000
```

Then in GitLab: **Settings → Webhooks** → URL `https://<your-host>/webhook`, set the **Secret token** to the same value as `GITLAB_SECRET`, and enable the **Merge request events** trigger. The service must be reachable from GitLab — for local development, tunnel it.

Open or update a merge request and the bot comments on it.

## Future Improvements

- **Move review off the request path.** The webhook currently runs the whole review synchronously, so GitLab waits through every model call and times out on a large MR. A background task with a job queue, replying 202 immediately, is the correct shape.
- **Populate `core/security.py`.** Token comparison lives inline in the router and is a plain `!=`; it belongs in the security module and should use a constant-time comparison.
- **Retry malformed completions.** A chunk whose response fails to parse is dropped silently; one re-ask with a stricter instruction, and a counter reported in the summary, would make the coverage visible rather than invisible.
- **Deduplicate findings across chunks**, so the same issue in a file touched by several hunks is reported once.
- **Add tests** for the chunker and the webhook filters — both are pure enough to test without a GitLab instance or a live model.
