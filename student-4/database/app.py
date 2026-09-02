"""
Student 4 (Stella Kwon) - Order & Kitchen Management
DATABASE MICROSERVICE  (container: student-4-database, port 7400)

This service is the ONLY process that opens orders.db. Every other
microservice - including my own backend/API - reads and writes this data
exclusively through the /db/* HTTP endpoints below.

Endpoints
    GET    /db/health
    GET    /db/stats

    GET    /db/orders                     ?status= &channel= &limit= &include=items
    POST   /db/orders                     (creates order + items + first status row)
    GET    /db/orders/<id>
    PUT    /db/orders/<id>
    DELETE /db/orders/<id>

    GET    /db/orders/<id>/items
    POST   /db/orders/<id>/items
    PUT    /db/order-items/<id>
    DELETE /db/order-items/<id>

    GET    /db/orders/<id>/statuses
    POST   /db/orders/<id>/statuses
    GET    /db/order-statuses             ?limit=
    DELETE /db/order-statuses/<id>
"""

import os
import sqlite3

from flask import Flask, jsonify, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("ORDER_DB_PATH", os.path.join(BASE_DIR, "orders.db"))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

VALID_STATUSES = [
    "PENDING", "CONFIRMED", "PREPARING", "READY", "COMPLETED", "CANCELLED",
]
VALID_ITEM_STATUSES = ["PENDING", "PREPARING", "READY", "CANCELLED"]
VALID_STATIONS = ["BAR", "KITCHEN", "PASTRY"]
VALID_CHANNELS = ["DINE_IN", "TAKEAWAY"]

app = Flask(__name__)


# =====================================================================
# Connection helpers
# =====================================================================

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_schema():
    """Create the tables on first boot so the container never starts empty."""
    conn = get_conn()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
        conn.executescript(schema_file.read())
    conn.commit()
    conn.close()


def rows_to_list(rows):
    return [dict(row) for row in rows]


def error(message, status_code=400, **extra):
    payload = {"error": message}
    payload.update(extra)
    return jsonify(payload), status_code


def next_order_number(conn):
    row = conn.execute(
        "SELECT order_number FROM orders "
        "WHERE order_number LIKE 'A-%' ORDER BY id DESC LIMIT 1"
    ).fetchone()

    if row is None:
        return "A-1001"

    try:
        return "A-%d" % (int(row["order_number"].split("-")[1]) + 1)
    except (IndexError, ValueError):
        count = conn.execute("SELECT COUNT(*) AS c FROM orders").fetchone()["c"]
        return "A-%d" % (1001 + count)


def recalc_order(conn, order_id):
    """
    Recompute item_count / total_amount / prep_seconds from order_items.

    Every line the order still holds is counted, including lines marked
    CANCELLED. Cancellation is recorded on the ORDER (status = 'CANCELLED'),
    and the value of a cancelled order still has to be reportable - a
    cancelled ticket showing $0.00 hides what was lost. A line the customer
    actually removed is DELETEd, which does reduce the total.

    (This rule was tightened after the agentic review loop flagged that the
    seeded cancelled order A-1004 stored $11.00 while this function
    recomputed $0.00 - see agentic/logs/ and prompts/03-*.md.)
    """
    row = conn.execute(
        """
        SELECT COALESCE(SUM(quantity), 0)                  AS item_count,
               COALESCE(SUM(line_total), 0)                AS total_amount,
               COALESCE(SUM(prep_seconds * quantity), 0)   AS prep_seconds
        FROM order_items
        WHERE order_id = ?
        """,
        (order_id,),
    ).fetchone()

    conn.execute(
        "UPDATE orders SET item_count = ?, total_amount = ?, prep_seconds = ? "
        "WHERE id = ?",
        (row["item_count"], round(row["total_amount"], 2),
         row["prep_seconds"], order_id),
    )


def fetch_order(conn, order_id, include_items=True):
    order = conn.execute(
        "SELECT * FROM orders WHERE id = ?", (order_id,)
    ).fetchone()

    if order is None:
        return None

    order = dict(order)

    if include_items:
        order["items"] = rows_to_list(conn.execute(
            "SELECT * FROM order_items WHERE order_id = ? ORDER BY id",
            (order_id,),
        ).fetchall())

        order["status_history"] = rows_to_list(conn.execute(
            "SELECT * FROM order_statuses WHERE order_id = ? "
            "ORDER BY changed_at, id",
            (order_id,),
        ).fetchall())

    return order


# =====================================================================
# Health / stats
# =====================================================================

@app.get("/db/health")
def health():
    try:
        conn = get_conn()
        conn.execute("SELECT 1 FROM orders LIMIT 1").fetchone()
        conn.close()
        return jsonify({
            "service": "student-4-database",
            "status": "healthy",
            "database": os.path.basename(DB_PATH),
        })
    except sqlite3.Error as exc:
        return jsonify({
            "service": "student-4-database",
            "status": "unhealthy",
            "detail": str(exc),
        }), 503


