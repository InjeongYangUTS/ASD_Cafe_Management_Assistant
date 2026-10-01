"""Release 1 local integration validation: shared MCP/RAG servers and every feature backend.

Run from the repository root with the shared servers and `docker compose up` running:

    python scripts/validate_integration.py
    python scripts/validate_integration.py --students 1 3

Writes evidence/release1/validation-<timestamp>.md and .json.
"""

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime

MCP_URL = os.environ.get("MCP_URL", "http://127.0.0.1:5700").rstrip("/")
RAG_URL = os.environ.get("RAG_URL", "http://127.0.0.1:5600").rstrip("/")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")

OUT_OF_SCOPE = "What is the capital city of France?"

# One row per feature. Leave "mcp" or "rag" as None until that student's route exists.
STUDENTS = {
    1: {"feature": "Customer Feedback & Reviews", "owner": "Hangyeol Yi",
        "health": "http://127.0.0.1:8100/api/health",
        "mcp": ("POST", "http://127.0.0.1:8100/api/ai/mcp",
                {"tool": "get_top_issues", "arguments": {"limit": 3}}),
        "rag": ("http://127.0.0.1:8100/api/ai/rag", "How is review sentiment classified?"),
        "mcp_tools": ["get_menu_item_feedback", "get_top_issues", "get_reviews_needing_reply"]},
    2: {"feature": "Menu & Recipe", "owner": "Ei Thandar",
        "health": "http://127.0.0.1:5201/api/menus",
        "mcp": None,
        "rag": ("http://127.0.0.1:5201/api/rag/query", "What does the Menu and Recipe feature manage?"),
        "mcp_tools": ["get_menus", "get_menu", "get_menu_price", "get_ingredients",
                      "get_ingredient", "get_recipes", "get_recipe", "get_recipe_ingredients"]},
    3: {"feature": "Inventory & Restocking", "owner": "Injeong Yang",
        "health": "http://127.0.0.1:8300/api/health",
        "mcp": ("GET", "http://127.0.0.1:8300/api/mcp/test", None),
        "rag": ("http://127.0.0.1:8300/api/rag/query", "What does the Inventory feature manage?"),
        "mcp_tools": ["get_inventory_items", "get_low_stock_items", "get_inventory_item",
                      "get_suppliers", "get_restock_orders"]},
    4: {"feature": "Order & Kitchen Management", "owner": "Stella Kwon",
        "health": "http://127.0.0.1:8400/api/health",
        "mcp": ("POST", "http://127.0.0.1:8400/api/ai/mcp", {}),
        "rag": ("http://127.0.0.1:8400/api/ai/rag", "What does the Order and Kitchen feature manage?"),
        "mcp_tools": ["get_orders", "get_order", "get_kitchen_queue", "get_order_status"]},
    5: {"feature": "Payment & Billing", "owner": "Ong Ath Vongnathi",
        "health": "http://127.0.0.1:8500/health",
        "mcp": None, "rag": None, "mcp_tools": []},
}

PASS, FAIL, NOT_READY = "PASS", "FAIL", "NOT READY"


def http(method, url, body=None, headers=None, timeout=15):
    """Return (status, parsed body or text, response headers, elapsed ms); status 0 when unreachable."""
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json", **(headers or {})})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status, raw, head = response.status, response.read().decode(), response.headers
    except urllib.error.HTTPError as exc:
        status, raw, head = exc.code, exc.read().decode(errors="replace"), exc.headers
    except (urllib.error.URLError, OSError) as exc:
        return 0, str(getattr(exc, "reason", exc)), {}, round((time.monotonic() - started) * 1000)

    elapsed = round((time.monotonic() - started) * 1000)
    for line in raw.splitlines():
        if line.startswith("data:"):
            raw = line[5:].strip()
            break
    try:
        return status, json.loads(raw), head, elapsed
    except ValueError:
        return status, raw, head, elapsed


