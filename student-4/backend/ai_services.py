"""
Student 4 (Stella Kwon) - Order & Kitchen Management
Clients for the two shared AI services introduced in Release 1.

    McpClient  -> the shared MCP server   (Injeong Yang)
    RagClient  -> the shared RAG server   (Ei Thandar)

Both servers run on the HOST and are deliberately not containerised, so
from inside student-4-backend they are reached through
host.docker.internal, which docker-compose.yml supplies as MCP_URL and
RAG_URL. Outside Docker the defaults are plain localhost.

These follow the same rule as every other client in this feature: the
Order service must stay usable while a dependency is down. Neither
client raises on an outage. Each returns a result object carrying an
"available" flag and a human-readable reason, so the screens can show
what happened instead of a stack trace.

    from ai_services import McpClient, RagClient
    mcp = McpClient()
    rag = RagClient()
"""

import json
import os
import time

import requests

MCP_URL = os.environ.get("MCP_URL", "http://localhost:5700")
RAG_URL = os.environ.get("RAG_URL", "http://localhost:5600")

MCP_TIMEOUT = float(os.environ.get("MCP_TIMEOUT", 15))
RAG_TIMEOUT = float(os.environ.get("RAG_TIMEOUT", 120))

# Which advertised tool belongs to Order & Kitchen.
#
# The shared server puts every feature's tools in one flat namespace, so
# a substring match is not enough: Student 3's "get_restock_orders"
# contains "order". Exact names are tried first, then a hint match that
# skips the other four features' vocabulary.
ORDER_TOOL_NAMES = (
    "get_orders",
    "get_order",
    "get_kitchen_queue",
    "get_order_status",
)

ORDER_TOOL_HINTS = ("order", "kitchen", "queue")

OTHER_FEATURE_WORDS = (
    "inventory", "restock", "supplier", "stock",
    "menu", "recipe", "ingredient",
    "payment", "billing", "invoice", "refund",
    "review", "feedback", "rating",
)


# =====================================================================
# Shared MCP server
# =====================================================================

