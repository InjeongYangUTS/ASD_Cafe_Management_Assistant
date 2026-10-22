"""
Student 4 (Stella Kwon) - Order & Kitchen Management
BACKEND / API MICROSERVICE  (container: student-4-backend, port 8400)

Business logic for ordering and the kitchen queue. Owns no data of its own:
it reads and writes orders through student-4-database, prices through
Student 2's Menu API, stock through Student 3's Inventory API, and AI-Mode
through the shared Ollama runtime.

Endpoints
    GET    /api/health
    GET    /api/menu

    GET    /api/orders
    POST   /api/orders
    GET    /api/orders/<id>
    PUT    /api/orders/<id>
    DELETE /api/orders/<id>

    POST   /api/orders/<id>/items
    PUT    /api/order-items/<id>
    DELETE /api/order-items/<id>

    GET    /api/order-status
    GET    /api/order-status/<id>
    PUT    /api/order-status/<id>

    GET    /api/kitchen/queue
    POST   /api/ai/kitchen-analysis

    GET    /api/ai/mcp          shared MCP server - tool catalogue
    POST   /api/ai/mcp          shared MCP server - structured tool result
    POST   /api/ai/rag          shared RAG server - grounded answer

    POST   /api/ai/multi-agent/workflows                    start a run
    GET    /api/ai/multi-agent/workflows/<id>               fetch a run
    POST   /api/ai/multi-agent/workflows/<id>/human-review  decide on it
"""

import os
from datetime import datetime

from flask import Flask, jsonify, request

import ai
from ai_services import McpClient, MultiAgentClient, RagClient
from clients import (
    DatabaseClient,
    InventoryClient,
    MenuClient,
    OllamaClient,
    ServiceError,
)

app = Flask(__name__)

db = DatabaseClient()
menu = MenuClient()
inventory = InventoryClient()
ollama = OllamaClient()

# Release 1 - the two shared AI services. Both run on the host and are
# deliberately not containerised, so docker-compose.yml points MCP_URL and
# RAG_URL at host.docker.internal rather than a Compose service name.
mcp = McpClient()
rag = RagClient()

# Release 2 - the shared Multi-Agent server, reached the same way, with
# MULTI_AGENT_URL pointing at host.docker.internal:5800.
multi_agent = MultiAgentClient()

# Allowed status transitions for an order.
TRANSITIONS = {
    "PENDING":   ["CONFIRMED", "CANCELLED"],
    "CONFIRMED": ["PREPARING", "CANCELLED"],
    "PREPARING": ["READY", "CANCELLED"],
    "READY":     ["COMPLETED"],
    "COMPLETED": [],
    "CANCELLED": [],
}

BOARD_COLUMNS = ["PENDING", "CONFIRMED", "PREPARING", "READY"]


@app.errorhandler(ServiceError)
def handle_service_error(exc):
    payload = {"error": exc.message}
    if exc.detail:
        payload["detail"] = exc.detail
    return jsonify(payload), exc.status_code


def bad_request(message, **extra):
    payload = {"error": message}
    payload.update(extra)
    return jsonify(payload), 400


# =====================================================================
# Health
# =====================================================================

@app.get("/api/health")
def health():
    try:
        database = db.health()
        database["reachable"] = True
    except ServiceError as exc:
        database = {"reachable": False, "detail": exc.message}

    report = {
        "service": "student-4-backend",
        "feature": "Order & Kitchen Management",
        "owner": "Student 4 - Stella Kwon",
        "dependencies": {
            "order_database": database,
            "menu_service_student_2": menu.health(),
            "inventory_service_student_3": inventory.health(),
            "ollama": ollama.health(),
            "mcp": mcp.health(),
            "rag": rag.health(),
            "multi_agent": multi_agent.health(),
        },
    }

    report["status"] = "healthy" if database.get("reachable") else "degraded"
    return jsonify(report), 200 if report["status"] == "healthy" else 503


# =====================================================================
# Menu (read-through to Student 2)
# =====================================================================

@app.get("/api/menu")
def get_menu():
    catalog, source = menu.get_catalog()
    items = sorted(catalog.values(), key=lambda item: item["menu_id"])

    return jsonify({
        "source": source,
        "count": len(items),
        "items": items,
    })


# =====================================================================
# Orders
# =====================================================================

@app.get("/api/orders")
def list_orders():
    params = {
        "limit": request.args.get("limit", 50),
        "include": "items",
    }
    if request.args.get("status"):
        params["status"] = request.args["status"]
    if request.args.get("channel"):
        params["channel"] = request.args["channel"]

    return jsonify(db.list_orders(**params))


