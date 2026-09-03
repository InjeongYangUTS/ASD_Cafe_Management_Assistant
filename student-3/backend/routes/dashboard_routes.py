from flask import Blueprint, render_template, request

from db import get_db_connection
from agentic_inventory import get_ai_restock_recommendation

dashboard_bp = Blueprint(
    "dashboard",
    __name__
)

# =========================================================
# INVENTORY DASHBOARD
# =========================================================

@dashboard_bp.route("/", methods=["GET", "POST"])
def inventory_dashboard():

    connection = get_db_connection()
    cursor = connection.cursor()


    # Total inventory items
    cursor.execute("""
        SELECT COUNT(*)
        FROM inventory
    """)

    total_items = cursor.fetchone()[0]


    # Low stock items
    cursor.execute("""
        SELECT COUNT(*)
        FROM inventory
        WHERE status = 'LOW'
    """)

    low_stock_count = cursor.fetchone()[0]


    # Out of stock items
    cursor.execute("""
        SELECT COUNT(*)
        FROM inventory
        WHERE status = 'OUT OF STOCK'
    """)

    out_of_stock_count = cursor.fetchone()[0]


    # Pending restock orders
    cursor.execute("""
        SELECT COUNT(*)
        FROM restock_orders
        WHERE status = 'Pending'
    """)

    pending_orders_count = cursor.fetchone()[0]

    # -----------------------------------------------------
    # LOW STOCK ITEMS
    # -----------------------------------------------------

    cursor.execute("""
        SELECT
            id,
            name,
            quantity,
            unit,
            minimum_stock,
            status
        FROM inventory
        WHERE status IN ('LOW', 'OUT OF STOCK')
        ORDER BY quantity ASC
        LIMIT 5
    """)

    low_stock_rows = cursor.fetchall()


    low_stock_items = []

    for row in low_stock_rows:

        low_stock_items.append({
            "id": row["id"],
            "name": row["name"],
            "quantity": f'{row["quantity"]:g} {row["unit"]}',
            "minimum_stock": f'{row["minimum_stock"]:g} {row["unit"]}',
            "status": row["status"]
        })

    # -----------------------------------------------------
    # RECENT RESTOCK ORDERS
    # -----------------------------------------------------

    cursor.execute("""
        SELECT
            restock_orders.id,
            inventory.name,
            suppliers.name AS supplier_name,
            restock_orders.status
        FROM restock_orders

        JOIN inventory
            ON restock_orders.inventory_id = inventory.id

        JOIN suppliers
            ON restock_orders.supplier_id = suppliers.id

        ORDER BY restock_orders.created_at DESC

        LIMIT 5
    """)

    recent_restock_orders = cursor.fetchall()

    connection.close()

    # -----------------------------------------------------
    # AI AGENT
    # -----------------------------------------------------

    ai_question = ""
    ai_answer = ""

    if request.method == "POST":

        ai_question = request.form.get("question", "").strip()

        if ai_question:

            ai_answer = get_ai_restock_recommendation(
                ai_question,
                low_stock_items
            )

    return render_template(
        "inventory_dashboard.html",

        total_items=total_items,
        low_stock_count=low_stock_count,
        out_of_stock_count=out_of_stock_count,
        pending_orders_count=pending_orders_count,

        low_stock_items=low_stock_items,
        recent_restock_orders=recent_restock_orders,
        
        ai_question=ai_question,
        ai_answer=ai_answer
    )

@dashboard_bp.route("/ai-restock-recommendation", methods=["POST"])
def ai_restock_recommendation():

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            name,
            quantity,
            unit,
            minimum_stock,
            status
        FROM inventory
        WHERE status IN ('LOW', 'OUT OF STOCK')
        ORDER BY
            CASE
                WHEN status = 'OUT OF STOCK' THEN 1
                WHEN status = 'LOW' THEN 2
                ELSE 3
            END,
            quantity ASC
    """)

    inventory_items = cursor.fetchall()

    connection.close()

    recommendation = get_ai_restock_recommendation(
        inventory_items
    )

    return recommendation