def mcp_tool_names():
    headers = {"Accept": "application/json, text/event-stream"}
    status, _body, head, _ = http("POST", MCP_URL + "/mcp", {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                   "clientInfo": {"name": "validate_integration", "version": "1"}}}, headers)
    if status != 200:
        return status, []
    session = head.get("Mcp-Session-Id")
    if session:
        headers["Mcp-Session-Id"] = session
    http("POST", MCP_URL + "/mcp", {"jsonrpc": "2.0", "method": "notifications/initialized"}, headers)
    status, body, _, _ = http("POST", MCP_URL + "/mcp",
                              {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers)
    tools = body.get("result", {}).get("tools", []) if isinstance(body, dict) else []
    return status, [tool["name"] for tool in tools]


class Report:

    def __init__(self):
        self.rows = []

    def add(self, section, check, expected, actual, result):
        self.rows.append({"section": section, "check": check, "expected": expected,
                          "actual": actual, "result": result})
        print("  %-10s %-44s %s" % (result, check, actual))

    def section(self, title):
        print("\n" + title)


def check_shared(report, tools):
    report.section("Shared local services")
    for name, url in (("Ollama", OLLAMA_URL + "/api/tags"), ("RAG server", RAG_URL + "/health"),
                      ("MCP server /health", MCP_URL + "/health")):
        status, _, _, ms = http("GET", url, timeout=5)
        report.add("Shared", "%s responds" % name, "200", "%s in %dms" % (status or "unreachable", ms),
                   PASS if status == 200 else FAIL)

    report.add("Shared", "MCP tools/list", "tools registered", "%d tools" % len(tools),
               PASS if tools else FAIL)

    status, body, _, ms = http("POST", RAG_URL + "/query", {"question": OUT_OF_SCOPE}, timeout=60)
    got = body.get("status") if isinstance(body, dict) else status
    report.add("Shared", "RAG out-of-scope question", "insufficient_context", "%s in %dms" % (got, ms),
               PASS if got == "insufficient_context" else FAIL)

    compose = open("docker-compose.yml", encoding="utf-8").read()
    block = compose.split("\nservices:", 1)[1]
    block = re.split(r"^\S", block, maxsplit=1, flags=re.M)[0]
    services = re.findall(r"^  ([\w-]+):\s*$", block, re.M)
    local_only = [s for s in services if re.search(r"ollama|mcp|rag|agentic", s)]
    report.add("Shared", "AI-Mode/MCP/RAG not Compose services", "none",
               ", ".join(local_only) or "none", FAIL if local_only else PASS)


def check_student(report, number, spec, tools):
    section = "Student %d - %s" % (number, spec["feature"])
    report.section(section)

    status, _, _, ms = http("GET", spec["health"], timeout=5)
    report.add(section, "Backend responds", "200", "%s in %dms" % (status or "unreachable", ms),
               PASS if status == 200 else FAIL)

    registered = [name for name in spec["mcp_tools"] if name in tools]
    report.add(section, "Own tools on shared MCP server", "at least 1",
               ", ".join(registered) or "none", PASS if registered else NOT_READY)

    if spec["mcp"] is None:
        report.add(section, "MCP through backend", "structured result", "route not built yet", NOT_READY)
    else:
        method, url, body = spec["mcp"]
        status, data, _, ms = http(method, url, body, timeout=30)
        ok = status == 200 and isinstance(data, dict) and (data.get("ok") or data.get("success"))
        rows = data.get("row_count", data.get("count")) if isinstance(data, dict) else None
        report.add(section, "MCP through backend", "200 + result",
                   "%s, %s rows in %dms" % (status or "unreachable", rows, ms),
                   PASS if ok else (NOT_READY if status == 404 else FAIL))

    if spec["rag"] is None:
        report.add(section, "RAG grounded answer", "sources + confidence", "route not built yet", NOT_READY)
        report.add(section, "RAG insufficient context", "insufficient_context", "route not built yet", NOT_READY)
        return

    url, question = spec["rag"]
    status, data, _, ms = http("POST", url, {"question": question}, timeout=240)
    if status == 404:
        report.add(section, "RAG grounded answer", "sources + confidence", "404, route not deployed", NOT_READY)
        report.add(section, "RAG insufficient context", "insufficient_context", "404, route not deployed", NOT_READY)
        return
    data = data if isinstance(data, dict) else {}
    confidence = str(data.get("confidence") or "").lower()
    answered = data.get("status") == "success" or (data.get("success") and not data.get("insufficient_context"))
    grounded = answered and data.get("sources") and confidence not in ("", "insufficient", "unknown")
    report.add(section, "RAG grounded answer", "sources + confidence",
               "%s, %s, %d sources in %dms" % (status, confidence or None,
                                               len(data.get("sources") or []), ms),
               PASS if grounded else FAIL)

    status, data, _, ms = http("POST", url, {"question": OUT_OF_SCOPE}, timeout=60)
    data = data if isinstance(data, dict) else {}
    insufficient = (data.get("status") == "insufficient_context" or data.get("insufficient_context") is True
                    or str(data.get("confidence") or "").lower() == "insufficient")
    report.add(section, "RAG insufficient context", "insufficient_context",
               "%s, %s in %dms" % (status, data.get("status") or data.get("confidence"), ms),
               PASS if insufficient else FAIL)


def save(report):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    folder = os.path.join("evidence", "release1")
    os.makedirs(folder, exist_ok=True)
    base = os.path.join(folder, "validation-%s" % stamp)

    counts = {r: sum(row["result"] == r for row in report.rows) for r in (PASS, FAIL, NOT_READY)}
    lines = ["# Release 1 Integration Validation", "",
             "Run: %s  " % datetime.now().strftime("%d %b %Y %H:%M"),
             "Result: %d PASS, %d FAIL, %d NOT READY" % (counts[PASS], counts[FAIL], counts[NOT_READY]),
             "", "| Check | Expected | Actual | Pass/Fail |", "|---|---|---|---|"]
    section = None
    for row in report.rows:
        if row["section"] != section:
            section = row["section"]
            lines.append("| **%s** | | | |" % section)
        lines.append("| %s | %s | %s | %s |" % (row["check"], row["expected"], row["actual"], row["result"]))

    with open(base + ".md", "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    with open(base + ".json", "w", encoding="utf-8") as handle:
        json.dump(report.rows, handle, indent=2)

    print("\n%d PASS, %d FAIL, %d NOT READY" % (counts[PASS], counts[FAIL], counts[NOT_READY]))
    print("Saved %s.md" % base)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--students", type=int, nargs="*", default=sorted(STUDENTS))
    args = parser.parse_args()

    report = Report()
    _, tools = mcp_tool_names()
    check_shared(report, tools)
    for number in args.students:
        check_student(report, number, STUDENTS[number], tools)
    save(report)


if __name__ == "__main__":
    main()
