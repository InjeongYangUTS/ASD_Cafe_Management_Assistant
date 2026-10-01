"""
Student 4 (Stella Kwon) - Shared Agentic Loop
MCP validation probe pack.

Validates the shared MCP server that the team runs locally and
non-containerised. The server is owned by Injeong Yang; this pack is the
contract test that decides whether it is behaving, and it is the
--mode mcp half of the shared agentic loop.

TRANSPORT DISCOVERY
-------------------
The MCP specification puts JSON-RPC 2.0 on a single HTTP endpoint, but a
small teaching implementation is just as likely to expose plain REST. So
this pack does not assume one. On the first call it tries, in order:

    1. JSON-RPC  POST /mcp     {"method": "tools/list"}
    2. JSON-RPC  POST /        {"method": "tools/list"}
    3. REST      GET  /tools   then POST /tools/<name>
    4. REST      GET  /tools   then POST /invoke {"tool", "arguments"}

Whichever answers first is remembered for the rest of the run and named
in the probe evidence, so the log records which contract the server
actually implements rather than which one I hoped for. If none of them
answers, every probe in the pack fails with the same message and the
loop's ADAPT step reports that the server is not reachable - which is
the correct outcome, not a crash.

WHAT IS BEING VALIDATED
-----------------------
    availability  the server is up, and it is not a Compose service
    protocol      a tool list is discoverable and each tool is described
    invocation    a tool call returns structured data, not prose
    resilience    unknown tools and bad arguments are refused, the
                  server does not hang, and it does not reach around
                  the owning service to read a database directly

The probe that matters most is mcp_agrees_with_the_owning_service. A
tool that returns well-formed JSON which disagrees with the service that
owns the data is worse than a tool that is down, because nothing else
will catch it. That probe calls the MCP tool and my own backend for the
same order and compares them.
"""

import json
import os
import re
import time

import requests

from repo import REPO_ROOT, must_not_be_containerised

AREAS = ["availability", "protocol", "invocation", "resilience"]

# Which advertised tool belongs to Order & Kitchen.
#
# The shared server exposes every feature's tools in one flat namespace,
# so a substring match is not enough: Student 3's "get_restock_orders"
# contains "order" and was picked ahead of my own tools the first time
# this ran against the real server. Exact names are tried first, in the
# order listed, and the hint match that follows excludes the vocabulary
# belonging to the other four features.
ORDER_TOOL_NAMES = (
    "get_orders",
    "get_order",
    "get_kitchen_queue",
    "get_order_status",
)

ORDER_TOOL_HINTS = ("order", "kitchen", "queue")

OTHER_FEATURE_WORDS = (
    "inventory", "restock", "supplier", "stock",     # Student 3
    "menu", "recipe", "ingredient",                  # Student 2
    "payment", "billing", "invoice", "refund",       # Student 5
    "review", "feedback", "rating",                  # Student 1
)