class McpClient:
    """
    Calls a tool on the shared MCP server and returns its structured result.

    The MCP specification puts JSON-RPC 2.0 on one HTTP endpoint, but a
    small Flask implementation is just as likely to expose plain REST, so
    this client discovers the transport on first use rather than assuming
    one. The same discovery is used by the agentic loop's --mode mcp, and
    the transport it settled on is reported back to the caller so the
    screen can display it.

    Nothing here reads another feature's database. A tool call is an HTTP
    call to the MCP server, which in turn calls the service that owns the
    data.
    """

    def __init__(self, base_url=MCP_URL, timeout=MCP_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._style = None      # "streamable" | "jsonrpc" | "rest"
        self._endpoint = None
        self._session_id = None
        self._tools = None
        self._http = requests.Session()
        self._next_id = 10

    # -- transport ----------------------------------------------------

    SSE_HEADERS = {
        "Content-Type": "application/json",
        # The MCP SDK refuses the request without both of these.
        "Accept": "application/json, text/event-stream",
    }

    def _discover(self):
        """Return the transport name, or None if the server is unreachable."""
        if self._style:
            return self._style

        for path in ("/mcp", "/"):
            tools = self._try_streamable(path)
            if tools is not None:
                self._style, self._endpoint, self._tools = (
                    "streamable", path, tools)
                return self._style

        for path in ("/mcp", "/"):
            tools = self._try_jsonrpc(path)
            if tools is not None:
                self._style, self._endpoint, self._tools = "jsonrpc", path, tools
                return self._style

        tools = self._try_rest()
        if tools is not None:
            self._style, self._endpoint, self._tools = "rest", "/invoke", tools
            return self._style

        return None

    # -- streamable-http (the official MCP SDK) -----------------------

    @staticmethod
    def _parse_sse(text):
        """Pull the JSON payload out of an SSE frame, or plain JSON."""
        for line in text.splitlines():
            if line.startswith("data:"):
                try:
                    return json.loads(line[5:].strip())
                except ValueError:
                    return None
        try:
            return json.loads(text)
        except ValueError:
            return None

    def _headers(self):
        headers = dict(self.SSE_HEADERS)
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    def _rpc(self, path, payload, timeout=None):
        return self._http.post(self.base_url + path, headers=self._headers(),
                               json=payload, timeout=timeout or self.timeout)

    def _try_streamable(self, path):
        """Handshake, then list the tools.

        The SDK will not serve anything until `initialize` has returned a
        session id and `notifications/initialized` has been sent, and it
        frames every reply as Server-Sent Events.
        """
        try:
            response = self._rpc(path, {
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "student-4-backend",
                                   "version": "1.0"},
                }})
        except requests.RequestException:
            return None

        session_id = response.headers.get("mcp-session-id")
        if response.status_code >= 300 or not session_id:
            return None

        self._session_id = session_id

        try:
            self._rpc(path, {"jsonrpc": "2.0",
                             "method": "notifications/initialized"})
            listing = self._rpc(path, {"jsonrpc": "2.0", "id": 2,
                                       "method": "tools/list", "params": {}})
            body = self._parse_sse(listing.text)
        except requests.RequestException:
            self._session_id = None
            return None

        result = (body or {}).get("result")
        if isinstance(result, dict) and isinstance(result.get("tools"), list):
            return result["tools"]

        self._session_id = None
        return None

    def _try_jsonrpc(self, path):
        try:
            response = requests.post(
                self.base_url + path, timeout=self.timeout,
                json={"jsonrpc": "2.0", "id": 1,
                      "method": "tools/list", "params": {}})
            if response.status_code != 200:
                return None
            body = response.json()
        except (requests.RequestException, ValueError):
            return None
        result = body.get("result") if isinstance(body, dict) else None
        if isinstance(result, dict) and isinstance(result.get("tools"), list):
            return result["tools"]
        return None

    def _try_rest(self):
        for path in ("/tools", "/mcp/tools", "/tools/list"):
            try:
                response = requests.get(self.base_url + path,
                                        timeout=self.timeout)
                if response.status_code != 200:
                    continue
                body = response.json()
            except (requests.RequestException, ValueError):
                continue
            if isinstance(body, list):
                return body
            if isinstance(body, dict) and isinstance(body.get("tools"), list):
                return body["tools"]
        return None

    @property
    def transport(self):
        if self._style == "streamable":
            return "streamable-http (MCP SDK) at POST %s" % self._endpoint
        if self._style == "jsonrpc":
            return "JSON-RPC 2.0 at POST %s" % self._endpoint
        if self._style == "rest":
            return "REST at GET /tools + POST /invoke"
        return "not discovered"

    # -- helpers ------------------------------------------------------

    @staticmethod
    def _name_of(tool):
        if isinstance(tool, str):
            return tool
        if isinstance(tool, dict):
            return tool.get("name") or tool.get("tool") or ""
        return ""

    @staticmethod
    def _unwrap(body):
        """Pull the tool's own result out of whichever envelope it arrived in."""
        if not isinstance(body, dict):
            return body
        if "result" in body:                          # JSON-RPC
            inner = body["result"]
            if isinstance(inner, dict) and "content" in inner:
                # streamable-http nests it twice: result.content[0].text
                # is itself a JSON document. A tool that returns prose is
                # left as the string it is.
                content = inner["content"]
                if isinstance(content, list) and content:
                    first = content[0]
                    if isinstance(first, dict) and "text" in first:
                        try:
                            return json.loads(first["text"])
                        except (ValueError, TypeError):
                            return first["text"]
                return content
            return inner
        for key in ("data", "output", "content"):
            if key in body:
                return body[key]
        return body

    @staticmethod
    def _rows(payload):
        """Normalise a tool result into a list of dicts for the table."""
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            for key in ("orders", "items", "results", "rows", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [row for row in value if isinstance(row, dict)]
            return [payload]
        return []

    def _unavailable(self, reason):
        return {
            "available": False,
            "server": self.base_url,
            "reason": reason,
            "tools": [],
            "tool": None,
            "rows": [],
            "raw": None,
        }

    # -- public -------------------------------------------------------

    def list_tools(self):
        """Return (tools, reason). tools is [] when the server is down."""
        if self._discover() is None:
            return [], ("the shared MCP server is not answering on %s"
                        % self.base_url)
        return self._tools or [], None

    def pick_order_tool(self):
        """The Order & Kitchen tool, not another feature's that reads alike."""
        tools = self._tools or []
        by_name = {self._name_of(t).lower(): t for t in tools}

        for wanted in ORDER_TOOL_NAMES:
            if wanted in by_name:
                return by_name[wanted]

        for tool in tools:
            name = self._name_of(tool).lower()
            if any(word in name for word in OTHER_FEATURE_WORDS):
                continue
            if any(hint in name for hint in ORDER_TOOL_HINTS):
                return tool

        return tools[0] if tools else None

    def call(self, tool_name=None, arguments=None):
        """
        Invoke a tool and return a structured, display-ready result.

        Never raises. On any failure the result carries available=False
        and a reason the screen can show.
        """
        arguments = arguments or {}

        if self._discover() is None:
            return self._unavailable(
                "the shared MCP server is not answering on %s. It runs on "
                "the host and is not containerised, so start it before "
                "using this panel." % self.base_url)

        tools = self._tools or []
        if not tools:
            return self._unavailable(
                "the MCP server answered but advertises no tools")

        if tool_name:
            chosen = next((t for t in tools
                           if self._name_of(t) == tool_name), None)
            if chosen is None:
                return self._unavailable(
                    "no tool called %r is advertised. Available: %s"
                    % (tool_name, ", ".join(self._name_of(t) for t in tools)))
        else:
            chosen = self.pick_order_tool()

        name = self._name_of(chosen)
        started = time.time()

        try:
            if self._style == "streamable":
                self._next_id += 1
                response = self._rpc(self._endpoint, {
                    "jsonrpc": "2.0", "id": self._next_id,
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments}})
                body = self._parse_sse(response.text)
                if body is None:
                    return self._unavailable(
                        "the MCP server returned something that is not JSON")
            elif self._style == "jsonrpc":
                response = requests.post(
                    self.base_url + self._endpoint, timeout=self.timeout,
                    json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                          "params": {"name": name, "arguments": arguments}})
                body = response.json()
            else:
                response = requests.post(
                    self.base_url + "/invoke", timeout=self.timeout,
                    json={"tool": name, "arguments": arguments})
                if response.status_code == 404:
                    response = requests.post(
                        self.base_url + "/tools/" + name,
                        timeout=self.timeout, json=arguments)
                body = response.json()
        except requests.RequestException as exc:
            return self._unavailable("the tool call failed: %s" % exc)
        except ValueError:
            return self._unavailable(
                "the MCP server returned something that is not JSON")

        elapsed_ms = int((time.time() - started) * 1000)

        # A failed call can report itself at three levels, and all three
        # have to be read or a failure looks like an empty success:
        #   HTTP status, the JSON-RPC result's isError, and the tool's own
        #   {"success": false, "error": ...} payload.
        detail = self._failure_reason(response.status_code, body)
        if detail:
            return {
                "available": True,
                "ok": False,
                "server": self.base_url,
                "transport": self.transport,
                "tool": name,
                "arguments": arguments,
                "reason": "the tool refused the call: %s" % detail,
                "elapsed_ms": elapsed_ms,
                "tools": [self._name_of(t) for t in tools],
                "rows": [],
                "raw": body,
            }

        payload = self._unwrap(body)
        rows = self._rows(payload)

        # Only scalar fields become table columns. A real tool result
        # carries nested lists - an order's line items, for instance -
        # and putting one in a cell renders as unreadable Python. The
        # full structure is still available under "raw".
        columns = []
        for row in rows:
            for key, value in row.items():
                if isinstance(value, (dict, list)):
                    continue
                if key not in columns:
                    columns.append(key)

        # A column that is empty in every row tells the reader nothing,
        # so it is dropped rather than printed as a stack of "None".
        columns = [c for c in columns
                   if any(row.get(c) not in (None, "") for row in rows)]

        description = ""
        if isinstance(chosen, dict):
            description = str(chosen.get("description", ""))

        return {
            "available": True,
            "ok": True,
            "server": self.base_url,
            "transport": self.transport,
            "tool": name,
            "tool_description": description,
            "arguments": arguments,
            "elapsed_ms": elapsed_ms,
            "tools": [self._name_of(t) for t in tools],
            "row_count": len(rows),
            "columns": columns[:8],
            "rows": rows[:25],
            "raw": payload,
        }

    @classmethod
    def _failure_reason(cls, status, body):
        """A readable reason, or None when the call actually succeeded.

        The body's own message is preferred over the status code: a
        server that answers 400 with {"error": "order_id must be an
        integer"} has told the user something useful, and collapsing
        that to "HTTP 400" throws it away.
        """
        if isinstance(body, dict):
            if "error" in body:
                return str(body["error"])[:200]

            result = body.get("result")
            payload = cls._unwrap(body)

            if isinstance(payload, dict) and payload.get("success") is False:
                return str(payload.get("error",
                                       "the tool reported a failure"))[:200]

            if isinstance(result, dict) and result.get("isError"):
                content = result.get("content") or [{}]
                return str(content[0].get("text", result))[:200]

        if status >= 400:
            return "HTTP %d" % status

        return None

    def health(self):
        # Discovery first: a server with no /health endpoint is still up if
        # it answers the protocol, and the transport and tool count are
        # worth reporting either way.
        discovered = self._discover() is not None

        try:
            response = requests.get(self.base_url + "/health", timeout=3)
            reachable = response.ok or discovered
        except requests.RequestException:
            reachable = discovered

        return {
            "reachable": reachable,
            "url": self.base_url,
            "transport": self.transport,
            "tool_count": len(self._tools or []),
            "containerised": False,
        }


