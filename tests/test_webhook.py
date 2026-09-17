import pytest
from fastapi.testclient import TestClient

import api.routers.webhook as webhook_module
from main import app

MR_PAYLOAD = {
    "project": {"id": 7},
    "user": {"id": 99},
    "object_attributes": {
        "iid": 42,
        "title": "Add retry",
        "description": "Why",
        "action": "open",
        "base_sha": "b", "start_sha": "s", "head_sha": "h",
    },
}


@pytest.fixture
def client(monkeypatch):
    """Replace the review task so nothing reaches GitLab or the model."""
    scheduled = []

    async def fake_run_review(event):
        scheduled.append(event)

    monkeypatch.setattr(webhook_module, "run_review", fake_run_review)
    with TestClient(app) as c:
        c.scheduled = scheduled
        yield c


def post(client, token="test-secret", event="Merge Request Hook", payload=MR_PAYLOAD):
    return client.post("/webhook", json=payload,
                       headers={"X-Gitlab-Token": token, "X-Gitlab-Event": event})


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_valid_event_is_accepted_and_scheduled(client):
    resp = post(client)
    assert resp.status_code == 202
    assert resp.json()["merge_request_iid"] == 42
    assert len(client.scheduled) == 1
    assert client.scheduled[0].title == "Add retry"
    assert client.scheduled[0].sha.head_sha == "h"


def test_wrong_token_is_forbidden(client):
    assert post(client, token="wrong").status_code == 403
    assert client.scheduled == []


def test_missing_token_is_forbidden(client):
    resp = client.post("/webhook", json=MR_PAYLOAD,
                       headers={"X-Gitlab-Event": "Merge Request Hook"})
    assert resp.status_code == 403


def test_non_merge_request_event_is_ignored(client):
    resp = post(client, event="Push Hook")
    assert resp.status_code == 202
    assert resp.json()["status"] == "ignored"
    assert client.scheduled == []


def test_merged_action_is_ignored(client):
    payload = {**MR_PAYLOAD, "object_attributes": {**MR_PAYLOAD["object_attributes"],
                                                   "action": "merge"}}
    resp = post(client, payload=payload)
    assert resp.json()["status"] == "ignored"
    assert client.scheduled == []


def test_bot_authored_event_is_ignored(client, monkeypatch):
    from core.config import settings
    monkeypatch.setattr(settings, "gitlab_bot_user_id", 99)  # payload user id
    resp = post(client)
    assert resp.json()["status"] == "ignored"
    assert client.scheduled == []
