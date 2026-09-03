from flask import Blueprint, render_template, request, redirect, url_for

from db import get_db_connection

inventory_bp = Blueprint(
    "inventory",
    __name__
)

# =========================================================
# Inventory Management
# =========================================================

@inventory_bp.route("/inventory-management")
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
                status,
                supplier_id
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
                status,
                supplier_id
            FROM inventory
            ORDER BY id ASC
            LIMIT ? OFFSET ?
        """, (per_page, offset))

    inventory_items = cursor.fetchall()

    # Supplier dropdown data
    cursor.execute("""
        SELECT
            id,
            name
        FROM suppliers
        ORDER BY name ASC
    """)

    suppliers = cursor.fetchall()

    connection.close()

    return render_template(
        "inventory_management.html",
        inventory_items=inventory_items,
        suppliers=suppliers,
        page=page,
        total_pages=total_pages,
        selected_category=category
    )

@inventory_bp.route("/inventory/add", methods=["POST"])
def add_inventory_item():
    
    name = request.form["name"]
    category = request.form["category"]
    unit = request.form["unit"]
    quantity = request.form["quantity"]
    minimum_stock = request.form["minimum_stock"]
    supplier_id = request.form["supplier_id"]
    
    quantity = float(quantity)
    minimum_stock = float(minimum_stock)
    
    if quantity == 0:
        status = "OUT OF STOCK"
    elif quantity <= minimum_stock:
        status = "LOW"
    else:
        status = "OK"
        
    connection = get_db_connection()
    cursor = connection.cursor()
    
    cursor.execute(
        """
        INSERT INTO inventory
        (
            name,
            category,
            quantity,
            unit,
            minimum_stock,
            status,
            supplier_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            category,
            quantity,
            unit,
            minimum_stock,
            status,
            supplier_id
        )
    )

    connection.commit()
    connection.close()

    return redirect(url_for("inventory.inventory_management"))

@inventory_bp.route("/inventory/edit", methods=["POST"])
def edit_inventory_item():

    item_id = request.form["item_id"]
    name = request.form["name"]
    category = request.form["category"]
    unit = request.form["unit"]

    quantity = float(request.form["quantity"])
    minimum_stock = float(request.form["minimum_stock"])

    supplier_id = request.form["supplier_id"]


    # Status 자동 계산

    if quantity == 0:
        status = "OUT OF STOCK"

    elif quantity <= minimum_stock:
        status = "LOW"

    else:
        status = "OK"


    connection = get_db_connection()
    cursor = connection.cursor()


    cursor.execute("""
        UPDATE inventory
        SET
            name = ?,
            category = ?,
            quantity = ?,
            unit = ?,
            minimum_stock = ?,
            status = ?,
            supplier_id = ?
        WHERE id = ?
    """, (
        name,
        category,
        quantity,
        unit,
        minimum_stock,
        status,
        supplier_id,
        item_id
    ))


    connection.commit()
    connection.close()


    return redirect(url_for("inventory.inventory_management"))

@inventory_bp.route("/inventory/delete", methods=["POST"])
def delete_inventory_item():

    item_id = request.form["item_id"]

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        DELETE FROM restock_orders
        WHERE inventory_id = ?
    """, (item_id,))


    # Inventory item 삭제

    cursor.execute("""
        DELETE FROM inventory
        WHERE id = ?
    """, (item_id,))


    connection.commit()
    connection.close()


    return redirect(url_for("inventory.inventory_management"))