@app.get("/db/stats")
def stats():
    conn = get_conn()

    by_status = {
        row["status"]: row["c"]
        for row in conn.execute(
            "SELECT status, COUNT(*) AS c FROM orders GROUP BY status"
        ).fetchall()
    }

    by_station = {
        row["station"]: row["c"]
        for row in conn.execute(
            """
            SELECT oi.station, COALESCE(SUM(oi.quantity), 0) AS c
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            WHERE o.status IN ('PENDING', 'CONFIRMED', 'PREPARING')
            GROUP BY oi.station
            """
        ).fetchall()
    }

    totals = conn.execute(
        """
        SELECT COUNT(*) AS orders,
               (SELECT COUNT(*) FROM order_items)    AS order_items,
               (SELECT COUNT(*) FROM order_statuses) AS order_statuses
        FROM orders
        """
    ).fetchone()

    conn.close()

    return jsonify({
        "service": "student-4-database",
        "row_counts": dict(totals),
        "orders_by_status": by_status,
        "open_items_by_station": by_station,
    })


# =====================================================================
# orders : CRUD
# =====================================================================

@app.get("/db/orders")
def list_orders():
    status = request.args.get("status")
    channel = request.args.get("channel")
    include = request.args.get("include", "")
    limit = min(int(request.args.get("limit", 100)), 500)
    offset = int(request.args.get("offset", 0))

    sql = "SELECT * FROM orders WHERE 1 = 1"
    params = []

    if status:
        wanted = [s.strip().upper() for s in status.split(",") if s.strip()]
        invalid = [s for s in wanted if s not in VALID_STATUSES]
        if invalid:
            return error("unknown status: %s" % ", ".join(invalid))
        sql += " AND status IN (%s)" % ",".join("?" * len(wanted))
        params.extend(wanted)

    if channel:
        if channel.upper() not in VALID_CHANNELS:
            return error("unknown channel: %s" % channel)
        sql += " AND channel = ?"
        params.append(channel.upper())

    sql += " ORDER BY placed_at DESC, id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    conn = get_conn()
    orders = rows_to_list(conn.execute(sql, params).fetchall())

    if "items" in include:
        for order in orders:
            order["items"] = rows_to_list(conn.execute(
                "SELECT * FROM order_items WHERE order_id = ? ORDER BY id",
                (order["id"],),
            ).fetchall())

    conn.close()
    return jsonify({"count": len(orders), "orders": orders})


