"""
Student 4 (Stella Kwon) - Order & Kitchen Management
Unit tests for the two shared AI service clients (Release 1).

No network. Every HTTP call made by McpClient and RagClient is
intercepted, so these run in CI with neither server present - which is
the point, because both are deliberately non-containerised and a GitHub
runner has neither.

What is being pinned down:

    * the MCP transport is DISCOVERED, not assumed, and both the
      JSON-RPC and the REST shapes are understood
    * a tool result is normalised into columns and rows whatever
      envelope it arrived in
    * an outage in either server is returned as data, never raised, so
      the Kitchen screen keeps rendering
    * the RAG client passes the three statuses through unchanged -
      success, insufficient_context and unavailable - and never invents
      an answer of its own
"""

import importlib
import os
import sys

import pytest

STUDENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(STUDENT_DIR, "backend")


@pytest.fixture()
def ai_services():
    sys.path.insert(0, BACKEND_DIR)
    if "ai_services" in sys.modules:
        del sys.modules["ai_services"]
    module = importlib.import_module("ai_services")
    yield module
    sys.path.remove(BACKEND_DIR)
    del sys.modules["ai_services"]


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        if self._payload is Ellipsis:
            raise ValueError("not json")
        return self._payload


class Recorder:
    """Stands in for requests.get / requests.post."""

    def __init__(self, routes, error_paths=()):
        self.routes = routes           # path -> FakeResponse
        self.error_paths = set(error_paths)
        self.calls = []

    def _answer(self, url, **kwargs):
        path = url.split("//", 1)[-1].split("/", 1)
        path = "/" + (path[1] if len(path) > 1 else "")
        self.calls.append((path, kwargs.get("json")))
        if path in self.error_paths:
            import requests
            raise requests.RequestException("refused")
        if path in self.routes:
            return self.routes[path]
        return FakeResponse(404, {"error": "not found"})

    def get(self, url, **kwargs):
        return self._answer(url, **kwargs)

    def post(self, url, **kwargs):
        return self._answer(url, **kwargs)


TOOLS = [
    {"name": "get_orders",
     "description": "List orders.",
     "inputSchema": {"type": "object",
                     "properties": {"order_id": {"type": "integer"}}}},
]

ORDER_ROWS = [
    {"id": 1, "order_number": "A-1001", "status": "PENDING", "total": 9.0},
    {"id": 2, "order_number": "A-1002", "status": "READY", "total": 4.5},
]


# =====================================================================
# McpClient - transport discovery
# =====================================================================

def test_mcp_discovers_the_rest_transport(ai_services, monkeypatch):
    recorder = Recorder({
        "/tools": FakeResponse(200, {"tools": TOOLS}),
        "/invoke": FakeResponse(200, {"data": ORDER_ROWS}),
    })
    monkeypatch.setattr(ai_services.requests, "get", recorder.get)
    monkeypatch.setattr(ai_services.requests, "post", recorder.post)

    client = ai_services.McpClient("http://mcp.test")
    result = client.call()

    assert result["ok"] is True
    assert "REST" in result["transport"]
    assert result["tool"] == "get_orders"
    assert result["row_count"] == 2


def test_mcp_discovers_the_jsonrpc_transport(ai_services, monkeypatch):
    recorder = Recorder({
        "/mcp": FakeResponse(200, {"jsonrpc": "2.0", "id": 1,
                                   "result": {"tools": TOOLS}}),
    })

    def post(url, **kwargs):
        body = kwargs.get("json") or {}
        if body.get("method") == "tools/call":
            recorder.calls.append(("/mcp", body))
            return FakeResponse(200, {"jsonrpc": "2.0", "id": 2,
                                      "result": {"content": ORDER_ROWS}})
        return recorder.post(url, **kwargs)

    monkeypatch.setattr(ai_services.requests, "get", recorder.get)
    monkeypatch.setattr(ai_services.requests, "post", post)

    client = ai_services.McpClient("http://mcp.test")
    result = client.call()

    assert result["ok"] is True
    assert "JSON-RPC" in result["transport"]
    assert result["row_count"] == 2


