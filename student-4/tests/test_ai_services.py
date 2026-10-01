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
# McpClient - the streamable-http transport
#
# This is what the team's server actually runs:
#   MCPServer.run(transport="streamable-http", port=5700)
#
# It is not plain JSON-RPC. It needs an Accept header naming
# text/event-stream, an `initialize` handshake that returns a session id,
# a `notifications/initialized` follow-up, and it frames every reply as
# Server-Sent Events whose payload is nested twice. The first version of
# this client knew none of that and could not reach the server at all.
# =====================================================================

SSE_TOOLS = (
    'event: message\n'
    'data: {"jsonrpc":"2.0","id":2,"result":{"tools":'
    '[{"name":"get_orders","description":"List orders.",'
    '"inputSchema":{"type":"object","properties":{}}}]}}\n'
)


def _sse(payload):
    return "event: message\ndata: " + __import__("json").dumps(payload) + "\n"


class StreamableServer:
    """A minimal stand-in for the MCP SDK's streamable-http endpoint."""

    SESSION = "abc123session"

    def __init__(self, tool_payload=None, is_error=False):
        self.tool_payload = tool_payload if tool_payload is not None else {
            "success": True,
            "orders": ORDER_ROWS,
            "count": len(ORDER_ROWS),
        }
        self.is_error = is_error
        self.saw_initialized = False
        self.headers_seen = []

    def post(self, url, **kwargs):
        import json as _json
        path = "/" + url.split("//", 1)[-1].split("/", 1)[1]
        body = kwargs.get("json") or {}
        headers = kwargs.get("headers") or {}
        self.headers_seen.append(headers)

        if path != "/mcp":
            return FakeResponse(404, {"error": "not found"})

        # The SDK rejects a request that does not accept event-stream.
        if "text/event-stream" not in headers.get("Accept", ""):
            return FakeResponse(406, {"error": "Not Acceptable"})

        method = body.get("method")

        if method == "initialize":
            r = FakeResponse(200, {})
            r.text = _sse({"jsonrpc": "2.0", "id": 1,
                           "result": {"protocolVersion": "2025-06-18"}})
            r.headers = {"mcp-session-id": self.SESSION}
            return r

        # Everything after the handshake must carry the session id.
        if headers.get("Mcp-Session-Id") != self.SESSION:
            return FakeResponse(400, {"error": "Missing session ID"})

        if method == "notifications/initialized":
            self.saw_initialized = True
            return FakeResponse(202, {})

        if method == "tools/list":
            r = FakeResponse(200, {})
            r.text = SSE_TOOLS
            r.headers = {}
            return r

        if method == "tools/call":
            r = FakeResponse(200, {})
            r.text = _sse({"jsonrpc": "2.0", "id": body.get("id"), "result": {
                "content": [{"type": "text",
                             "text": _json.dumps(self.tool_payload)}],
                "isError": self.is_error}})
            r.headers = {}
            return r

        return FakeResponse(400, {"error": "bad method"})


def _use_streamable(ai_services, monkeypatch, server):
    class Sess:
        post = staticmethod(server.post)
    monkeypatch.setattr(ai_services.requests, "Session", lambda: Sess())
    monkeypatch.setattr(ai_services.requests, "get",
                        lambda *a, **k: FakeResponse(404, {}))
    monkeypatch.setattr(ai_services.requests, "post",
                        lambda *a, **k: FakeResponse(404, {}))


def test_mcp_speaks_streamable_http(ai_services, monkeypatch):
    server = StreamableServer()
    _use_streamable(ai_services, monkeypatch, server)

    result = ai_services.McpClient("http://mcp.test").call()

    assert result["ok"] is True
    assert "streamable-http" in result["transport"]
    assert result["tool"] == "get_orders"
    assert result["row_count"] == 2


def test_mcp_completes_the_handshake_before_listing(ai_services, monkeypatch):
    server = StreamableServer()
    _use_streamable(ai_services, monkeypatch, server)

    ai_services.McpClient("http://mcp.test").call()

    assert server.saw_initialized, "notifications/initialized was never sent"
    assert any("text/event-stream" in h.get("Accept", "")
               for h in server.headers_seen)
    assert any(h.get("Mcp-Session-Id") == server.SESSION
               for h in server.headers_seen)


def test_mcp_unwraps_the_doubly_nested_payload(ai_services, monkeypatch):
    """result.content[0].text is itself a JSON document."""
    server = StreamableServer()
    _use_streamable(ai_services, monkeypatch, server)

    result = ai_services.McpClient("http://mcp.test").call()

    assert result["rows"][0]["order_number"] == "A-1001"
    assert result["raw"]["success"] is True


def test_mcp_reads_a_tool_level_failure(ai_services, monkeypatch):
    """isError stays False while the tool's own payload says it failed."""
    server = StreamableServer(tool_payload={
        "success": False, "error": "order 99999 not found"})
    _use_streamable(ai_services, monkeypatch, server)

    result = ai_services.McpClient("http://mcp.test").call()

    assert result["available"] is True
    assert result["ok"] is False
    assert "99999" in result["reason"]


def test_mcp_reads_an_is_error_result(ai_services, monkeypatch):
    server = StreamableServer(tool_payload={"any": "thing"}, is_error=True)
    _use_streamable(ai_services, monkeypatch, server)

    result = ai_services.McpClient("http://mcp.test").call()

    assert result["ok"] is False


def test_mcp_nested_lists_do_not_become_table_columns(ai_services, monkeypatch):
    server = StreamableServer(tool_payload={"success": True, "orders": [
        {"id": 1, "order_number": "A-1001",
         "items": [{"id": 9, "name": "Latte"}]}]})
    _use_streamable(ai_services, monkeypatch, server)

    result = ai_services.McpClient("http://mcp.test").call()

    assert "items" not in result["columns"]
    assert "order_number" in result["columns"]
    assert result["raw"]["orders"][0]["items"], "raw keeps the full structure"


def test_mcp_picks_my_tool_not_a_lookalike(ai_services, monkeypatch):
    """Student 3's get_restock_orders also contains the word 'order'."""
    recorder = Recorder({
        "/tools": FakeResponse(200, {"tools": [
            {"name": "get_restock_orders", "description": "Student 3.",
             "inputSchema": {"type": "object"}},
            {"name": "get_inventory_items", "description": "Student 3.",
             "inputSchema": {"type": "object"}},
            {"name": "get_orders", "description": "Student 4.",
             "inputSchema": {"type": "object"}},
        ]}),
        "/invoke": FakeResponse(200, {"data": ORDER_ROWS}),
    })
    monkeypatch.setattr(ai_services.requests, "get", recorder.get)
    monkeypatch.setattr(ai_services.requests, "post", recorder.post)

    result = ai_services.McpClient("http://mcp.test").call()

    assert result["tool"] == "get_orders"


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