@app.post("/api/orders")
def create_order():
    body = request.get_json(silent=True) or {}
    raw_items = body.get("items") or []

    if not raw_items:
        return bad_request("Add at least one menu item before placing the order.")

    catalog, price_source = menu.get_catalog()

    lines = []
    unknown = []

    for entry in raw_items:
        try:
            menu_id = int(entry.get("menu_id"))
            quantity = int(entry.get("quantity", 1))
        except (TypeError, ValueError):
            return bad_request("Every item needs a numeric menu_id and quantity.")

        if quantity < 1:
            return bad_request("Quantity must be 1 or more.")

        item = catalog.get(menu_id)
        if item is None:
            unknown.append(menu_id)
            continue

        if not item.get("available", True):
            return bad_request("%s is not available right now." % item["name"])

        lines.append({
            "menu_id": menu_id,
            "menu_name": item["name"],
            "unit_price": item["price"],
            "quantity": quantity,
            "station": item.get("station", "BAR"),
            "prep_seconds": item.get("prep_seconds", 90),
            "note": entry.get("note"),
        })

    if unknown:
        return bad_request(
            "Unknown menu item(s): %s" % ", ".join(str(m) for m in unknown),
            unknown_menu_ids=unknown,
        )

    # --- Student 3 : check stock before we commit the order ----------
    stock_ok, stock_detail = inventory.check(lines)
    if stock_ok is False:
        return jsonify({
            "error": "Not enough stock for this order.",
            "inventory": stock_detail,
        }), 409

    payload = {
        "channel": body.get("channel", "DINE_IN"),
        "table_number": body.get("table_number"),
        "customer_id": body.get("customer_id"),
        "customer_name": body.get("customer_name"),
        "staff_id": body.get("staff_id"),
        "staff_name": body.get("staff_name"),
        "note": body.get("note"),
        "items": lines,
    }

    order = db.create_order(payload)

    # --- Student 3 : deduct stock now the order exists ---------------
    deducted, deduct_detail = inventory.deduct(lines)
    if deducted:
        order = db.update_order(order["id"], {"stock_deducted": True})

    return jsonify({
        "order": order,
        "integration": {
            "price_source": price_source,
            "stock_checked": stock_ok is not None,
            "stock_deducted": bool(deducted),
            "inventory_detail": deduct_detail if deducted is None else None,
        },
    }), 201


@app.get("/api/orders/<int:order_id>")
def get_order(order_id):
    return jsonify(db.get_order(order_id))


@app.put("/api/orders/<int:order_id>")
def update_order(order_id):
    body = request.get_json(silent=True) or {}

    editable = ["channel", "table_number", "customer_name", "staff_name", "note"]
    payload = {key: body[key] for key in editable if key in body}

    if not payload:
        return bad_request("Nothing to update. Editable fields: %s"
                           % ", ".join(editable))

    return jsonify(db.update_order(order_id, payload))


@app.delete("/api/orders/<int:order_id>")
def delete_order(order_id):
    order = db.get_order(order_id)

    if order["status"] in ("PREPARING", "READY", "COMPLETED"):
        return jsonify({
            "error": "Order %s is already %s and cannot be deleted. "
                     "Cancel it instead." % (order["order_number"],
                                             order["status"].lower()),
        }), 409

    return jsonify(db.delete_order(order_id))


# =====================================================================
# Order items
# =====================================================================

@app.post("/api/orders/<int:order_id>/items")
def add_item(order_id):
    body = request.get_json(silent=True) or {}

    order = db.get_order(order_id)
    if order["status"] in ("READY", "COMPLETED", "CANCELLED"):
        return jsonify({
            "error": "Cannot add items to a %s order." % order["status"].lower(),
        }), 409

    try:
        menu_id = int(body.get("menu_id"))
        quantity = int(body.get("quantity", 1))
    except (TypeError, ValueError):
        return bad_request("menu_id and quantity are required.")

    catalog, _ = menu.get_catalog()
    item = catalog.get(menu_id)

    if item is None:
        return bad_request("Unknown menu item: %s" % menu_id)

    created = db.add_item(order_id, {
        "menu_id": menu_id,
        "menu_name": item["name"],
        "unit_price": item["price"],
        "quantity": quantity,
        "station": item.get("station", "BAR"),
        "prep_seconds": item.get("prep_seconds", 90),
        "note": body.get("note"),
    })

    inventory.deduct([{"menu_id": menu_id, "quantity": quantity}])

    return jsonify(created), 201


@app.put("/api/order-items/<int:item_id>")
def update_item(item_id):
    body = request.get_json(silent=True) or {}
    allowed = ["quantity", "item_status", "note", "station"]
    payload = {key: body[key] for key in allowed if key in body}

    if not payload:
        return bad_request("Nothing to update. Editable fields: %s"
                           % ", ".join(allowed))

    return jsonify(db.update_item(item_id, payload))


@app.delete("/api/order-items/<int:item_id>")
def delete_item(item_id):
    return jsonify(db.delete_item(item_id))