@app.post("/db/orders")
def create_order():
    body = request.get_json(silent=True) or {}
    items = body.get("items") or []

    if not items:
        return error("an order needs at least one item")

    channel = str(body.get("channel", "DINE_IN")).upper()
    if channel not in VALID_CHANNELS:
        return error("channel must be one of %s" % VALID_CHANNELS)

    # Validate every line item before touching the database.
    cleaned = []
    for index, item in enumerate(items):
        try:
            menu_id = int(item["menu_id"])
            quantity = int(item.get("quantity", 1))
            unit_price = float(item["unit_price"])
        except (KeyError, TypeError, ValueError):
            return error("item %d needs menu_id, unit_price and quantity" % index)

        if quantity < 1:
            return error("item %d quantity must be 1 or more" % index)
        if unit_price < 0:
            return error("item %d unit_price cannot be negative" % index)

        station = str(item.get("station", "BAR")).upper()
        if station not in VALID_STATIONS:
            station = "BAR"

        cleaned.append({
            "menu_id": menu_id,
            "menu_name": item.get("menu_name") or ("Menu #%d" % menu_id),
            "unit_price": round(unit_price, 2),
            "quantity": quantity,
            "line_total": round(unit_price * quantity, 2),
            "station": station,
            "prep_seconds": int(item.get("prep_seconds", 60)),
            "note": item.get("note"),
        })

    conn = get_conn()
    try:
        order_number = body.get("order_number") or next_order_number(conn)

        cursor = conn.execute(
            """
            INSERT INTO orders
                (order_number, channel, table_number, customer_id, customer_name,
                 staff_id, staff_name, status, note, stock_deducted)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
            """,
            (
                order_number, channel, body.get("table_number"),
                body.get("customer_id"), body.get("customer_name"),
                body.get("staff_id"), body.get("staff_name"),
                body.get("note"), 1 if body.get("stock_deducted") else 0,
            ),
        )
        order_id = cursor.lastrowid

        for item in cleaned:
            conn.execute(
                """
                INSERT INTO order_items
                    (order_id, menu_id, menu_name, unit_price, quantity,
                     line_total, station, prep_seconds, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id, item["menu_id"], item["menu_name"],
                    item["unit_price"], item["quantity"], item["line_total"],
                    item["station"], item["prep_seconds"], item["note"],
                ),
            )

        conn.execute(
            "INSERT INTO order_statuses (order_id, status, changed_by, note) "
            "VALUES (?, 'PENDING', ?, 'order placed')",
            (order_id, body.get("staff_name") or "pos"),
        )

        recalc_order(conn, order_id)
        conn.commit()

        created = fetch_order(conn, order_id)

    except sqlite3.IntegrityError as exc:
        conn.rollback()
        conn.close()
        return error("could not create order: %s" % exc, 409)

    conn.close()
    return jsonify(created), 201


@app.get("/db/orders/<int:order_id>")
def get_order(order_id):
    conn = get_conn()
    order = fetch_order(conn, order_id)
    conn.close()

    if order is None:
        return error("order %d not found" % order_id, 404)

    return jsonify(order)


@app.put("/db/orders/<int:order_id>")
def update_order(order_id):
    body = request.get_json(silent=True) or {}

    editable = [
        "channel", "table_number", "customer_id", "customer_name",
        "staff_id", "staff_name", "note", "status", "stock_deducted",
    ]
    updates = {k: body[k] for k in editable if k in body}

    if not updates:
        return error("nothing to update")

    if "status" in updates:
        updates["status"] = str(updates["status"]).upper()
        if updates["status"] not in VALID_STATUSES:
            return error("status must be one of %s" % VALID_STATUSES)

    if "channel" in updates:
        updates["channel"] = str(updates["channel"]).upper()
        if updates["channel"] not in VALID_CHANNELS:
            return error("channel must be one of %s" % VALID_CHANNELS)

    if "stock_deducted" in updates:
        updates["stock_deducted"] = 1 if updates["stock_deducted"] else 0

    conn = get_conn()
    if conn.execute("SELECT 1 FROM orders WHERE id = ?", (order_id,)).fetchone() is None:
        conn.close()
        return error("order %d not found" % order_id, 404)

    conn.execute(
        "UPDATE orders SET %s WHERE id = ?" %
        ", ".join("%s = ?" % column for column in updates),
        list(updates.values()) + [order_id],
    )
    conn.commit()

    order = fetch_order(conn, order_id)
    conn.close()
    return jsonify(order)


@app.delete("/db/orders/<int:order_id>")
def delete_order(order_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT order_number FROM orders WHERE id = ?", (order_id,)
    ).fetchone()

    if row is None:
        conn.close()
        return error("order %d not found" % order_id, 404)

    conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()

    return jsonify({"deleted": True, "id": order_id,
                    "order_number": row["order_number"]})


# =====================================================================
# order_items : CRUD
# =====================================================================

@app.get("/db/orders/<int:order_id>/items")
def list_items(order_id):
    conn = get_conn()
    if conn.execute("SELECT 1 FROM orders WHERE id = ?", (order_id,)).fetchone() is None:
        conn.close()
        return error("order %d not found" % order_id, 404)

    items = rows_to_list(conn.execute(
        "SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order_id,)
    ).fetchall())
    conn.close()

    return jsonify({"order_id": order_id, "count": len(items), "items": items})


@app.post("/db/orders/<int:order_id>/items")
def add_item(order_id):
    body = request.get_json(silent=True) or {}

    try:
        menu_id = int(body["menu_id"])
        unit_price = float(body["unit_price"])
        quantity = int(body.get("quantity", 1))
    except (KeyError, TypeError, ValueError):
        return error("menu_id, unit_price and quantity are required")

    if quantity < 1:
        return error("quantity must be 1 or more")

    station = str(body.get("station", "BAR")).upper()
    if station not in VALID_STATIONS:
        station = "BAR"

    conn = get_conn()
    if conn.execute("SELECT 1 FROM orders WHERE id = ?", (order_id,)).fetchone() is None:
        conn.close()
        return error("order %d not found" % order_id, 404)

    cursor = conn.execute(
        """
        INSERT INTO order_items
            (order_id, menu_id, menu_name, unit_price, quantity,
             line_total, station, prep_seconds, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            order_id, menu_id, body.get("menu_name") or ("Menu #%d" % menu_id),
            round(unit_price, 2), quantity, round(unit_price * quantity, 2),
            station, int(body.get("prep_seconds", 60)), body.get("note"),
        ),
    )
    item_id = cursor.lastrowid

    recalc_order(conn, order_id)
    conn.commit()

    item = dict(conn.execute(
        "SELECT * FROM order_items WHERE id = ?", (item_id,)
    ).fetchone())
    conn.close()

    return jsonify(item), 201


