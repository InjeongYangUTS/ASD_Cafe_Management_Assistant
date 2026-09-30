import json
import os

import requests

MCP_URL = os.environ.get("MCP_URL", "http://localhost:5700").rstrip("/")
RAG_URL = os.environ.get("RAG_URL", "http://localhost:5600").rstrip("/")

MCP_TIMEOUT = float(os.environ.get("MCP_TIMEOUT", 15))
RAG_TIMEOUT = float(os.environ.get("RAG_TIMEOUT", 120))


def _enabled(name):
    return os.environ.get(name, "true").strip().lower() not in ("0", "false", "no", "off")


def _parse_rpc_body(response):
    """Streamable HTTP answers with plain JSON or a single SSE message."""
    content_type = response.headers.get("Content-Type", "")

    if "text/event-stream" in content_type:
        for line in response.text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        raise ValueError("empty event stream")

    return response.json()


JSON_TYPES = {"integer": int, "number": (int, float), "string": str,
              "boolean": bool, "object": dict, "array": list}


def validate_arguments(schema, arguments):
    """Check arguments against a tool's inputSchema; returns a list of problems."""
    if not schema:
        return []

    properties = schema.get("properties", {})
    problems = []

    for name in schema.get("required", []):
        if name not in arguments:
            problems.append("missing required argument '%s'" % name)

    for name, value in arguments.items():
        rules = properties.get(name)
        if rules is None:
            problems.append("unknown argument '%s'" % name)
            continue

        expected = JSON_TYPES.get(rules.get("type"))
        if expected and (not isinstance(value, expected) or
                         (isinstance(value, bool) and rules.get("type") != "boolean")):
            problems.append("'%s' must be %s" % (name, rules["type"]))
            continue

        if "enum" in rules and value not in rules["enum"]:
            problems.append("'%s' must be one of %s" % (name, rules["enum"]))
        if "minimum" in rules and value < rules["minimum"]:
            problems.append("'%s' must be at least %s" % (name, rules["minimum"]))
        if "maximum" in rules and value > rules["maximum"]:
            problems.append("'%s' must be at most %s" % (name, rules["maximum"]))

    return problems


def to_rows(payload):
    """Flatten a tool result into (columns, rows) for a table."""
    if isinstance(payload, dict) and set(payload) == {"result"}:
        payload = payload["result"]

    if isinstance(payload, list):
        rows = [item if isinstance(item, dict) else {"value": item} for item in payload]
    elif isinstance(payload, dict):
        nested = [value for value in payload.values()
                  if isinstance(value, list) and value and isinstance(value[0], dict)]
        if nested:
            rows = nested[0]
        else:
            rows = [{"field": key, "value": value} for key, value in payload.items()]
    elif payload is None:
        rows = []
    else:
        rows = [{"value": payload}]

    columns = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)

    return columns, rows


class MCPClient:

    def __init__(self, base_url=MCP_URL, timeout=MCP_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @property
    def enabled(self):
        return _enabled("MCP_ENABLED")

    def _rpc(self, method, params=None, session_id=None, request_id=1):
        headers = {"Accept": "application/json, text/event-stream"}
        if session_id:
            headers["Mcp-Session-Id"] = session_id

        body = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if request_id is not None:
            body["id"] = request_id

        response = requests.post(self.base_url + "/mcp", json=body,
                                 headers=headers, timeout=self.timeout)
        response.raise_for_status()

        if request_id is None:
            return None, response.headers.get("Mcp-Session-Id")

        data = _parse_rpc_body(response)
        if data.get("error"):
            raise RuntimeError(data["error"].get("message") or "MCP error")

        return data.get("result"), response.headers.get("Mcp-Session-Id")

    def _session(self):
        _result, session_id = self._rpc("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "student-1-backend", "version": "1.0"},
        })
        self._rpc("notifications/initialized", session_id=session_id, request_id=None)
        return session_id

    def _unavailable(self, status, reason):
        return {"available": False, "status": status, "reason": reason,
                "server": self.base_url, "count": 0, "tools": []}

    def list_tools(self):
        if not self.enabled:
            return self._unavailable("disabled", "MCP is disabled (MCP_ENABLED=false).")

        try:
            session_id = self._session()
            result, _ = self._rpc("tools/list", session_id=session_id, request_id=2)
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            return self._unavailable("unavailable",
                                     "The shared MCP server is not reachable at %s (%s)."
                                     % (self.base_url, exc.__class__.__name__))

        tools = [{"name": tool.get("name"),
                  "description": tool.get("description") or "",
                  "input_schema": tool.get("inputSchema") or {}}
                 for tool in (result or {}).get("tools", [])]

        return {"available": True, "status": "success", "reason": None,
                "server": self.base_url, "count": len(tools), "tools": tools}

    def call(self, tool_name, arguments=None):
        arguments = arguments or {}
        outcome = {"ok": False, "tool": tool_name, "arguments": arguments,
                   "server": self.base_url}

        def fail(status, error):
            outcome.update({"status": status, "error": error})
            return outcome

        if not tool_name:
            return fail("rejected", "Choose a tool to run.")

        catalogue = self.list_tools()
        if not catalogue["available"]:
            return fail(catalogue["status"], catalogue["reason"])

        tool = next((t for t in catalogue["tools"] if t["name"] == tool_name), None)
        if tool is None:
            return fail("not_registered", "'%s' is not a registered MCP tool." % tool_name)

        problems = validate_arguments(tool["input_schema"], arguments)
        if problems:
            return fail("rejected", "Invalid arguments: " + "; ".join(problems) + ".")

        try:
            session_id = self._session()
            result, _ = self._rpc("tools/call",
                                  {"name": tool_name, "arguments": arguments},
                                  session_id=session_id, request_id=3)
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            return fail("unavailable", "The MCP tool call failed: %s" % exc)

        result = result or {}
        payload = result.get("structuredContent")
        texts = [part.get("text", "") for part in result.get("content", [])
                 if part.get("type") == "text"]

        if payload is None and texts:
            try:
                payload = json.loads(texts[0])
            except ValueError:
                payload = "\n".join(texts)

        if result.get("isError"):
            return fail("tool_error", "\n".join(texts) or "The tool reported an error.")

        columns, rows = to_rows(payload)
        outcome.update({"ok": True, "status": "success", "result": payload,
                        "columns": columns, "rows": rows, "row_count": len(rows)})
        return outcome


class RAGClient:

    def __init__(self, base_url=RAG_URL, timeout=RAG_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @property
    def enabled(self):
        return _enabled("RAG_ENABLED")

    def _unavailable(self, question, status, reason):
        return {"question": question, "answer": None, "sources": [],
                "confidence": None, "status": status, "reason": reason,
                "server": self.base_url}

    def ask(self, question):
        if not self.enabled:
            return self._unavailable(question, "disabled",
                                     "RAG is disabled (RAG_ENABLED=false).")

        try:
            response = requests.post(self.base_url + "/query",
                                     json={"question": question},
                                     timeout=self.timeout)
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            return self._unavailable(question, "unavailable",
                                     "The shared RAG server is not reachable at %s (%s)."
                                     % (self.base_url, exc.__class__.__name__))

        if response.status_code != 200:
            return self._unavailable(question, "unavailable", data.get("error") or
                                     "The RAG server answered HTTP %d." % response.status_code)

        data["server"] = self.base_url
        data["needs_review"] = data.get("confidence") in ("low", "insufficient")
        return data
