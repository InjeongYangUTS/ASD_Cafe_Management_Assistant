"""Release 2: shared Multi-Agent server integration. No server is needed; responses are faked."""

import importlib.util

import pytest

from services import ai_audit, shared_ai
from services.shared_ai import MultiAgentClient

from conftest import STUDENT_DIR

DEAD_URL = "http://127.0.0.1:9"

WORKFLOW = {
    "workflow_id": "wf-1",
    "task": "Summarise complaints",
    "status": "awaiting_human_review",
    "plan": {"worker_steps": ["Read reviews"]},
    "worker_output": {"result": "Cold coffee", "missing_information": [], "evidence_used": []},
    "review": {"assessment": "ok", "issues": [], "recommendation": "approve", "reason": "grounded"},
    "human_review": None,
    "history": [],
}


class FakeResponse:

    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body or {}

    def json(self):
        return self._body


@pytest.fixture()
def backend_client(monkeypatch, tmp_path):
    monkeypatch.setattr(ai_audit, "AUDIT_PATH", str(tmp_path / "ai-audit.jsonl"))
    spec = importlib.util.spec_from_file_location(
        "student1_backend_app", STUDENT_DIR / "backend" / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.app.config["TESTING"] = True
    return module.app.test_client()


def test_multi_agent_disabled_is_reported(monkeypatch):
    monkeypatch.setenv("MULTI_AGENT_ENABLED", "false")
    result = MultiAgentClient().start("Summarise complaints", {})
    assert result["status"] == "disabled"
    assert result["workflow"] is None


def test_multi_agent_down_returns_unavailable_not_an_exception(monkeypatch):
    monkeypatch.setenv("MULTI_AGENT_ENABLED", "true")
    result = MultiAgentClient(base_url=DEAD_URL, timeout=1).start("Summarise complaints", {})
    assert result["status"] == "unavailable"
    assert DEAD_URL in result["reason"]


def test_multi_agent_workflow_is_passed_through(monkeypatch):
    monkeypatch.setenv("MULTI_AGENT_ENABLED", "true")
    sent = {}

    def fake_request(method, url, json=None, timeout=None):
        sent.update(method=method, url=url, json=json)
        return FakeResponse(201, WORKFLOW)

    monkeypatch.setattr(shared_ai.requests, "request", fake_request)
    result = MultiAgentClient(base_url="http://ma").start("Summarise complaints", {"review_count": 3})

    assert result["status"] == "success"
    assert result["workflow"]["status"] == "awaiting_human_review"
    assert sent == {"method": "POST", "url": "http://ma/workflows",
                    "json": {"task": "Summarise complaints", "evidence": {"review_count": 3}}}


def test_multi_agent_server_error_is_reported(monkeypatch):
    monkeypatch.setenv("MULTI_AGENT_ENABLED", "true")
    monkeypatch.setattr(shared_ai.requests, "request",
                        lambda *a, **k: FakeResponse(400, {"error": "Workflow is not awaiting human review."}))

    result = MultiAgentClient(base_url="http://ma").review("wf-1", "approve")

    assert result["status"] == "rejected"
    assert result["reason"] == "Workflow is not awaiting human review."


def test_backend_multi_agent_route_returns_403_when_disabled(backend_client, monkeypatch):
    monkeypatch.setenv("MULTI_AGENT_ENABLED", "false")
    response = backend_client.post("/api/ai/multi-agent", json={"task": "Summarise complaints"})
    assert response.status_code == 403
    assert response.get_json()["status"] == "disabled"


def test_backend_multi_agent_route_rejects_empty_task(backend_client):
    response = backend_client.post("/api/ai/multi-agent", json={"task": "  "})
    assert response.status_code == 400


@pytest.mark.parametrize("body", [
    {"decision": "maybe"},
    {"decision": "correct", "comments": ""},
])
def test_backend_human_review_validates_decision(backend_client, body):
    response = backend_client.post("/api/ai/multi-agent/wf-1/review", json=body)
    assert response.status_code == 400


def test_multi_agent_invocations_are_audited(backend_client, monkeypatch):
    monkeypatch.setenv("MULTI_AGENT_ENABLED", "false")

    backend_client.post("/api/ai/multi-agent", json={"task": "Summarise complaints"})
    backend_client.post("/api/ai/multi-agent/wf-1/review", json={"decision": "approve"})

    entries = backend_client.get("/api/ai/audit").get_json()["entries"]

    assert [entry["name"] for entry in entries] == ["human-review", "start"]
    assert all(entry["mode"] == "multi-agent" and entry["status"] == "disabled"
               for entry in entries)