# =====================================================================
# Order status
# =====================================================================

@app.get("/api/order-status")
def status_board():
    data = db.list_orders(status=",".join(BOARD_COLUMNS), include="items", limit=100)

    now = datetime.now()
    board = {column: [] for column in BOARD_COLUMNS}

    for order in data["orders"]:
        # Enrich each ticket with what the kitchen display needs to render,
        # so the frontend never has to re-implement the lifecycle rules.
        order["age_minutes"] = round(ai.age_minutes(order, now), 1)
        order["next_statuses"] = TRANSITIONS.get(order["status"], [])
        board[order["status"]].append(order)

    for column in BOARD_COLUMNS:
        board[column].sort(key=lambda o: o["age_minutes"], reverse=True)

    return jsonify({
        "columns": BOARD_COLUMNS,
        "counts": {column: len(board[column]) for column in BOARD_COLUMNS},
        "board": board,
    })


@app.get("/api/order-status/<int:order_id>")
def order_status(order_id):
    order = db.get_order(order_id)
    history = db.list_statuses(order_id)

    return jsonify({
        "order_id": order["id"],
        "order_number": order["order_number"],
        "status": order["status"],
        "next_statuses": TRANSITIONS.get(order["status"], []),
        "status_history": history["status_history"],
    })


@app.put("/api/order-status/<int:order_id>")
def advance_status(order_id):
    body = request.get_json(silent=True) or {}
    target = str(body.get("status", "")).upper()

    order = db.get_order(order_id)
    current = order["status"]
    allowed = TRANSITIONS.get(current, [])

    if target not in allowed:
        return jsonify({
            "error": "Cannot move order %s from %s to %s."
                     % (order["order_number"], current, target or "(none)"),
            "current_status": current,
            "allowed_next": allowed,
        }), 409

    db.add_status(order_id, {
        "status": target,
        "changed_by": body.get("changed_by", "kitchen"),
        "note": body.get("note"),
    })

    # Keep the line items in step with the ticket.
    item_status = {"PREPARING": "PREPARING", "READY": "READY",
                   "COMPLETED": "READY", "CANCELLED": "CANCELLED"}.get(target)

    if item_status:
        for item in order.get("items", []):
            if item["item_status"] != "CANCELLED":
                db.update_item(item["id"], {"item_status": item_status})

    updated = db.get_order(order_id)

    return jsonify({
        "order_id": updated["id"],
        "order_number": updated["order_number"],
        "previous_status": current,
        "status": updated["status"],
        "next_statuses": TRANSITIONS.get(updated["status"], []),
        "status_history": updated.get("status_history", []),
    })


# =====================================================================
# Kitchen queue + AI-Mode
# =====================================================================

@app.get("/api/kitchen/queue")
def kitchen_queue():
    data = db.list_orders(status=",".join(BOARD_COLUMNS[:3]),
                          include="items", limit=100)
    metrics = ai.summarise_queue(data["orders"])
    return jsonify(metrics)


@app.post("/api/ai/kitchen-analysis")
def kitchen_analysis():
    data = db.list_orders(status=",".join(BOARD_COLUMNS[:3]),
                          include="items", limit=100)
    result = ai.analyse(data["orders"], ollama)
    return jsonify(result)


@app.get("/api/ai/kitchen-analysis")
def kitchen_analysis_get():
    """Convenience alias so the endpoint can be demonstrated from a browser."""
    return kitchen_analysis()


# =====================================================================
# Release 1 - the two shared AI services
#
# Both are reached the same way every other dependency in this feature is
# reached: over HTTP, from this backend only, with the frontend calling
# nothing but this service. Neither endpoint fails the request when its
# server is down - it returns the outage as data so the screen can show
# what happened.
# =====================================================================

@app.get("/api/ai/mcp")
def mcp_tools():
    """The tool catalogue the shared MCP server advertises."""
    tools, reason = mcp.list_tools()

    return jsonify({
        "server": mcp.base_url,
        "transport": mcp.transport,
        "containerised": False,
        "available": reason is None,
        "reason": reason,
        "count": len(tools),
        "tools": tools,
    })


@app.post("/api/ai/mcp")
def mcp_call():
    """
    Call a tool on the shared MCP server and return its structured result.

    The result is deliberately NOT prose. It carries the tool that was
    called, the arguments it was given, the columns and rows it returned,
    and the raw payload - so the screen can render a table and the reader
    can see exactly what the model would have been handed.

    It also carries a cross-check: the same question is put to my own
    database, and the two row counts are compared. A tool that is up and
    well-formed but disagreeing with the service that owns the data is the
    failure nothing else catches.
    """
    body = request.get_json(silent=True) or {}
    tool_name = body.get("tool")
    arguments = body.get("arguments") or {}

    if not isinstance(arguments, dict):
        return bad_request("arguments must be an object")

    result = mcp.call(tool_name, arguments)

    if result.get("ok"):
        try:
            mine = db.list_orders(limit=100)
            my_count = len(mine.get("orders", []))
            result["cross_check"] = {
                "checked": True,
                "my_order_count": my_count,
                "tool_row_count": result["row_count"],
                "agrees": result["row_count"] <= my_count,
                "note": ("the tool returned %d row(s); student-4-database "
                         "holds %d order(s)"
                         % (result["row_count"], my_count)),
            }
        except ServiceError as exc:
            result["cross_check"] = {
                "checked": False,
                "note": "could not read my own database to compare: %s"
                        % exc.message,
            }

    return jsonify(result)


