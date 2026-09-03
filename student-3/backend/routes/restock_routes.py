from datetime import date

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for
)

from db import get_db_connection


restock_bp = Blueprint(
    "restock",
    __name__
)


# =========================================================
# SETTINGS
# =========================================================

ORDERS_PER_PAGE = 6

ALLOWED_STATUSES = (
    "Pending",
    "Ordered",
    "Delivered",
    "Cancelled"
)


# =========================================================
# RESTOCK ORDER MANAGEMENT
# =========================================================

@restock_bp.route(
    "/restock-order-management",
    methods=["GET"]
)
def restock_order_management():

    selected_status = request.args.get(
        "status",
        "All"
    ).strip()

    if selected_status not in ("All", *ALLOWED_STATUSES):
        selected_status = "All"

    page = request.args.get(
        "page",
        1,
        type=int
    )

    if page is None or page < 1:
        page = 1

    connection = get_db_connection()

    # -----------------------------------------------------
    # COUNT ORDERS
    # -----------------------------------------------------

    if selected_status == "All":

        total_orders = connection.execute("""
            SELECT COUNT(*)
            FROM restock_orders
        """).fetchone()[0]

    else:

        total_orders = connection.execute("""
            SELECT COUNT(*)
            FROM restock_orders
            WHERE status = ?
        """, (
            selected_status,
        )).fetchone()[0]

    total_pages = max(
        1,
        (total_orders + ORDERS_PER_PAGE - 1)
        // ORDERS_PER_PAGE
    )

    if page > total_pages:
        page = total_pages

    offset = (page - 1) * ORDERS_PER_PAGE

    # -----------------------------------------------------
    # GET RESTOCK ORDERS
    # -----------------------------------------------------

    if selected_status == "All":

        orders = connection.execute("""
            SELECT
                restock_orders.id,
                restock_orders.inventory_id,
                restock_orders.supplier_id,
                restock_orders.quantity,
                restock_orders.order_date,
                restock_orders.status,
                inventory.name AS item_name,
                suppliers.name AS supplier_name
            FROM restock_orders
            JOIN inventory
                ON restock_orders.inventory_id = inventory.id
            JOIN suppliers
                ON restock_orders.supplier_id = suppliers.id
            ORDER BY
                restock_orders.order_date DESC,
                restock_orders.id DESC
            LIMIT ?
            OFFSET ?
        """, (
            ORDERS_PER_PAGE,
            offset
        )).fetchall()

    else:

        orders = connection.execute("""
            SELECT
                restock_orders.id,
                restock_orders.inventory_id,
                restock_orders.supplier_id,
                restock_orders.quantity,
                restock_orders.order_date,
                restock_orders.status,
                inventory.name AS item_name,
                suppliers.name AS supplier_name
            FROM restock_orders
            JOIN inventory
                ON restock_orders.inventory_id = inventory.id
            JOIN suppliers
                ON restock_orders.supplier_id = suppliers.id
            WHERE restock_orders.status = ?
            ORDER BY
                restock_orders.order_date DESC,
                restock_orders.id DESC
            LIMIT ?
            OFFSET ?
        """, (
            selected_status,
            ORDERS_PER_PAGE,
            offset
        )).fetchall()

    # -----------------------------------------------------
    # GET SUPPLIERS FOR MODALS
    # -----------------------------------------------------

    suppliers = connection.execute("""
        SELECT
            id,
            name
        FROM suppliers
        ORDER BY name
    """).fetchall()

    # -----------------------------------------------------
    # GET INVENTORY ITEMS FOR MODALS
    # -----------------------------------------------------

    inventory_items = connection.execute("""
        SELECT
            id,
            name,
            unit
        FROM inventory
        ORDER BY name
    """).fetchall()

    connection.close()

    return render_template(
        "restock_order_management.html",
        orders=orders,
        suppliers=suppliers,
        inventory_items=inventory_items,
        selected_status=selected_status,
        page=page,
        total_pages=total_pages
    )


# =========================================================
# ADD RESTOCK ORDER
# =========================================================