@app.put("/db/order-items/<int:item_id>")
def update_item(item_id):
    body = request.get_json(silent=True) or {}

    conn = get_conn()
    existing = conn.execute(
        "SELECT * FROM order_items WHERE id = ?", (item_id,)
    ).fetchone()

    if existing is None:
        conn.close()
        return error("order item %d not found" % item_id, 404)

    quantity = int(body.get("quantity", existing["quantity"]))
    if quantity < 1:
        conn.close()
        return error("quantity must be 1 or more")

    unit_price = round(float(body.get("unit_price", existing["unit_price"])), 2)

    item_status = str(body.get("item_status", existing["item_status"])).upper()
    if item_status not in VALID_ITEM_STATUSES:
        conn.close()
        return error("item_status must be one of %s" % VALID_ITEM_STATUSES)

    station = str(body.get("station", existing["station"])).upper()
    if station not in VALID_STATIONS:
        conn.close()
        return error("station must be one of %s" % VALID_STATIONS)

    conn.execute(
        """
        UPDATE order_items
        SET quantity = ?, unit_price = ?, line_total = ?, item_status = ?,
            station = ?, note = ?
        WHERE id = ?
        """,
        (
            quantity, unit_price, round(unit_price * quantity, 2), item_status,
            station, body.get("note", existing["note"]), item_id,
        ),
    )

    recalc_order(conn, existing["order_id"])
    conn.commit()

    item = dict(conn.execute(
        "SELECT * FROM order_items WHERE id = ?", (item_id,)
    ).fetchone())
    conn.close()

    return jsonify(item)


@app.delete("/db/order-items/<int:item_id>")
def delete_item(item_id):
    conn = get_conn()
    existing = conn.execute(
        "SELECT order_id FROM order_items WHERE id = ?", (item_id,)
    ).fetchone()

    if existing is None:
        conn.close()
        return error("order item %d not found" % item_id, 404)

    conn.execute("DELETE FROM order_items WHERE id = ?", (item_id,))
    recalc_order(conn, existing["order_id"])
    conn.commit()
    conn.close()

    return jsonify({"deleted": True, "id": item_id,
                    "order_id": existing["order_id"]})


# =====================================================================
# order_statuses : CRUD
# =====================================================================

@app.get("/db/orders/<int:order_id>/statuses")
def list_statuses(order_id):
    conn = get_conn()
    if conn.execute("SELECT 1 FROM orders WHERE id = ?", (order_id,)).fetchone() is None:
        conn.close()
        return error("order %d not found" % order_id, 404)

    history = rows_to_list(conn.execute(
        "SELECT * FROM order_statuses WHERE order_id = ? ORDER BY changed_at, id",
        (order_id,),
    ).fetchall())
    conn.close()

    return jsonify({"order_id": order_id, "count": len(history),
                    "status_history": history})


@app.post("/db/orders/<int:order_id>/statuses")
def add_status(order_id):
    body = request.get_json(silent=True) or {}
    status = str(body.get("status", "")).upper()

    if status not in VALID_STATUSES:
        return error("status must be one of %s" % VALID_STATUSES)

    conn = get_conn()
    if conn.execute("SELECT 1 FROM orders WHERE id = ?", (order_id,)).fetchone() is None:
        conn.close()
        return error("order %d not found" % order_id, 404)

    cursor = conn.execute(
        "INSERT INTO order_statuses (order_id, status, changed_by, note) "
        "VALUES (?, ?, ?, ?)",
        (order_id, status, body.get("changed_by", "system"), body.get("note")),
    )
    status_id = cursor.lastrowid

    # The order row keeps the current status denormalised for fast board reads.
    conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()

    row = dict(conn.execute(
        "SELECT * FROM order_statuses WHERE id = ?", (status_id,)
    ).fetchone())
    conn.close()

    return jsonify(row), 201


@app.get("/db/order-statuses")
def list_all_statuses():
    limit = min(int(request.args.get("limit", 50)), 500)

    conn = get_conn()
    rows = rows_to_list(conn.execute(
        """
        SELECT s.*, o.order_number
        FROM order_statuses s
        JOIN orders o ON o.id = s.order_id
        ORDER BY s.changed_at DESC, s.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall())
    conn.close()

    return jsonify({"count": len(rows), "status_history": rows})


@app.delete("/db/order-statuses/<int:status_id>")
def delete_status(status_id):
    conn = get_conn()
    existing = conn.execute(
        "SELECT order_id FROM order_statuses WHERE id = ?", (status_id,)
    ).fetchone()

    if existing is None:
        conn.close()
        return error("status record %d not found" % status_id, 404)

    conn.execute("DELETE FROM order_statuses WHERE id = ?", (status_id,))
    conn.commit()
    conn.close()

    return jsonify({"deleted": True, "id": status_id})


@app.errorhandler(404)
def not_found(_):
    return error("endpoint not found", 404)


ensure_schema()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 7400)),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