def test_mcp_discovery_happens_once(ai_services, monkeypatch):
    recorder = Recorder({
        "/tools": FakeResponse(200, {"tools": TOOLS}),
        "/invoke": FakeResponse(200, {"data": ORDER_ROWS}),
    })
    monkeypatch.setattr(ai_services.requests, "get", recorder.get)
    monkeypatch.setattr(ai_services.requests, "post", recorder.post)

    client = ai_services.McpClient("http://mcp.test")
    client.call()
    client.call()

    assert [c[0] for c in recorder.calls].count("/tools") == 1


# =====================================================================
# McpClient - results and failures
# =====================================================================

@pytest.mark.parametrize("envelope", [
    {"data": ORDER_ROWS},
    {"result": {"content": ORDER_ROWS}},
    {"output": {"orders": ORDER_ROWS}},
])
def test_mcp_normalises_every_envelope(ai_services, monkeypatch, envelope):
    recorder = Recorder({
        "/tools": FakeResponse(200, {"tools": TOOLS}),
        "/invoke": FakeResponse(200, envelope),
    })
    monkeypatch.setattr(ai_services.requests, "get", recorder.get)
    monkeypatch.setattr(ai_services.requests, "post", recorder.post)

    result = ai_services.McpClient("http://mcp.test").call()

    assert result["row_count"] == 2
    assert result["columns"][:2] == ["id", "order_number"]


def test_mcp_outage_is_returned_not_raised(ai_services, monkeypatch):
    recorder = Recorder({}, error_paths={"/tools", "/mcp/tools",
                                         "/tools/list", "/mcp", "/"})
    monkeypatch.setattr(ai_services.requests, "get", recorder.get)
    monkeypatch.setattr(ai_services.requests, "post", recorder.post)

    result = ai_services.McpClient("http://mcp.test").call()

    assert result["available"] is False
    assert "not answering" in result["reason"]
    assert result["rows"] == []


def test_mcp_unknown_tool_is_reported_with_the_alternatives(ai_services,
                                                            monkeypatch):
    recorder = Recorder({"/tools": FakeResponse(200, {"tools": TOOLS})})
    monkeypatch.setattr(ai_services.requests, "get", recorder.get)
    monkeypatch.setattr(ai_services.requests, "post", recorder.post)

    result = ai_services.McpClient("http://mcp.test").call("no_such_tool")

    assert result["available"] is False
    assert "get_orders" in result["reason"]


def test_mcp_tool_error_keeps_the_panel_alive(ai_services, monkeypatch):
    recorder = Recorder({
        "/tools": FakeResponse(200, {"tools": TOOLS}),
        "/invoke": FakeResponse(400, {"error": "order_id must be an integer"}),
    })
    monkeypatch.setattr(ai_services.requests, "get", recorder.get)
    monkeypatch.setattr(ai_services.requests, "post", recorder.post)

    result = ai_services.McpClient("http://mcp.test").call(
        arguments={"order_id": "abc"})

    assert result["available"] is True
    assert result["ok"] is False
    assert "order_id" in result["reason"]


def test_mcp_health_reports_the_transport(ai_services, monkeypatch):
    recorder = Recorder({
        "/health": FakeResponse(200, {"status": "ok"}),
        "/tools": FakeResponse(200, {"tools": TOOLS}),
    })
    monkeypatch.setattr(ai_services.requests, "get", recorder.get)
    monkeypatch.setattr(ai_services.requests, "post", recorder.post)

    health = ai_services.McpClient("http://mcp.test").health()

    assert health["reachable"] is True
    assert health["tool_count"] == 1
    assert health["containerised"] is False


# =====================================================================
# RagClient
# =====================================================================