# =====================================================================
# Shared RAG server
# =====================================================================

class RagClient:
    """
    Asks the shared RAG server a question and returns a grounded answer.

    The contract, from shared/rag/:

        POST /retrieve  {"question": str}
        POST /query     {"question": str}
            -> {"question", "answer", "sources", "confidence", "status"}

    Three outcomes matter to the screens and each is returned as its own
    status, never as an exception:

        "success"              an answer, its citations and a confidence
        "insufficient_context" nothing was retrieved, so nothing was
                               answered - this is a correct result, not
                               an error, and the panel says so
        "unavailable"          the server or the model could not be
                               reached

    The client adds no wording of its own to the answer. Everything shown
    on screen comes from the server, including the excerpt behind each
    citation, so a reader can check any claim against the text it was
    drawn from.
    """

    def __init__(self, base_url=RAG_URL, timeout=RAG_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    CONFIDENCE_LABELS = {
        "high": "High confidence",
        "medium": "Medium confidence",
        "low": "Low confidence",
        "insufficient": "Not enough context",
    }

    def _unavailable(self, question, reason):
        return {
            "status": "unavailable",
            "question": question,
            "answer": None,
            "sources": [],
            "confidence": None,
            "confidence_label": None,
            "reason": reason,
            "server": self.base_url,
        }

    def ask(self, question):
        """Ask a question. Never raises."""
        question = (question or "").strip()
        if not question:
            return {
                "status": "invalid",
                "question": "",
                "answer": None,
                "sources": [],
                "confidence": None,
                "confidence_label": None,
                "reason": "Type a question first.",
                "server": self.base_url,
            }

        started = time.time()
        try:
            response = requests.post(
                self.base_url + "/query",
                json={"question": question}, timeout=self.timeout)
        except requests.RequestException as exc:
            return self._unavailable(
                question,
                "the shared RAG server is not answering on %s. It runs on "
                "the host and is not containerised, so start it before "
                "using this panel. (%s)" % (self.base_url, exc))

        elapsed_ms = int((time.time() - started) * 1000)

        try:
            body = response.json()
        except ValueError:
            return self._unavailable(
                question, "the RAG server returned something that is not JSON")

        if response.status_code == 503:
            result = self._unavailable(
                question,
                "the RAG server is up but its language model is not: %s"
                % body.get("error", "no detail given"))
            result["elapsed_ms"] = elapsed_ms
            return result

        if response.status_code >= 400:
            result = self._unavailable(
                question, body.get("error") or
                "the RAG server refused the question (HTTP %d)"
                % response.status_code)
            result["elapsed_ms"] = elapsed_ms
            return result

        status = body.get("status", "success")
        confidence = body.get("confidence")

        sources = []
        for source in body.get("sources") or []:
            coverage = source.get("coverage")
            sources.append({
                "id": source.get("id"),
                "document": source.get("document", "unknown"),
                "excerpt": source.get("excerpt", ""),
                "coverage": coverage,
                "coverage_percent": (round(float(coverage) * 100)
                                     if coverage is not None else None),
            })

        return {
            "status": status,
            "question": body.get("question", question),
            "answer": body.get("answer"),
            "sources": sources,
            "source_count": len(sources),
            "confidence": confidence,
            "confidence_label": self.CONFIDENCE_LABELS.get(
                confidence, confidence),
            "elapsed_ms": elapsed_ms,
            "server": self.base_url,
            "reason": None,
        }

    def retrieve(self, question):
        """Retrieval only, with no model call. Used by the evidence panel."""
        try:
            response = requests.post(
                self.base_url + "/retrieve",
                json={"question": (question or "").strip()}, timeout=10)
            body = response.json()
        except (requests.RequestException, ValueError) as exc:
            return {"available": False, "reason": str(exc), "results": []}

        if response.status_code >= 400:
            return {"available": True, "reason": body.get("error"),
                    "results": []}

        return {"available": True, "reason": None,
                "results": body.get("results", [])}

    def health(self):
        try:
            response = requests.get(self.base_url + "/health", timeout=3)
            body = response.json() if response.ok else {}
            return {
                "reachable": response.ok,
                "url": self.base_url,
                "service": body.get("service"),
                "containerised": False,
            }
        except (requests.RequestException, ValueError):
            return {"reachable": False, "url": self.base_url,
                    "containerised": False}
