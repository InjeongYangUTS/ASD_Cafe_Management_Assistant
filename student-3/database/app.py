import math
import os
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, request

from init_db import initialise_database


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("INVENTORY_DB_PATH", BASE_DIR / "inventory.db"))
app = Flask(__name__)


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def rows_to_list(rows):
    return [dict(row) for row in rows]


def error(message, status=400):
    return jsonify({"error": message}), status


def positive_int(value, default):
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


@app.get("/db/health")
def health():
    try:
        connection = get_connection()
        connection.execute("SELECT 1 FROM inventory LIMIT 1").fetchone()
        connection.close()
        return jsonify({"service": "student-3-database", "status": "healthy"})
    except sqlite3.Error as exc:
        return jsonify({"service": "student-3-database", "status": "unhealthy", "detail": str(exc)}), 503


@app.get("/db/dashboard")
def dashboard():
    connection = get_connection()
    summary = {
        "total_items": connection.execute("SELECT COUNT(*) FROM inventory").fetchone()[0],
        "low_stock_count": connection.execute("SELECT COUNT(*) FROM inventory WHERE status = 'LOW'").fetchone()[0],
        "out_of_stock_count": connection.execute("SELECT COUNT(*) FROM inventory WHERE status = 'OUT OF STOCK'").fetchone()[0],
        "pending_orders_count": connection.execute("SELECT COUNT(*) FROM restock_orders WHERE status = 'Pending'").fetchone()[0],
    }
    low_stock_items = rows_to_list(connection.execute("SELECT id, name, quantity, unit, minimum_stock, status FROM inventory WHERE status IN ('LOW', 'OUT OF STOCK') ORDER BY CASE status WHEN 'OUT OF STOCK' THEN 1 ELSE 2 END, quantity ASC").fetchall())
    recent_orders = rows_to_list(connection.execute("SELECT r.id, r.inventory_id, r.supplier_id, r.quantity, r.order_date, r.status, i.name AS item_name, s.name AS supplier_name FROM restock_orders r JOIN inventory i ON r.inventory_id = i.id JOIN suppliers s ON r.supplier_id = s.id ORDER BY r.created_at DESC, r.id DESC LIMIT 5").fetchall())
    connection.close()
    return jsonify({"summary": summary, "low_stock_items": low_stock_items, "recent_restock_orders": recent_orders})


@app.get("/db/inventory")
def list_inventory():
    category = request.args.get("category", "").strip()
    page = positive_int(request.args.get("page"), 1)
    per_page = min(100, positive_int(request.args.get("per_page"), 6))
    connection = get_connection()
    where = " WHERE category = ?" if category else ""
    params = [category] if category else []
    total = connection.execute("SELECT COUNT(*) FROM inventory" + where, params).fetchone()[0]
    total_pages = max(1, math.ceil(total / per_page))
    page = min(page, total_pages)
    offset = (page - 1) * per_page
    items = rows_to_list(connection.execute("SELECT id, name, category, quantity, unit, minimum_stock, status, supplier_id FROM inventory" + where + " ORDER BY id ASC LIMIT ? OFFSET ?", params + [per_page, offset]).fetchall())
    connection.close()
    return jsonify({"items": items, "page": page, "per_page": per_page, "total": total, "total_pages": total_pages})


@app.get("/db/inventory/<int:item_id>")
def get_inventory_item(item_id):
    connection = get_connection()
    row = connection.execute("SELECT * FROM inventory WHERE id = ?", (item_id,)).fetchone()
    connection.close()
    if row is None:
        return error("Inventory item not found.", 404)
    return jsonify(dict(row))


@app.post("/db/inventory")
def create_inventory_item():
    body = request.get_json(silent=True) or {}
    required = ["name", "category", "quantity", "unit", "minimum_stock", "status"]
    if any(key not in body for key in required):
        return error("Missing inventory fields.")
    connection = get_connection()
    cursor = connection.execute("INSERT INTO inventory (name, category, quantity, unit, minimum_stock, status, supplier_id) VALUES (?, ?, ?, ?, ?, ?, ?)", (body["name"], body["category"], body["quantity"], body["unit"], body["minimum_stock"], body["status"], body.get("supplier_id")))
    connection.commit()
    row = connection.execute("SELECT * FROM inventory WHERE id = ?", (cursor.lastrowid,)).fetchone()
    connection.close()
    return jsonify(dict(row)), 201