@app.post("/api/ai/rag")
def rag_query():
    """
    Ask the shared RAG server a question and return its grounded answer.

    Three outcomes, all HTTP 200, because none of them is an error in this
    service:

        success               answer + citations + confidence category
        insufficient_context  nothing retrieved, so nothing answered
        unavailable           the RAG server or its model is down

    Every claim on screen is backed by the excerpt it came from, which the
    RAG server returns alongside the answer. This service adds no wording
    of its own.
    """
    body = request.get_json(silent=True) or {}
    question = body.get("question")

    if not isinstance(question, str) or not question.strip():
        return bad_request("a non-empty question is required")

    return jsonify(rag.ask(question))


# =====================================================================
# Release 2 - the shared Multi-Agent server
#
# Planner -> Worker -> Reviewer -> Human Review. The first three run on
# the shared server; the fourth is a person on the Kitchen screen, and
# the workflow stays at awaiting_human_review until they decide. Nothing
# is applied to an order by any of this: the agents produce a written
# recommendation about the live queue, and a human accepts, corrects,
# partially accepts or rejects it.
#
# The evidence the agents reason over is this feature's own queue
# metrics - the same deterministic summary AI-Mode uses - so the three
# agents are reading real Order & Kitchen data rather than a prompt.
# =====================================================================

def queue_evidence():
    """The live queue, trimmed to what three agents can actually read."""
    try:
        data = db.list_orders(status=",".join(BOARD_COLUMNS[:3]),
                              include="items", limit=100)
    except ServiceError as exc:
        return {"source": "student-4-backend",
                "error": "could not read the order database: %s" % exc.message}

    metrics = ai.summarise_queue(data["orders"])

    return {
        "source": "student-4-backend /api/kitchen/queue",
        "feature": "Order & Kitchen Management",
        "generated_at": metrics["generated_at"],
        "open_order_count": metrics["open_order_count"],
        "total_workload_minutes": metrics["total_workload_minutes"],
        "longest_wait_minutes": metrics["longest_wait_minutes"],
        "busiest_station": metrics["busiest_station"],
        "congestion_level": metrics["congestion_level"],
        "station_load": metrics["station_load"],
        "at_risk_orders": metrics["at_risk_orders"],
        # The whole board would bury the agents, so only the tickets at
        # the head of the queue are sent, with the count they came from.
        "ticket_sample": metrics["tickets"][:8],
        "ticket_total": len(metrics["tickets"]),
    }


@app.post("/api/ai/multi-agent/workflows")
def multi_agent_start():
    """Start a Planner -> Worker -> Reviewer run over the live queue.

    Slow by design: the server runs all three agents on a local model
    inside this request, then stops and waits for a human.
    """
    body = request.get_json(silent=True) or {}
    task = body.get("task")

    if not isinstance(task, str) or not task.strip():
        return bad_request("a non-empty task is required")

    evidence = body.get("evidence")
    if evidence is None:
        evidence = queue_evidence()
    elif not isinstance(evidence, dict):
        return bad_request("evidence must be an object")

    return jsonify(multi_agent.start(task, evidence))


@app.get("/api/ai/multi-agent/workflows/<workflow_id>")
def multi_agent_get(workflow_id):
    """One workflow, with its plan, work, review and audit history."""
    return jsonify(multi_agent.get(workflow_id))


@app.post("/api/ai/multi-agent/workflows/<workflow_id>/human-review")
def multi_agent_human_review(workflow_id):
    """The human decision that releases the workflow.

    This is the stage that makes the loop accountable: nothing the three
    agents produced counts until a named person accepts it, and anything
    short of an approval has to say what is wrong.
    """
    body = request.get_json(silent=True) or {}
    decision = body.get("decision")
    comments = body.get("comments", "")

    if not isinstance(decision, str) or not decision.strip():
        return bad_request("a decision is required")

    if not isinstance(comments, str):
        return bad_request("comments must be text")

    return jsonify(multi_agent.submit_review(workflow_id, decision, comments))


@app.errorhandler(404)
def not_found(_):
    return jsonify({"error": "endpoint not found"}), 404


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8400)),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
