from flask import Flask, render_template, request
import sqlite3
import os 

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.path.join(
    BASE_DIR,
    "database",
    "inventory.db"
)



app = Flask(
    __name__,
    template_folder="frontend/templates",
    static_folder="assets"
)

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# =========================================================
# INVENTORY DASHBOARD
# =========================================================

@app.route("/")
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


    return render_template(
        "inventory_dashboard.html",

        total_items=total_items,
        low_stock_count=low_stock_count,
        out_of_stock_count=out_of_stock_count,
        pending_orders_count=pending_orders_count,

        low_stock_items=low_stock_items,
        recent_restock_orders=recent_restock_orders,
        ai_recommendation=""
    )

# =========================================================
# Inventory Management
# =========================================================

@app.route("/inventory-management")
def inventory_management():

    page = request.args.get("page", 1, type=int)
    category = request.args.get("category", "")

    per_page = 6

    if page < 1:
        page = 1

    offset = (page - 1) * per_page

    connection = get_db_connection()
    cursor = connection.cursor()

    if category:
        cursor.execute("""
            SELECT COUNT(*)
            FROM inventory
            WHERE category = ?
        """, (category,))
    else:
        cursor.execute("""
            SELECT COUNT(*)
            FROM inventory
        """)

    total_items = cursor.fetchone()[0]

    total_pages = (total_items + per_page - 1) // per_page

    if total_pages > 0 and page > total_pages:
        page = total_pages
        offset = (page - 1) * per_page

    if category:

        cursor.execute("""
            SELECT
                id,
                name,
                category,
                quantity,
                unit,
                minimum_stock,
                status
            FROM inventory
            WHERE category = ?
            ORDER BY id ASC
            LIMIT ? OFFSET ?
        """, (category, per_page, offset))

    else:

        cursor.execute("""
            SELECT
                id,
                name,
                category,
                quantity,
                unit,
                minimum_stock,
                status
            FROM inventory
            ORDER BY id ASC
            LIMIT ? OFFSET ?
        """, (per_page, offset))

    inventory_items = cursor.fetchall()

    connection.close()

    return render_template(
        "inventory_management.html",
        inventory_items=inventory_items,
        page=page,
        total_pages=total_pages,
        selected_category=category
    )

# =========================================================
# Supplier Management
# =========================================================

@app.route("/supplier-management")
def supplier_management():
    return render_template("supplier_management.html")


# =========================================================
# Restock Order Management
# =========================================================

@app.route("/restock-order-management")
def restock_order_management():
    return render_template("restock_order_management.html")


# =========================================================
# Run Application
# =========================================================

if __name__ == "__main__":
    app.run(debug=True, port=5001)