@app.put("/db/inventory/<int:item_id>")
def update_inventory_item(item_id):
    body = request.get_json(silent=True) or {}
    required = ["name", "category", "quantity", "unit", "minimum_stock", "status"]
    if any(key not in body for key in required):
        return error("Missing inventory fields.")
    connection = get_connection()
    if connection.execute("SELECT id FROM inventory WHERE id = ?", (item_id,)).fetchone() is None:
        connection.close()
        return error("Inventory item not found.", 404)
    connection.execute("UPDATE inventory SET name = ?, category = ?, quantity = ?, unit = ?, minimum_stock = ?, status = ?, supplier_id = ? WHERE id = ?", (body["name"], body["category"], body["quantity"], body["unit"], body["minimum_stock"], body["status"], body.get("supplier_id"), item_id))
    connection.commit()
    row = connection.execute("SELECT * FROM inventory WHERE id = ?", (item_id,)).fetchone()
    connection.close()
    return jsonify(dict(row))


@app.patch("/db/inventory/<int:item_id>/quantity")
def update_inventory_quantity(item_id):
    body = request.get_json(silent=True) or {}
    try:
        quantity = float(body["quantity"])
    except (KeyError, TypeError, ValueError):
        return error("A numeric quantity is required.")
    connection = get_connection()
    row = connection.execute("SELECT minimum_stock FROM inventory WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        connection.close()
        return error("Inventory item not found.", 404)
    status = "OUT OF STOCK" if quantity == 0 else "LOW" if quantity <= row["minimum_stock"] else "OK"
    connection.execute("UPDATE inventory SET quantity = ?, status = ? WHERE id = ?", (quantity, status, item_id))
    connection.commit()
    updated = connection.execute("SELECT * FROM inventory WHERE id = ?", (item_id,)).fetchone()
    connection.close()
    return jsonify(dict(updated))


@app.delete("/db/inventory/<int:item_id>")
def delete_inventory_item(item_id):
    connection = get_connection()
    if connection.execute("SELECT id FROM inventory WHERE id = ?", (item_id,)).fetchone() is None:
        connection.close()
        return error("Inventory item not found.", 404)
    connection.execute("DELETE FROM restock_orders WHERE inventory_id = ?", (item_id,))
    connection.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
    connection.commit()
    connection.close()
    return jsonify({"deleted": True, "id": item_id})


def evaluate_requirements(connection, requirements):
    results = []
    available = True
    for name, required in requirements.items():
        row = connection.execute("SELECT id, name, quantity, unit, minimum_stock, status FROM inventory WHERE name = ?", (name,)).fetchone()
        if row is None:
            results.append({"name": name, "required": required, "available": 0, "unit": None, "sufficient": False, "reason": "missing inventory item"})
            available = False
            continue
        sufficient = float(row["quantity"]) >= float(required)
        available = available and sufficient
        results.append({"id": row["id"], "name": row["name"], "required": required, "available": row["quantity"], "unit": row["unit"], "sufficient": sufficient})
    return available, results


@app.post("/db/inventory/check")
def check_requirements():
    requirements = (request.get_json(silent=True) or {}).get("requirements", {})
    if not isinstance(requirements, dict) or not requirements:
        return error("Inventory requirements are required.")
    connection = get_connection()
    available, results = evaluate_requirements(connection, requirements)
    connection.close()
    return jsonify({"available": available, "requirements": results})


@app.post("/db/inventory/deduct")
def deduct_requirements():
    requirements = (request.get_json(silent=True) or {}).get("requirements", {})
    if not isinstance(requirements, dict) or not requirements:
        return error("Inventory requirements are required.")
    connection = get_connection()
    available, results = evaluate_requirements(connection, requirements)
    if not available:
        connection.close()
        return jsonify({"error": "Insufficient inventory.", "available": False, "requirements": results}), 409
    for result in results:
        quantity = float(result["available"]) - float(result["required"])
        row = connection.execute("SELECT minimum_stock FROM inventory WHERE id = ?", (result["id"],)).fetchone()
        status = "OUT OF STOCK" if quantity == 0 else "LOW" if quantity <= row["minimum_stock"] else "OK"
        connection.execute("UPDATE inventory SET quantity = ?, status = ? WHERE id = ?", (quantity, status, result["id"]))
    connection.commit()
    connection.close()
    return jsonify({"deducted": True, "available": True, "requirements": results})


@app.get("/db/suppliers")
def list_suppliers():
    search = request.args.get("search", "").strip()
    page = positive_int(request.args.get("page"), 1)
    per_page = min(100, positive_int(request.args.get("per_page"), 6))
    connection = get_connection()
    params = []
    where = ""
    if search:
        value = f"%{search}%"
        where = " WHERE name LIKE ? OR contact_name LIKE ? OR supplies LIKE ? OR status LIKE ?"
        params = [value, value, value, value]
    total = connection.execute("SELECT COUNT(*) FROM suppliers" + where, params).fetchone()[0]
    total_pages = max(1, math.ceil(total / per_page))
    page = min(page, total_pages)
    offset = (page - 1) * per_page
    suppliers = rows_to_list(connection.execute("SELECT id, name, contact_name, phone, email, supplies, status FROM suppliers" + where + " ORDER BY id ASC LIMIT ? OFFSET ?", params + [per_page, offset]).fetchall())
    connection.close()
    return jsonify({"suppliers": suppliers, "page": page, "per_page": per_page, "total": total, "total_pages": total_pages})


@app.get("/db/suppliers/<int:supplier_id>")
def get_supplier(supplier_id):
    connection = get_connection()
    row = connection.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
    connection.close()
    if row is None:
        return error("Supplier not found.", 404)
    return jsonify(dict(row))


@app.post("/db/suppliers")
def create_supplier():
    body = request.get_json(silent=True) or {}
    if not str(body.get("name", "")).strip():
        return error("Supplier name is required.")
    connection = get_connection()
    cursor = connection.execute("INSERT INTO suppliers (name, contact_name, email, phone, supplies, status) VALUES (?, ?, ?, ?, ?, ?)", (body["name"], body.get("contact_name", ""), body.get("email", ""), body.get("phone", ""), body.get("supplies", ""), body.get("status", "Active")))
    connection.commit()
    row = connection.execute("SELECT * FROM suppliers WHERE id = ?", (cursor.lastrowid,)).fetchone()
    total = connection.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]
    connection.close()
    return jsonify({"supplier": dict(row), "total": total}), 201