class McpTransport:
    """Discovers and remembers how this MCP server actually speaks.

    Three shapes are tried, in this order:

      1. streamable-http  POST /mcp   the official MCP Python SDK (mcp 2.x,
                                      MCPServer.run(transport="streamable-http")).
                                      JSON-RPC 2.0, but the response is
                                      Server-Sent-Events framed and every
                                      call after `initialize` has to carry
                                      the Mcp-Session-Id header the server
                                      issued. This is what Group 48's
                                      server actually uses.
      2. plain JSON-RPC   POST /mcp or /     a hand-written Flask server
      3. REST             GET /tools + POST /invoke

    Order matters. The first version of this class only knew shapes 2 and 3
    and could not talk to the real server at all: a bare POST to /mcp with
    no Accept header and no handshake was answered with a terminated
    session, and /tools, /mcp/tools, /tools/list and /health were all 404.
    Finding that was the point of running the loop against the real thing
    rather than only against a stub.
    """

    SSE_HEADERS = {
        "Content-Type": "application/json",
        # The SDK refuses the request without both of these.
        "Accept": "application/json, text/event-stream",
    }

    def __init__(self, base_url, timeout=20):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.style = None          # "streamable" | "jsonrpc" | "rest"
        self.endpoint = None
        self.session_id = None
        self.error = None
        self._tools = None
        self._http = requests.Session()
        self._next_id = 10

    # -- discovery ----------------------------------------------------

    def discover(self):
        if self.style or self.error:
            return self.style

        for path in ("/mcp", "/"):
            tools = self._try_streamable(path)
            if tools is not None:
                self.style, self.endpoint, self._tools = (
                    "streamable", path, tools)
                return self.style

        for path in ("/mcp", "/"):
            tools = self._try_jsonrpc(path)
            if tools is not None:
                self.style, self.endpoint, self._tools = "jsonrpc", path, tools
                return self.style

        tools = self._try_rest_list()
        if tools is not None:
            self.style, self.endpoint, self._tools = "rest", "/invoke", tools
            return self.style

        self.error = ("no MCP transport answered at %s - tried "
                      "streamable-http and plain JSON-RPC on /mcp and /, "
                      "and REST on /tools" % self.base)
        return None

    # -- streamable-http ----------------------------------------------

    @staticmethod
    def _parse_sse(text):
        """Pull the JSON payload out of an SSE frame.

        A streamable-http reply looks like:

            event: message
            data: {"jsonrpc":"2.0","id":1,"result":{...}}

        A server that answers with plain JSON instead is also accepted,
        so this works either way.
        """
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
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        return headers

    def _rpc(self, path, payload, timeout=None):
        return self._http.post(self.base + path, headers=self._headers(),
                               json=payload, timeout=timeout or self.timeout)

    def _try_streamable(self, path):
        try:
            response = self._rpc(path, {
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "student-4-agentic-loop",
                                   "version": "1.0"},
                }})
        except requests.RequestException:
            return None

        session_id = response.headers.get("mcp-session-id")
        if response.status_code >= 300 or not session_id:
            return None

        self.session_id = session_id

        # The server will not serve anything else until this is sent.
        try:
            self._rpc(path, {"jsonrpc": "2.0",
                             "method": "notifications/initialized"})
        except requests.RequestException:
            self.session_id = None
            return None

        try:
            listing = self._rpc(path, {"jsonrpc": "2.0", "id": 2,
                                       "method": "tools/list", "params": {}})
            body = self._parse_sse(listing.text)
        except requests.RequestException:
            self.session_id = None
            return None

        result = (body or {}).get("result")
        if isinstance(result, dict) and isinstance(result.get("tools"), list):
            return result["tools"]

        self.session_id = None
        return None

    # -- plain JSON-RPC and REST --------------------------------------

    def _try_jsonrpc(self, path):
        try:
            response = requests.post(
                self.base + path, timeout=self.timeout,
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list",
                      "params": {}})
            if response.status_code != 200:
                return None
            body = response.json()
        except (requests.RequestException, ValueError):
            return None
        result = body.get("result") if isinstance(body, dict) else None
        if isinstance(result, dict) and isinstance(result.get("tools"), list):
            return result["tools"]
        return None

    def _try_rest_list(self):
        for path in ("/tools", "/mcp/tools", "/tools/list"):
            try:
                response = requests.get(self.base + path, timeout=self.timeout)
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

    # -- operations ---------------------------------------------------

    def describe(self):
        if self.style == "streamable":
            return ("streamable-http (MCP SDK) at POST %s%s"
                    % (self.base, self.endpoint))
        if self.style == "jsonrpc":
            return "JSON-RPC 2.0 at POST %s%s" % (self.base, self.endpoint)
        if self.style == "rest":
            return "REST at %s (list GET /tools, call POST %s)" % (
                self.base, self.endpoint)
        return self.error or "transport not discovered"

    def list_tools(self):
        self.discover()
        if self._tools is None:
            raise RuntimeError(self.error or "no tool list available")
        return self._tools

    def call(self, name, arguments, timeout=None):
        """Invoke a tool. Returns (http_status, parsed_body)."""
        self.discover()
        timeout = timeout or self.timeout

        if self.style == "streamable":
            self._next_id += 1
            response = self._rpc(self.endpoint, {
                "jsonrpc": "2.0", "id": self._next_id, "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }, timeout=timeout)
            body = self._parse_sse(response.text)
            return response.status_code, (body if body is not None
                                          else {"_raw": response.text[:400]})

        if self.style == "jsonrpc":
            response = requests.post(
                self.base + self.endpoint, timeout=timeout,
                json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                      "params": {"name": name, "arguments": arguments}})
        elif self.style == "rest":
            response = requests.post(
                self.base + "/invoke", timeout=timeout,
                json={"tool": name, "arguments": arguments})
            if response.status_code == 404:
                response = requests.post(
                    self.base + "/tools/" + name, timeout=timeout,
                    json=arguments)
        else:
            raise RuntimeError(self.error or "no transport")

        try:
            return response.status_code, response.json()
        except ValueError:
            return response.status_code, {"_raw": response.text[:400]}

    @staticmethod
    def payload_of(body):
        """Pull the tool's own result out of whichever envelope it came in.

        streamable-http nests it twice: the JSON-RPC result holds
        content[0].text, and that text is itself a JSON document. A tool
        that returns prose instead of JSON is left as the string it is,
        so the probe that checks for structured data can still fail it.
        """
        if not isinstance(body, dict):
            return body

        if "result" in body:
            inner = body["result"]
            if isinstance(inner, dict) and "content" in inner:
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
    def is_error(status, body):
        """True when the call failed, at any of the three levels it can.

        A streamable-http server answers HTTP 200 even for an unknown
        tool - the failure is `isError` on the JSON-RPC result - and a
        tool's own failure is `success: false` inside its payload. All
        three have to be checked or a failed call reads as a successful
        empty one.
        """
        if status >= 400:
            return True
        if not isinstance(body, dict):
            return False
        if "error" in body:
            return True
        result = body.get("result")
        if isinstance(result, dict) and result.get("isError"):
            return True
        payload = McpTransport.payload_of(body)
        if isinstance(payload, dict) and payload.get("success") is False:
            return True
        return False

    @staticmethod
    def error_text(body):
        """A readable reason out of whichever level reported the failure."""
        if not isinstance(body, dict):
            return str(body)[:200]
        if "error" in body:
            return str(body["error"])[:200]
        payload = McpTransport.payload_of(body)
        if isinstance(payload, dict) and payload.get("error"):
            return str(payload["error"])[:200]
        result = body.get("result")
        if isinstance(result, dict) and result.get("isError"):
            content = result.get("content") or [{}]
            return str(content[0].get("text", result))[:200]
        return str(body)[:200]


def _tool_name(tool):
    if isinstance(tool, str):
        return tool
    if isinstance(tool, dict):
        return tool.get("name") or tool.get("tool") or ""
    return ""


def build_mcp_probes(mcp_url, backend_url, ok, fail, Probe):
    """Return the MCP probe pack. ok/fail/Probe come from loop.py."""

    transport = McpTransport(mcp_url)
    backend = backend_url.rstrip("/")

    def require_transport():
        if transport.discover() is None:
            raise RuntimeError(transport.error)

    def find_order_tool():
        """The Order & Kitchen tool, not somebody else's that reads alike."""
        tools = transport.list_tools()
        by_name = {_tool_name(t).lower(): t for t in tools}

        for wanted in ORDER_TOOL_NAMES:
            if wanted in by_name:
                return by_name[wanted]

        for tool in tools:
            name = _tool_name(tool).lower()
            if any(word in name for word in OTHER_FEATURE_WORDS):
                continue
            if any(hint in name for hint in ORDER_TOOL_HINTS):
                return tool

        return None

    # ---------------- availability ----------------

    def mcp_server_answers():
        started = time.time()
        try:
            health = requests.get(mcp_url.rstrip("/") + "/health", timeout=8)
            health_note = ("health %d" % health.status_code)
        except requests.RequestException:
            health_note = "no /health endpoint"
        require_transport()
        elapsed = time.time() - started
        return ok("%s, %s, discovered in %.0f ms"
                  % (transport.describe(), health_note, elapsed * 1000))

    def mcp_is_not_a_compose_service():
        return must_not_be_containerised(
            "the MCP server", "mcp", ok=ok, fail=fail)

    # ---------------- protocol ----------------

    def tools_are_discoverable():
        require_transport()
        tools = transport.list_tools()
        if not tools:
            return fail("the server answered but advertised no tools")
        names = [_tool_name(t) for t in tools]
        if any(not n for n in names):
            return fail("a tool was advertised without a name")
        if len(set(names)) != len(names):
            return fail("duplicate tool names: %s" % names)
        return ok("%d tool(s) advertised over %s: %s"
                  % (len(tools), transport.style, ", ".join(names)))

    def every_tool_is_described():
        require_transport()
        tools = transport.list_tools()
        undescribed, unschemad = [], []
        for tool in tools:
            name = _tool_name(tool)
            if not isinstance(tool, dict):
                undescribed.append(name)
                continue
            if not str(tool.get("description", "")).strip():
                undescribed.append(name)
            schema = (tool.get("inputSchema") or tool.get("input_schema")
                      or tool.get("parameters"))
            if not isinstance(schema, dict):
                unschemad.append(name)
        problems = []
        if undescribed:
            problems.append("no description: %s" % ", ".join(undescribed))
        if unschemad:
            problems.append("no input schema: %s" % ", ".join(unschemad))
        if problems:
            return fail("a model cannot choose a tool it cannot read - "
                        + "; ".join(problems))
        return ok("all %d tool(s) carry a description and an input schema"
                  % len(tools))

    def an_order_tool_is_exposed():
        require_transport()
        tool = find_order_tool()
        if tool is None:
            return fail("no tool covering orders, the kitchen or the queue "
                        "is advertised, so my feature has nothing to put "
                        "behind its MCP panel (saw: %s)"
                        % ", ".join(_tool_name(t)
                                    for t in transport.list_tools()))
        return ok("Order & Kitchen is reachable through the tool '%s'"
                  % _tool_name(tool))

    # ---------------- invocation ----------------

    def a_tool_call_returns_structured_data():
        require_transport()
        tool = find_order_tool()
        if tool is None:
            return fail("no order tool to call")
        status, body = transport.call(_tool_name(tool), {})
        if transport.is_error(status, body):
            return fail("calling '%s' with no arguments returned an error: "
                        "%r" % (_tool_name(tool), body))
        payload = transport.payload_of(body)
        if isinstance(payload, str):
            return fail("the tool returned a string, not structured data - "
                        "an MCP tool result must be machine-readable: %r"
                        % payload[:120])
        if not isinstance(payload, (dict, list)):
            return fail("the tool returned %s, not an object or a list"
                        % type(payload).__name__)
        size = len(payload)
        return ok("'%s' returned a %s with %d entr%s"
                  % (_tool_name(tool), type(payload).__name__, size,
                     "y" if size == 1 else "ies"))

    def mcp_agrees_with_the_owning_service():
        """The tool and the service that owns the data must say the same thing.

        A tool that is up and well-formed but wrong is the failure no
        other check catches, so the loop asks both and compares.
        """
        require_transport()
        tool = find_order_tool()
        if tool is None:
            return fail("no order tool to cross-check")

        try:
            direct = requests.get(backend + "/api/orders", timeout=10).json()
        except (requests.RequestException, ValueError) as exc:
            return fail("could not read the owning service at %s to compare "
                        "against: %s" % (backend, exc))

        direct_orders = direct if isinstance(direct, list) else \
            direct.get("orders", direct.get("data", []))
        if not isinstance(direct_orders, list):
            return fail("unexpected shape from the backend: %r"
                        % sorted(direct)[:6])

        status, body = transport.call(_tool_name(tool), {})
        if transport.is_error(status, body):
            return fail("the tool errored while the backend answered: %r"
                        % body)
        payload = transport.payload_of(body)
        tool_orders = payload if isinstance(payload, list) else \
            (payload.get("orders", payload.get("data", []))
             if isinstance(payload, dict) else [])

        if not isinstance(tool_orders, list):
            return fail("the tool did not return a list of orders")

        def ids(rows):
            out = set()
            for row in rows:
                if isinstance(row, dict):
                    value = row.get("id", row.get("order_id"))
                    if value is not None:
                        out.add(int(value))
            return out

        backend_ids, tool_ids = ids(direct_orders), ids(tool_orders)
        if not backend_ids:
            return fail("the backend returned no identifiable orders, so "
                        "there is nothing to compare")
        missing = backend_ids - tool_ids
        invented = tool_ids - backend_ids
        if invented:
            return fail("the tool reported order(s) %s that the owning "
                        "service does not have"
                        % sorted(invented)[:5])
        if len(missing) > len(backend_ids) * 0.5:
            return fail("the tool is missing %d of the %d orders the owning "
                        "service reports" % (len(missing), len(backend_ids)))
        return ok("the tool and student-4-backend agree on %d order id(s); "
                  "no invented rows"
                  % len(backend_ids & tool_ids))

    def a_tool_call_is_bounded():
        require_transport()
        tool = find_order_tool()
        if tool is None:
            return fail("no order tool to time")
        started = time.time()
        transport.call(_tool_name(tool), {}, timeout=30)
        elapsed = time.time() - started
        if elapsed > 15:
            return fail("the tool took %.1f s - too slow to sit behind a "
                        "page request" % elapsed)
        return ok("responded in %.0f ms" % (elapsed * 1000))

    # ---------------- resilience ----------------

    def unknown_tool_is_refused_cleanly():
        require_transport()
        status, body = transport.call("student_4_no_such_tool_xyz", {})
        if not transport.is_error(status, body):
            return fail("an unknown tool name was accepted and returned %r"
                        % body)
        if status >= 500:
            return fail("an unknown tool name crashed the server with HTTP "
                        "%d - it should be a refusal, not a fault" % status)
        return ok("refused rather than crashed (HTTP %d): %s"
                  % (status, transport.error_text(body)[:110]))

    def bad_arguments_are_refused_cleanly():
        require_transport()
        tool = find_order_tool()
        if tool is None:
            return fail("no order tool to send bad arguments to")
        status, body = transport.call(
            _tool_name(tool), {"order_id": "not-a-number", "limit": -1})
        if status >= 500:
            return fail("bad arguments caused HTTP %d - the server should "
                        "validate its input, not fault on it" % status)
        return ok("bad arguments produced HTTP %d rather than a 500"
                  % status)

    def mcp_does_not_reach_past_the_owning_service():
        """An MCP tool must call the service that owns the data, not its file.

        Checked against the source on disk, the same way the Release 0
        loop checks that my backend never opens SQLite.
        """
        candidates = []
        for root in ("ai-services", "shared", "mcp"):
            directory = os.path.join(REPO_ROOT, root)
            if not os.path.isdir(directory):
                continue
            for dirpath, _dirnames, filenames in os.walk(directory):
                if "mcp" not in dirpath.lower() and root != "mcp":
                    continue
                for filename in filenames:
                    if filename.endswith(".py"):
                        candidates.append(os.path.join(dirpath, filename))

        if not candidates:
            return fail("no MCP server source found under ai-services/, "
                        "shared/ or mcp/ - cannot check how it reads data")

        offenders = []
        for path in candidates:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                source = handle.read()
            if re.search(r"^\s*import\s+sqlite3", source, re.M) or \
               re.search(r"\.db[\"']", source):
                offenders.append(os.path.relpath(path, REPO_ROOT))

        if offenders:
            return fail("the MCP server opens a database directly in %s - "
                        "it must go through the owning service's HTTP API"
                        % ", ".join(offenders))
        return ok("%d MCP source file(s) checked, none opens a database "
                  "directly" % len(candidates))

    def backend_outage_is_reported_not_faked():
        """Point a tool at an order that cannot exist.

        Whatever the server does, it must not answer as if the data were
        there. A clean 'not found' and a clean error are both correct; a
        confident empty success is not.
        """
        require_transport()
        tool = find_order_tool()
        if tool is None:
            return fail("no order tool to test")
        status, body = transport.call(_tool_name(tool), {"order_id": 999999})
        if status >= 500:
            return fail("a missing order faulted the server with HTTP %d"
                        % status)
        if transport.is_error(status, body):
            return ok("a missing order was reported as an error, not "
                      "invented (HTTP %d)" % status)
        payload = transport.payload_of(body)
        if isinstance(payload, dict) and payload.get("id") in (999999,
                                                               "999999"):
            return fail("the tool returned an order 999999 that does not "
                        "exist")
        return ok("a missing order produced an empty result rather than an "
                  "invented one")

    return [
        Probe("mcp_reachable", "availability",
              "MCP server answers and its transport is known",
              mcp_server_answers),
        Probe("mcp_not_containerised", "availability",
              "MCP server is not a Compose service",
              mcp_is_not_a_compose_service),

        Probe("mcp_tools_listed", "protocol",
              "A tool list is discoverable", tools_are_discoverable),
        Probe("mcp_tools_described", "protocol",
              "Every tool has a description and a schema",
              every_tool_is_described),
        Probe("mcp_order_tool", "protocol",
              "An Order & Kitchen tool is exposed",
              an_order_tool_is_exposed),

        Probe("mcp_structured_result", "invocation",
              "A tool call returns structured data",
              a_tool_call_returns_structured_data),
        Probe("mcp_agrees_with_owner", "invocation",
              "The tool agrees with the owning service",
              mcp_agrees_with_the_owning_service),
        Probe("mcp_bounded", "invocation",
              "A tool call finishes inside 15 s",
              a_tool_call_is_bounded),

        Probe("mcp_unknown_tool", "resilience",
              "Unknown tool names are refused cleanly",
              unknown_tool_is_refused_cleanly),
        Probe("mcp_bad_arguments", "resilience",
              "Bad arguments are refused cleanly",
              bad_arguments_are_refused_cleanly),
        Probe("mcp_no_direct_db", "resilience",
              "MCP does not reach past the owning service",
              mcp_does_not_reach_past_the_owning_service),
        Probe("mcp_missing_data", "resilience",
              "Missing data is reported, not invented",
              backend_outage_is_reported_not_faked),
    ]