@restock_bp.route(
    "/restock/add",
    methods=["POST"]
)
def add_restock_order():

    supplier_id = request.form.get(
        "supplier_id",
        type=int
    )

    inventory_id = request.form.get(
        "inventory_id",
        type=int
    )

    quantity = request.form.get(
        "quantity",
        type=float
    )

    order_date = request.form.get(
        "order_date",
        ""
    ).strip()

    status = request.form.get(
        "status",
        "Pending"
    ).strip()

    if supplier_id is None:
        flash(
            "Please select a supplier.",
            "error"
        )

        return redirect(
            url_for(
                "restock.restock_order_management"
            )
        )

    if inventory_id is None:
        flash(
            "Please select an inventory item.",
            "error"
        )

        return redirect(
            url_for(
                "restock.restock_order_management"
            )
        )

    if quantity is None or quantity <= 0:
        flash(
            "Quantity must be greater than zero.",
            "error"
        )

        return redirect(
            url_for(
                "restock.restock_order_management"
            )
        )

    if not order_date:
        order_date = date.today().isoformat()

    if status not in ALLOWED_STATUSES:
        status = "Pending"

    connection = get_db_connection()

    supplier_exists = connection.execute("""
        SELECT id
        FROM suppliers
        WHERE id = ?
    """, (
        supplier_id,
    )).fetchone()

    inventory_exists = connection.execute("""
        SELECT id
        FROM inventory
        WHERE id = ?
    """, (
        inventory_id,
    )).fetchone()

    if supplier_exists is None:
        connection.close()

        flash(
            "The selected supplier does not exist.",
            "error"
        )

        return redirect(
            url_for(
                "restock.restock_order_management"
            )
        )

    if inventory_exists is None:
        connection.close()

        flash(
            "The selected inventory item does not exist.",
            "error"
        )

        return redirect(
            url_for(
                "restock.restock_order_management"
            )
        )

    connection.execute("""
        INSERT INTO restock_orders (
            inventory_id,
            supplier_id,
            quantity,
            order_date,
            status
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        inventory_id,
        supplier_id,
        quantity,
        order_date,
        status
    ))

    connection.commit()
    connection.close()

    flash(
        "Restock order created successfully.",
        "success"
    )

    return redirect(
        url_for(
            "restock.restock_order_management"
        )
    )


# =========================================================
# EDIT RESTOCK ORDER
# =========================================================

@restock_bp.route(
    "/restock/edit",
    methods=["POST"]
)
def edit_restock_order():

    order_id = request.form.get(
        "order_id",
        type=int
    )

    supplier_id = request.form.get(
        "supplier_id",
        type=int
    )

    inventory_id = request.form.get(
        "inventory_id",
        type=int
    )

    quantity = request.form.get(
        "quantity",
        type=float
    )

    order_date = request.form.get(
        "order_date",
        ""
    ).strip()

    status = request.form.get(
        "status",
        ""
    ).strip()

    if (
        order_id is None
        or supplier_id is None
        or inventory_id is None
        or quantity is None
        or quantity <= 0
        or not order_date
        or status not in ALLOWED_STATUSES
    ):
        flash(
            "Please enter valid order information.",
            "error"
        )

        return redirect(
            url_for(
                "restock.restock_order_management"
            )
        )

    connection = get_db_connection()

    existing_order = connection.execute("""
        SELECT id
        FROM restock_orders
        WHERE id = ?
    """, (
        order_id,
    )).fetchone()

    if existing_order is None:
        connection.close()

        flash(
            "The selected restock order does not exist.",
            "error"
        )

        return redirect(
            url_for(
                "restock.restock_order_management"
            )
        )

    connection.execute("""
        UPDATE restock_orders
        SET
            inventory_id = ?,
            supplier_id = ?,
            quantity = ?,
            order_date = ?,
            status = ?
        WHERE id = ?
    """, (
        inventory_id,
        supplier_id,
        quantity,
        order_date,
        status,
        order_id
    ))

    connection.commit()
    connection.close()

    flash(
        "Restock order updated successfully.",
        "success"
    )

    return redirect(
        url_for(
            "restock.restock_order_management"
        )
    )


# =========================================================
# DELETE RESTOCK ORDER
# =========================================================

@restock_bp.route(
    "/restock/delete",
    methods=["POST"]
)
def delete_restock_order():

    order_id = request.form.get(
        "order_id",
        type=int
    )

    if order_id is None:
        flash(
            "No restock order was selected.",
            "error"
        )

        return redirect(
            url_for(
                "restock.restock_order_management"
            )
        )

    connection = get_db_connection()

    existing_order = connection.execute("""
        SELECT id
        FROM restock_orders
        WHERE id = ?
    """, (
        order_id,
    )).fetchone()

    if existing_order is None:
        connection.close()

        flash(
            "The selected restock order does not exist.",
            "error"
        )

        return redirect(
            url_for(
                "restock.restock_order_management"
            )
        )

    connection.execute("""
        DELETE FROM restock_orders
        WHERE id = ?
    """, (
        order_id,
    ))

    connection.commit()
    connection.close()

    flash(
        "Restock order deleted successfully.",
        "success"
    )

    return redirect(
        url_for(
            "restock.restock_order_management"
        )
    )