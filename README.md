# AI Code Review Assistant

A FastAPI service that reviews GitLab merge requests with an LLM: it receives the MR webhook, fetches the diff, asks the model for structured findings, and posts them back as inline comments anchored to the changed lines, plus a summary.

## Overview

Review backlog is the usual bottleneck in a team: mechanical issues — an unhandled error path, a missing validation, a naming inconsistency — consume senior reviewers' attention before anyone looks at the design. This service takes the mechanical pass, so a human reviewer opens the MR with the obvious problems already annotated.

It is a bot with write access to merge requests, so the design is shaped mostly by the ways that can go wrong: a webhook anyone can call, diffs larger than the model's context, model output that is not valid JSON, a bot whose own comments retrigger it, and a review that takes far longer than the caller is willing to wait.

## Technical Approach

**The webhook answers immediately.** A full review is many model calls and takes minutes; GitLab's webhook timeout is seconds. The endpoint validates, schedules the review as a background task and returns `202 Accepted`. Doing the work inline — as the first version did — means GitLab times out and retries, and the same MR gets reviewed repeatedly.

**Authentication in constant time.** The `X-Gitlab-Token` header is compared against the configured secret with `hmac.compare_digest`. A plain `!=` returns as soon as two bytes differ, which leaks the length of the matching prefix through timing and lets a secret be recovered one character at a time.

**Loop prevention.** The bot writes comments to the MR, and comments are events. Events attributed to the bot's own user id are dropped, as are `close` and `merge` actions and any event that is not a Merge Request Hook. The bot's user id is a required part of configuration rather than an optional extra, because without it the service will loop on its own output.

**Diff chunking.** `split_diff_into_chunks` packs per-file diffs into chunks under a character budget, keeping each file's `File: <path>` header attached to its hunks so the model always knows which file it is reading.

**Structured output, defended twice.** The request sets `response_format={"type": "json_object"}`, so the provider enforces syntactically valid JSON. The parser still tolerates a fenced block or JSON padded with prose, then validates against a Pydantic model; entries with the wrong shape are dropped rather than crashing the chunk. Transport failures and `429`/`5xx` responses are retried three times with exponential backoff.

**Partial coverage is reported, not hidden.** A chunk that cannot be parsed after retries is a chunk that was not reviewed. The summary states how many of the chunks were reviewed, so nobody reads a short review as a clean bill of health.

**Deduplication.** A file touched by several hunks appears in more than one chunk, so the same finding comes back more than once. Findings are collapsed on `(file, line, comment)` before anything is posted.

**Bounded concurrency.** Chunks are reviewed concurrently under a semaphore rather than one after another, which is the difference between a review that scales with MR size and one that does not.

**Layering.** `api/` handles HTTP, `domain/services/` holds review orchestration and merge-request operations, `infrastructure/` wraps the OpenAI and GitLab HTTP clients, `utils/` holds chunking, prompts and parsing. `ReviewService` depends on `AIService`, which delegates to a provider client — swapping vendors means writing one class with the same `complete_json` signature. The entire I/O path is `async`; a synchronous HTTP call inside an async endpoint blocks the event loop for every other request.

## Technologies

Python · FastAPI · Uvicorn · httpx (async) · Pydantic / pydantic-settings · pytest · OpenAI API · GitLab REST API (webhooks, merge request changes, discussions)

## Architecture

```
GitLab MR event
      │  POST /webhook  (X-Gitlab-Token, X-Gitlab-Event)
      ▼
api/routers/webhook.py
      │   constant-time token check
      │   event / action / bot-author filters
      └─► 202 Accepted ................................ returns here
              │
              ▼  background task
      GitLabService.get_merge_request_changes()
              │
              ▼
      ReviewService.analyze()
              │   split_diff_into_chunks()      per-file chunks under a budget
              │   REVIEW_INLINE_PROMPT          title + description + diff
              │   asyncio.gather (semaphore)    bounded concurrency
              │   OpenAIClient.complete_json()  JSON mode, retry + backoff
              │   parse_chunk_review()          fence/prose tolerant, validated
              │   _dedupe()                     collapse repeats across chunks
              ▼
      GitLabService
              ├─► post_inline_comment()   anchored via base/start/head SHA
              ├─► post_summary_comment()  summary + coverage line
              └─► add_label("ai-reviewed")
```

```
├── main.py                        app factory, logging setup, /healthz
├── api/routers/webhook.py         endpoint, filters, background scheduling
├── core/
│   ├── config.py                      settings from environment
│   ├── logging.py                     log configuration
│   └── security.py                    constant-time token verification
├── domain/
│   ├── models/merge_request.py        typed webhook payload and review output
│   └── services/
│       ├── review_service.py          chunking, prompting, dedup, coverage
│       ├── gitlab_service.py          MR reads and comment writes
│       └── ai_service.py              provider-agnostic review interface
├── infrastructure/
│   ├── ai/openai_client.py            JSON mode, retry, backoff
│   └── gitlab/gitlab_client.py        pooled async REST client
├── utils/
│   ├── chunker.py                     diff -> size-bounded chunks
│   ├── parsing.py                     completion -> validated findings
│   └── prompts.py                     system and review prompts
└── tests/                         28 tests, no network or API key required
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
GITLAB_SECRET=          # shared secret, must match the webhook's Secret token
GITLAB_TOKEN=           # personal access token with api scope
GITLAB_BASE_URL=        # https://gitlab.com/api/v4 or your instance
GITLAB_BOT_USER_ID=     # user id the bot posts as -- set this, see below
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```

```bash
uvicorn main:app --reload --port 8000
curl localhost:8000/healthz
```

In GitLab: **Settings → Webhooks** → URL `https://<your-host>/webhook`, set **Secret token** to the same value as `GITLAB_SECRET`, and enable the **Merge request events** trigger. The service must be reachable from GitLab — for local development, tunnel it.

> Set `GITLAB_BOT_USER_ID` to the numeric id of the account whose token you configured (`GET /api/v4/user` returns it). If it is left empty the bot cannot recognise its own comments, and each summary it posts triggers another review.

Open or update a merge request and the bot comments on it.

## Tests

```bash
pytest
```

28 tests covering chunking, token verification, response parsing, review assembly and the webhook endpoint. The model and GitLab are both replaced with fakes, so the suite needs no API key and makes no network calls.

## Future Improvements

- **Move background work into a real queue.** `BackgroundTasks` runs in-process, so a restart loses a review in flight and a burst of MRs is bounded only by memory. Celery or arq with a Redis broker would make the work durable and observable.
- **Cache reviews by diff hash**, so reopening or rebasing an MR does not pay for the same chunks twice.
- **Resolve stale threads.** Comments stay open once the line they point at is fixed; tracking discussion ids per MR would let the bot resolve its own threads on the next run.
- **Post a review rather than isolated comments.** GitLab's discussions API can group findings into a single review, which reads better than a scatter of separate threads on a large MR.
- **Report token cost per review** in the summary, so the price of running the bot on a large MR is visible to the team.
