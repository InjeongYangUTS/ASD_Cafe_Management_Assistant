import os
from datetime import date
from urllib.parse import urlencode

from flask import Flask, jsonify, request

from agentic_inventory import run_agentic_loop
from database_client import DatabaseError, call_database
from recipes import build_requirements


ALLOWED_RESTOCK_STATUSES = {"Pending", "Ordered", "Delivered", "Cancelled"}
ALLOWED_SUPPLIER_STATUSES = {"Active", "Inactive"}
app = Flask(__name__)


@app.errorhandler(DatabaseError)
def handle_database_error(exc):
    payload = {"error": exc.message}
    if exc.detail:
        payload["detail"] = exc.detail
    return jsonify(payload), exc.status_code


def error(message, status=400, **extra):
    payload = {"error": message}
    payload.update(extra)
    return jsonify(payload), status


def status_for(quantity, minimum_stock):
    if quantity == 0:
        return "OUT OF STOCK"
    if quantity <= minimum_stock:
        return "LOW"
    return "OK"


def query_path(path):
    values = {key: value for key, value in request.args.items() if value != ""}
    return path + ("?" + urlencode(values) if values else "")


@app.get("/api/health")
def health():
    try:
        database = call_database("GET", "/db/health")
        status = "healthy"
    except DatabaseError as exc:
        database = {"status": "unreachable", "detail": exc.message}
        status = "degraded"
    return jsonify({"service": "student-3-backend", "status": status, "database": database}), 200 if status == "healthy" else 503


@app.get("/api/dashboard")
def dashboard():
    return jsonify(call_database("GET", "/db/dashboard"))


@app.get("/api/inventory")
def list_inventory():
    return jsonify(call_database("GET", query_path("/db/inventory")))


@app.get("/api/inventory/<int:item_id>")
def get_inventory_item(item_id):
    return jsonify(call_database("GET", f"/db/inventory/{item_id}"))


@app.post("/api/inventory")
def create_inventory_item():
    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    category = str(body.get("category", "")).strip()
    unit = str(body.get("unit", "")).strip()
    try:
        quantity = float(body.get("quantity"))
        minimum_stock = float(body.get("minimum_stock"))
    except (TypeError, ValueError):
        return error("Quantity and minimum stock must be numeric.")
    if not name or not category or not unit:
        return error("Name, category and unit are required.")
    if quantity < 0 or minimum_stock < 0:
        return error("Quantity and minimum stock cannot be negative.")
    payload = {
        "name": name,
        "category": category,
        "quantity": quantity,
        "unit": unit,
        "minimum_stock": minimum_stock,
        "status": status_for(quantity, minimum_stock),
        "supplier_id": body.get("supplier_id") or None,
    }
    return jsonify(call_database("POST", "/db/inventory", json=payload)), 201


@app.put("/api/inventory/<int:item_id>")
def update_inventory_item(item_id):
    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    category = str(body.get("category", "")).strip()
    unit = str(body.get("unit", "")).strip()
    try:
        quantity = float(body.get("quantity"))
        minimum_stock = float(body.get("minimum_stock"))
    except (TypeError, ValueError):
        return error("Quantity and minimum stock must be numeric.")
    if not name or not category or not unit:
        return error("Name, category and unit are required.")
    if quantity < 0 or minimum_stock < 0:
        return error("Quantity and minimum stock cannot be negative.")
    payload = {
        "name": name,
        "category": category,
        "quantity": quantity,
        "unit": unit,
        "minimum_stock": minimum_stock,
        "status": status_for(quantity, minimum_stock),
        "supplier_id": body.get("supplier_id") or None,
    }
    return jsonify(call_database("PUT", f"/db/inventory/{item_id}", json=payload))


@app.delete("/api/inventory/<int:item_id>")
def delete_inventory_item(item_id):
    return jsonify(call_database("DELETE", f"/db/inventory/{item_id}"))


@app.post("/api/inventory/check")
def check_inventory():
    body = request.get_json(silent=True) or {}
    try:
        requirements, unknown = build_requirements(body.get("items", []))
    except ValueError as exc:
        return error(str(exc))
    if unknown:
        return error("Unknown menu items.", 400, unknown_menu_ids=unknown)
    result = call_database("POST", "/db/inventory/check", json={"requirements": requirements})
    result["source"] = body.get("source")
    return jsonify(result)