@app.put("/db/suppliers/<int:supplier_id>")
def update_supplier(supplier_id):
    body = request.get_json(silent=True) or {}
    if not str(body.get("name", "")).strip():
        return error("Supplier name is required.")
    connection = get_connection()
    if connection.execute("SELECT id FROM suppliers WHERE id = ?", (supplier_id,)).fetchone() is None:
        connection.close()
        return error("Supplier not found.", 404)
    connection.execute("UPDATE suppliers SET name = ?, contact_name = ?, email = ?, phone = ?, supplies = ?, status = ? WHERE id = ?", (body["name"], body.get("contact_name", ""), body.get("email", ""), body.get("phone", ""), body.get("supplies", ""), body.get("status", "Active"), supplier_id))
    connection.commit()
    row = connection.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
    connection.close()
    return jsonify(dict(row))


@app.delete("/db/suppliers/<int:supplier_id>")
def delete_supplier(supplier_id):
    connection = get_connection()
    if connection.execute("SELECT id FROM suppliers WHERE id = ?", (supplier_id,)).fetchone() is None:
        connection.close()
        return error("Supplier not found.", 404)
    connection.execute("DELETE FROM restock_orders WHERE supplier_id = ?", (supplier_id,))
    connection.execute("UPDATE inventory SET supplier_id = NULL WHERE supplier_id = ?", (supplier_id,))
    connection.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
    connection.commit()
    connection.close()
    return jsonify({"deleted": True, "id": supplier_id})