GROUNDED = {
    "question": "What does the Order and Kitchen feature manage?",
    "answer": "It manages customer orders and kitchen operations.",
    "sources": [{"id": 1, "document": "cafe_overview.txt",
                 "excerpt": "The Order and Kitchen feature manages "
                            "customer orders and kitchen operations.",
                 "coverage": 0.75}],
    "confidence": "high",
    "status": "success",
}

REFUSED = {
    "question": "What is the refund policy for oat milk?",
    "answer": None,
    "sources": [],
    "confidence": "insufficient",
    "status": "insufficient_context",
}


def test_rag_passes_a_grounded_answer_through_unchanged(ai_services,
                                                        monkeypatch):
    recorder = Recorder({"/query": FakeResponse(200, GROUNDED)})
    monkeypatch.setattr(ai_services.requests, "post", recorder.post)

    result = ai_services.RagClient("http://rag.test").ask("anything")

    assert result["status"] == "success"
    assert result["answer"] == GROUNDED["answer"]
    assert result["confidence"] == "high"
    assert result["confidence_label"] == "High confidence"
    assert result["source_count"] == 1


def test_rag_turns_coverage_into_a_percentage_for_the_screen(ai_services,
                                                             monkeypatch):
    recorder = Recorder({"/query": FakeResponse(200, GROUNDED)})
    monkeypatch.setattr(ai_services.requests, "post", recorder.post)

    result = ai_services.RagClient("http://rag.test").ask("anything")

    assert result["sources"][0]["coverage_percent"] == 75
    assert result["sources"][0]["document"] == "cafe_overview.txt"
    assert result["sources"][0]["excerpt"]


def test_rag_insufficient_context_is_not_an_error(ai_services, monkeypatch):
    recorder = Recorder({"/query": FakeResponse(200, REFUSED)})
    monkeypatch.setattr(ai_services.requests, "post", recorder.post)

    result = ai_services.RagClient("http://rag.test").ask("oat milk refunds")

    assert result["status"] == "insufficient_context"
    assert result["answer"] is None
    assert result["sources"] == []
    assert result["confidence_label"] == "Not enough context"


def test_rag_never_writes_an_answer_of_its_own(ai_services, monkeypatch):
    """The client must not paper over a refusal with wording of its own."""
    recorder = Recorder({"/query": FakeResponse(200, REFUSED)})
    monkeypatch.setattr(ai_services.requests, "post", recorder.post)

    result = ai_services.RagClient("http://rag.test").ask("oat milk refunds")

    assert result["answer"] is None


def test_rag_model_outage_becomes_unavailable(ai_services, monkeypatch):
    recorder = Recorder({"/query": FakeResponse(
        503, {"error": "Failed to communicate with Ollama"})})
    monkeypatch.setattr(ai_services.requests, "post", recorder.post)

    result = ai_services.RagClient("http://rag.test").ask("anything")

    assert result["status"] == "unavailable"
    assert "language model" in result["reason"]


def test_rag_server_outage_is_returned_not_raised(ai_services, monkeypatch):
    recorder = Recorder({}, error_paths={"/query"})
    monkeypatch.setattr(ai_services.requests, "post", recorder.post)

    result = ai_services.RagClient("http://rag.test").ask("anything")

    assert result["status"] == "unavailable"
    assert result["answer"] is None
    assert "not answering" in result["reason"]


def test_rag_refuses_a_blank_question_without_calling_the_server(ai_services,
                                                                 monkeypatch):
    recorder = Recorder({})
    monkeypatch.setattr(ai_services.requests, "post", recorder.post)

    result = ai_services.RagClient("http://rag.test").ask("   ")

    assert result["status"] == "invalid"
    assert recorder.calls == []


def test_rag_health_marks_itself_non_containerised(ai_services, monkeypatch):
    recorder = Recorder({"/health": FakeResponse(
        200, {"status": "ok", "service": "shared-rag"})})
    monkeypatch.setattr(ai_services.requests, "get", recorder.get)

    health = ai_services.RagClient("http://rag.test").health()

    assert health["reachable"] is True
    assert health["service"] == "shared-rag"
    assert health["containerised"] is False