@app.post("/api/inventory/deduct")
def deduct_inventory():
    body = request.get_json(silent=True) or {}
    try:
        requirements, unknown = build_requirements(body.get("items", []))
    except ValueError as exc:
        return error(str(exc))
    if unknown:
        return error("Unknown menu items.", 400, unknown_menu_ids=unknown)
    result = call_database("POST", "/db/inventory/deduct", json={"requirements": requirements})
    result["source"] = body.get("source")
    return jsonify(result)


@app.get("/api/suppliers")
def list_suppliers():
    return jsonify(call_database("GET", query_path("/db/suppliers")))


@app.get("/api/suppliers/<int:supplier_id>")
def get_supplier(supplier_id):
    return jsonify(call_database("GET", f"/db/suppliers/{supplier_id}"))


@app.post("/api/suppliers")
def create_supplier():
    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    status = str(body.get("status", "Active")).strip()
    if not name:
        return error("Supplier name is required.")
    if status not in ALLOWED_SUPPLIER_STATUSES:
        return error("Invalid supplier status.")
    payload = {
        "name": name,
        "contact_name": str(body.get("contact_name", "")).strip(),
        "email": str(body.get("email", "")).strip(),
        "phone": str(body.get("phone", "")).strip(),
        "supplies": str(body.get("supplies", "")).strip(),
        "status": status,
    }
    return jsonify(call_database("POST", "/db/suppliers", json=payload)), 201


@app.put("/api/suppliers/<int:supplier_id>")
def update_supplier(supplier_id):
    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    status = str(body.get("status", "Active")).strip()
    if not name:
        return error("Supplier name is required.")
    if status not in ALLOWED_SUPPLIER_STATUSES:
        return error("Invalid supplier status.")
    payload = {
        "name": name,
        "contact_name": str(body.get("contact_name", "")).strip(),
        "email": str(body.get("email", "")).strip(),
        "phone": str(body.get("phone", "")).strip(),
        "supplies": str(body.get("supplies", "")).strip(),
        "status": status,
    }
    return jsonify(call_database("PUT", f"/db/suppliers/{supplier_id}", json=payload))


@app.delete("/api/suppliers/<int:supplier_id>")
def delete_supplier(supplier_id):
    return jsonify(call_database("DELETE", f"/db/suppliers/{supplier_id}"))


@app.get("/api/restock-orders")
def list_restock_orders():
    return jsonify(call_database("GET", query_path("/db/restock-orders")))


@app.get("/api/restock-orders/<int:order_id>")
def get_restock_order(order_id):
    return jsonify(call_database("GET", f"/db/restock-orders/{order_id}"))


def restock_payload(body):
    try:
        inventory_id = int(body.get("inventory_id"))
        supplier_id = int(body.get("supplier_id"))
        quantity = float(body.get("quantity"))
    except (TypeError, ValueError):
        raise ValueError("Supplier, inventory item and quantity are required.")
    order_date = str(body.get("order_date", "")).strip() or date.today().isoformat()
    status = str(body.get("status", "Pending")).strip()
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")
    if status not in ALLOWED_RESTOCK_STATUSES:
        raise ValueError("Invalid restock order status.")
    return {"inventory_id": inventory_id, "supplier_id": supplier_id, "quantity": quantity, "order_date": order_date, "status": status}


@app.post("/api/restock-orders")
def create_restock_order():
    try:
        payload = restock_payload(request.get_json(silent=True) or {})
    except ValueError as exc:
        return error(str(exc))
    return jsonify(call_database("POST", "/db/restock-orders", json=payload)), 201


@app.put("/api/restock-orders/<int:order_id>")
def update_restock_order(order_id):
    try:
        payload = restock_payload(request.get_json(silent=True) or {})
    except ValueError as exc:
        return error(str(exc))
    return jsonify(call_database("PUT", f"/db/restock-orders/{order_id}", json=payload))


@app.delete("/api/restock-orders/<int:order_id>")
def delete_restock_order(order_id):
    return jsonify(call_database("DELETE", f"/db/restock-orders/{order_id}"))


@app.post("/api/ai/restock-recommendation")
def ai_restock_recommendation():
    body = request.get_json(silent=True) or {}
    question = str(body.get("question", "")).strip()
    if not question:
        return error("A question is required.")
    inventory = call_database("GET", "/db/dashboard")["low_stock_items"]
    try:
        return jsonify(run_agentic_loop(inventory, question, save_log=True))
    except RuntimeError as exc:
        return error(str(exc), 503)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8300")), debug=False)
