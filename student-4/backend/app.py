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
"""

import os
from datetime import datetime

from flask import Flask, jsonify, request

import ai
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


@app.errorhandler(404)
def not_found(_):
    return jsonify({"error": "endpoint not found"}), 404


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8400)),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
