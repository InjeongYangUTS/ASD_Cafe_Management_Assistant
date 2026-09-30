"""Release 1: MCP and RAG integration. No shared server is needed; responses are faked."""

import importlib.util

import pytest

from services import ai_audit, shared_ai
from services.shared_ai import MCPClient, RAGClient, to_rows, validate_arguments

from conftest import STUDENT_DIR

DEAD_URL = "http://127.0.0.1:9"


class FakeResponse:

    def __init__(self, status_code=200, body=None, headers=None):
        self.status_code = status_code
        self._body = body or {}
        self.headers = headers or {"Content-Type": "application/json"}
        self.text = ""

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise shared_ai.requests.HTTPError(str(self.status_code))


@pytest.fixture()
def backend_client(monkeypatch, tmp_path):
    monkeypatch.setattr(ai_audit, "AUDIT_PATH", str(tmp_path / "ai-audit.jsonl"))
    spec = importlib.util.spec_from_file_location(
        "student1_backend_app", STUDENT_DIR / "backend" / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.app.config["TESTING"] = True
    return module.app.test_client()


# Table shaping

def test_list_of_rows_becomes_a_table():
    columns, rows = to_rows([{"id": 1, "rating": 5}, {"id": 2, "rating": 2}])
    assert columns == ["id", "rating"]
    assert len(rows) == 2


def test_flat_object_becomes_field_value_rows():
    columns, rows = to_rows({"review_count": 3, "average_rating": 3.33})
    assert columns == ["field", "value"]
    assert {"field": "review_count", "value": 3} in rows


def test_fastmcp_result_wrapper_is_unwrapped():
    _columns, rows = to_rows({"result": [{"id": 1}]})
    assert rows == [{"id": 1}]


# RAG

def test_rag_disabled_is_reported(monkeypatch):
    monkeypatch.setenv("RAG_ENABLED", "false")
    result = RAGClient().ask("How is sentiment classified?")
    assert result["status"] == "disabled"
    assert "disabled" in result["reason"]


def test_rag_down_returns_unavailable_not_an_exception(monkeypatch):
    monkeypatch.setenv("RAG_ENABLED", "true")
    result = RAGClient(base_url=DEAD_URL, timeout=1).ask("anything")
    assert result["status"] == "unavailable"


def test_rag_grounded_answer_is_passed_through(monkeypatch):
    monkeypatch.setenv("RAG_ENABLED", "true")
    answer = {"question": "q", "answer": "a", "confidence": "high",
              "status": "success",
              "sources": [{"id": 1, "document": "student-1/x.txt",
                           "excerpt": "e", "coverage": 0.8}]}
    monkeypatch.setattr(shared_ai.requests, "post",
                        lambda *args, **kwargs: FakeResponse(body=answer))

    result = RAGClient().ask("q")

    assert result["status"] == "success"
    assert result["confidence"] == "high"
    assert result["sources"][0]["document"] == "student-1/x.txt"
    assert result["needs_review"] is False


def test_rag_insufficient_context_is_kept_and_flagged(monkeypatch):
    monkeypatch.setenv("RAG_ENABLED", "true")
    body = {"question": "q", "answer": None, "sources": [],
            "confidence": "insufficient", "status": "insufficient_context"}
    monkeypatch.setattr(shared_ai.requests, "post",
                        lambda *args, **kwargs: FakeResponse(body=body))

    result = RAGClient().ask("q")

    assert result["status"] == "insufficient_context"
    assert result["needs_review"] is True


# Argument validation

LIMIT_SCHEMA = {"type": "object", "required": ["limit"],
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 20}}}


def test_valid_arguments_pass():
    assert validate_arguments(LIMIT_SCHEMA, {"limit": 5}) == []


@pytest.mark.parametrize("arguments, problem", [
    ({}, "missing required"),
    ({"limit": 0}, "at least"),
    ({"limit": 99}, "at most"),
    ({"limit": "5"}, "must be integer"),
    ({"limit": True}, "must be integer"),
    ({"limit": 5, "drop": "table"}, "unknown argument"),
])
def test_invalid_arguments_are_rejected(arguments, problem):
    problems = validate_arguments(LIMIT_SCHEMA, arguments)
    assert any(problem in item for item in problems), problems


# MCP

def fake_rpc(tools, call_result=None):
    def rpc(self, method, params=None, session_id=None, request_id=1):
        if method == "tools/list":
            return {"tools": tools}, None
        if method == "tools/call":
            return call_result, None
        return {}, None
    return rpc


def test_mcp_disabled_returns_unavailable(monkeypatch):
    monkeypatch.setenv("MCP_ENABLED", "false")
    client = MCPClient()

    assert client.list_tools()["available"] is False
    assert client.call("student1_review_summary")["ok"] is False