@app.get("/db/restock-orders")
def list_restock_orders():
    status = request.args.get("status", "All").strip()
    page = positive_int(request.args.get("page"), 1)
    per_page = min(100, positive_int(request.args.get("per_page"), 6))
    connection = get_connection()
    params = []
    where = ""
    if status != "All":
        where = " WHERE r.status = ?"
        params = [status]
    total = connection.execute("SELECT COUNT(*) FROM restock_orders r" + where, params).fetchone()[0]
    total_pages = max(1, math.ceil(total / per_page))
    page = min(page, total_pages)
    offset = (page - 1) * per_page
    orders = rows_to_list(connection.execute("SELECT r.id, r.inventory_id, r.supplier_id, r.quantity, r.order_date, r.status, i.name AS item_name, s.name AS supplier_name FROM restock_orders r JOIN inventory i ON r.inventory_id = i.id JOIN suppliers s ON r.supplier_id = s.id" + where + " ORDER BY r.order_date DESC, r.id DESC LIMIT ? OFFSET ?", params + [per_page, offset]).fetchall())
    connection.close()
    return jsonify({"orders": orders, "page": page, "per_page": per_page, "total": total, "total_pages": total_pages})


@app.get("/db/restock-orders/<int:order_id>")
def get_restock_order(order_id):
    connection = get_connection()
    row = connection.execute("SELECT * FROM restock_orders WHERE id = ?", (order_id,)).fetchone()
    connection.close()
    if row is None:
        return error("Restock order not found.", 404)
    return jsonify(dict(row))


@app.post("/db/restock-orders")
def create_restock_order():
    body = request.get_json(silent=True) or {}
    connection = get_connection()
    try:
        cursor = connection.execute("INSERT INTO restock_orders (inventory_id, supplier_id, quantity, order_date, status) VALUES (?, ?, ?, ?, ?)", (body["inventory_id"], body["supplier_id"], body["quantity"], body["order_date"], body["status"]))
        connection.commit()
    except (KeyError, sqlite3.IntegrityError) as exc:
        connection.close()
        return error(str(exc))
    row = connection.execute("SELECT * FROM restock_orders WHERE id = ?", (cursor.lastrowid,)).fetchone()
    connection.close()
    return jsonify(dict(row)), 201


@app.put("/db/restock-orders/<int:order_id>")
def update_restock_order(order_id):
    body = request.get_json(silent=True) or {}
    connection = get_connection()
    if connection.execute("SELECT id FROM restock_orders WHERE id = ?", (order_id,)).fetchone() is None:
        connection.close()
        return error("Restock order not found.", 404)
    try:
        connection.execute("UPDATE restock_orders SET inventory_id = ?, supplier_id = ?, quantity = ?, order_date = ?, status = ? WHERE id = ?", (body["inventory_id"], body["supplier_id"], body["quantity"], body["order_date"], body["status"], order_id))
        connection.commit()
    except (KeyError, sqlite3.IntegrityError) as exc:
        connection.close()
        return error(str(exc))
    row = connection.execute("SELECT * FROM restock_orders WHERE id = ?", (order_id,)).fetchone()
    connection.close()
    return jsonify(dict(row))


@app.delete("/db/restock-orders/<int:order_id>")
def delete_restock_order(order_id):
    connection = get_connection()
    if connection.execute("SELECT id FROM restock_orders WHERE id = ?", (order_id,)).fetchone() is None:
        connection.close()
        return error("Restock order not found.", 404)
    connection.execute("DELETE FROM restock_orders WHERE id = ?", (order_id,))
    connection.commit()
    connection.close()
    return jsonify({"deleted": True, "id": order_id})


initialise_database(DB_PATH)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "7300")), debug=False)
