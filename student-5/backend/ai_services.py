"""Clients for the shared Release 1 MCP and RAG services.

Both services run on the host outside Docker Compose. These clients never
invent fallback answers: an outage is returned as structured data so the
Student 5 page can remain usable and explain what is unavailable.
"""

import json
import os
import time

import requests


MCP_URL = os.getenv("MCP_URL", "http://localhost:5700").rstrip("/")
RAG_URL = os.getenv("RAG_URL", "http://localhost:5600").rstrip("/")
MCP_TIMEOUT = float(os.getenv("MCP_TIMEOUT", "15"))
RAG_TIMEOUT = float(os.getenv("RAG_TIMEOUT", "120"))


class McpClient:
    """Small MCP Streamable HTTP client for listing and calling tools."""

    def __init__(self, base_url=MCP_URL, timeout=MCP_TIMEOUT):
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()
        self.session_id = None
        self.tools = None
        self.next_id = 10

    @staticmethod
    def _parse(text):
        for line in text.splitlines():
            if line.startswith("data:"):
                text = line[5:].strip()
                break
        try:
            return json.loads(text)
        except (TypeError, ValueError):
            return None

    def _headers(self):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        return headers

    def _post(self, payload):
        return self.session.post(
            self.base_url + "/mcp",
            headers=self._headers(),
            json=payload,
            timeout=self.timeout,
        )

    def _discover(self):
        if self.tools is not None:
            return True

        try:
            response = self._post({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "student-5-backend",
                        "version": "1.0",
                    },
                },
            })
            if response.status_code >= 300:
                return False

            self.session_id = response.headers.get("Mcp-Session-Id")
            if not self.session_id:
                return False

            self._post({
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            })
            listing = self._post({
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            })
            body = self._parse(listing.text) or {}
            tools = body.get("result", {}).get("tools")
            if listing.status_code == 200 and isinstance(tools, list):
                self.tools = tools
                return True
        except requests.RequestException:
            return False

        return False

    def list_tools(self):
        if not self._discover():
            return [], (
                f"The shared MCP server is not answering on {self.base_url}."
            )
        return self.tools, None

    @staticmethod
    def _tool_name(tool):
        return tool.get("name", "") if isinstance(tool, dict) else str(tool)

    @staticmethod
    def _unwrap(body):
        result = body.get("result", {}) if isinstance(body, dict) else {}
        content = result.get("content") if isinstance(result, dict) else None
        if isinstance(content, list) and content:
            text = content[0].get("text") if isinstance(content[0], dict) else None
            if text is not None:
                try:
                    return json.loads(text)
                except (TypeError, ValueError):
                    return text
        return result

    @staticmethod
    def _rows(payload):
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            for key in ("payments", "refunds", "rows", "data"):
                if isinstance(payload.get(key), list):
                    return payload[key]
            return [payload]
        return []

    def call(self, tool_name, arguments):
        tools, reason = self.list_tools()
        if reason:
            return {
                "status": "unavailable",
                "available": False,
                "reason": reason,
                "tools": [],
            }

        selected = next(
            (tool for tool in tools if self._tool_name(tool) == tool_name),
            None,
        )
        if selected is None:
            return {
                "status": "not_registered",
                "available": True,
                "reason": f"The MCP server does not register {tool_name!r}.",
                "tools": [self._tool_name(tool) for tool in tools],
            }

        started = time.time()
        self.next_id += 1
        try:
            response = self._post({
                "jsonrpc": "2.0",
                "id": self.next_id,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            })
            body = self._parse(response.text)
        except requests.RequestException as exc:
            return {
                "status": "unavailable",
                "available": False,
                "reason": f"The MCP tool call failed: {exc}",
            }

        if not isinstance(body, dict):
            return {
                "status": "unavailable",
                "available": False,
                "reason": "The MCP server returned unreadable data.",
            }

        result = body.get("result", {})
        if response.status_code >= 400 or body.get("error") or result.get("isError"):
            return {
                "status": "tool_error",
                "available": True,
                "tool": tool_name,
                "reason": str(body.get("error") or result),
            }

        payload = self._unwrap(body)
        rows = self._rows(payload)
        columns = []
        for row in rows:
            for key, value in row.items():
                if not isinstance(value, (dict, list)) and key not in columns:
                    columns.append(key)

        return {
            "status": "success",
            "available": True,
            "tool": tool_name,
            "arguments": arguments,
            "elapsed_ms": round((time.time() - started) * 1000),
            "row_count": len(rows),
            "columns": columns[:8],
            "rows": rows[:25],
            "raw": payload,
        }


class RagClient:
    """Calls the shared RAG /query endpoint and preserves its evidence."""

    def __init__(self, base_url=RAG_URL, timeout=RAG_TIMEOUT):
        self.base_url = base_url
        self.timeout = timeout

    def ask(self, question):
        try:
            response = requests.post(
                self.base_url + "/query",
                json={"question": question},
                timeout=self.timeout,
            )
            body = response.json()
        except (requests.RequestException, ValueError) as exc:
            return {
                "status": "unavailable",
                "answer": None,
                "sources": [],
                "confidence": None,
                "reason": (
                    f"The shared RAG server is not answering on "
                    f"{self.base_url}: {exc}"
                ),
            }

        if response.status_code >= 400:
            return {
                "status": "unavailable",
                "answer": None,
                "sources": [],
                "confidence": None,
                "reason": body.get("error", "The RAG request failed."),
            }

        return body