def test_mcp_down_returns_unavailable(monkeypatch):
    monkeypatch.setenv("MCP_ENABLED", "true")
    catalogue = MCPClient(base_url=DEAD_URL, timeout=1).list_tools()
    assert catalogue["available"] is False
    assert catalogue["tools"] == []


def test_mcp_unregistered_tool_is_rejected(monkeypatch):
    monkeypatch.setenv("MCP_ENABLED", "true")
    monkeypatch.setattr(MCPClient, "_rpc",
                        fake_rpc([{"name": "student1_review_summary"}]))

    result = MCPClient().call("drop_all_tables")

    assert result["ok"] is False
    assert result["status"] == "not_registered"
    assert "not a registered" in result["error"]


def test_mcp_out_of_range_argument_never_reaches_the_server(monkeypatch):
    monkeypatch.setenv("MCP_ENABLED", "true")
    calls = []

    def rpc(self, method, params=None, session_id=None, request_id=1):
        calls.append(method)
        return {"tools": [{"name": "student1_recent_reviews",
                           "inputSchema": LIMIT_SCHEMA}]}, None

    monkeypatch.setattr(MCPClient, "_rpc", rpc)

    result = MCPClient().call("student1_recent_reviews", {"limit": 500})

    assert result["status"] == "rejected"
    assert "tools/call" not in calls


def test_mcp_structured_result_is_returned_as_rows(monkeypatch):
    monkeypatch.setenv("MCP_ENABLED", "true")
    call_result = {"structuredContent": {"review_count": 3, "average_rating": 3.33},
                   "content": [{"type": "text", "text": "{}"}], "isError": False}
    monkeypatch.setattr(MCPClient, "_rpc",
                        fake_rpc([{"name": "student1_review_summary"}], call_result))

    result = MCPClient().call("student1_review_summary")

    assert result["ok"] is True
    assert result["row_count"] == 2
    assert result["result"]["review_count"] == 3


def test_mcp_tool_error_is_reported(monkeypatch):
    monkeypatch.setenv("MCP_ENABLED", "true")
    call_result = {"content": [{"type": "text", "text": "limit must be positive"}],
                   "isError": True}
    monkeypatch.setattr(MCPClient, "_rpc",
                        fake_rpc([{"name": "student1_recent_reviews"}], call_result))

    result = MCPClient().call("student1_recent_reviews", {"limit": -1})

    assert result["ok"] is False
    assert "limit must be positive" in result["error"]


# Backend routes

def test_backend_rag_route_rejects_empty_question(backend_client):
    response = backend_client.post("/api/ai/rag", json={"question": "  "})
    assert response.status_code == 400


def test_backend_rag_route_returns_403_when_disabled(backend_client, monkeypatch):
    monkeypatch.setenv("RAG_ENABLED", "false")
    response = backend_client.post("/api/ai/rag", json={"question": "hello"})
    assert response.status_code == 403
    assert response.get_json()["status"] == "disabled"


def test_backend_rag_route_returns_503_when_server_down(backend_client, monkeypatch):
    monkeypatch.setenv("RAG_ENABLED", "true")
    def refuse(*args, **kwargs):
        raise shared_ai.requests.ConnectionError("refused")

    monkeypatch.setattr(shared_ai.requests, "post", refuse)
    response = backend_client.post("/api/ai/rag", json={"question": "hello"})
    assert response.status_code == 503


def test_backend_mcp_routes_return_403_when_disabled(backend_client, monkeypatch):
    monkeypatch.setenv("MCP_ENABLED", "false")

    listing = backend_client.get("/api/ai/mcp")
    assert listing.status_code == 403
    assert listing.get_json()["available"] is False

    call = backend_client.post("/api/ai/mcp", json={"tool": "anything"})
    assert call.status_code == 403
    assert call.get_json()["ok"] is False


def test_every_invocation_is_audited(backend_client, monkeypatch):
    monkeypatch.setenv("MCP_ENABLED", "false")
    monkeypatch.setenv("RAG_ENABLED", "false")

    backend_client.post("/api/ai/mcp", json={"tool": "student1_review_summary"})
    backend_client.post("/api/ai/rag", json={"question": "How is sentiment classified?"})

    entries = backend_client.get("/api/ai/audit").get_json()["entries"]

    assert [entry["mode"] for entry in entries] == ["rag", "mcp"]
    assert entries[1]["name"] == "student1_review_summary"
    assert all(entry["status"] == "disabled" and "duration_ms" in entry
               for entry in entries)


def test_backend_mcp_route_rejects_non_object_arguments(backend_client):
    response = backend_client.post("/api/ai/mcp", json={"tool": "x", "arguments": [1]})
    assert response.status_code == 400
