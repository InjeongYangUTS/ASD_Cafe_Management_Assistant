from flask import Flask, render_template, url_for, request, redirect
import sqlite3
import os
import requests  

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(BACKEND_DIR)

DATABASE = os.path.join(
    BASE_DIR,
    "database",
    "inventory.db"
)

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "frontend", "templates"),
    static_folder=os.path.join(BASE_DIR, "assets")
)

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def get_ai_restock_recommendation(question, low_stock_items):

    inventory_context = ""

    for item in low_stock_items:

        inventory_context += (
            f"ID: {item['id']}, "
            f"Name: {item['name']}, "
            f"Current Quantity: {item['quantity']}, "
            f"Minimum Stock: {item['minimum_stock']}, "
            f"Status: {item['status']}\n"
        )


    prompt = f"""
You are an AI inventory assistant for a cafe.

Use ONLY the inventory information provided below.

CURRENT INVENTORY DATA:
{inventory_context}

USER QUESTION:
{question}

IMPORTANT STATUS RULES:
- The Status field provided in the inventory data is authoritative.
- If Status is "OUT OF STOCK", treat the item as out of stock.
- If Status is "LOW", treat the item as low stock.
- NEVER change, infer, or reinterpret an item's status.
- An item with a quantity greater than 0 must NOT be described as OUT OF STOCK unless its provided Status explicitly says "OUT OF STOCK".
- Do not place LOW items in the OUT OF STOCK category.
- Do not place OUT OF STOCK items in the LOW category.

Instructions:
- Answer the user's inventory-related question.
- Base your answer only on the inventory data provided.
- Prioritise OUT OF STOCK items over LOW items.
- Do not invent inventory items, quantities, minimum stock values, or statuses.
- Keep the answer concise and practical for cafe staff.
"""


    try:

        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "qwen2.5:0.5b",
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )

        response.raise_for_status()

        result = response.json()

        return result["response"]


    except requests.RequestException as error:

        return f"AI service unavailable: {error}"

# =========================================================
# INVENTORY DASHBOARD
# =========================================================

@app.route("/", methods=["GET", "POST"])
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

@app.route("/ai-restock-recommendation", methods=["POST"])
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

@app.route("/inventory/add", methods=["POST"])
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

    return redirect(url_for("inventory_management"))

@app.route("/inventory/edit", methods=["POST"])
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


    return redirect(url_for("inventory_management"))

@app.route("/inventory/delete", methods=["POST"])
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


    return redirect(url_for("inventory_management"))

# =========================================================
# Supplier Management
# =========================================================

@app.route("/supplier-management")
def supplier_management():

    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "").strip()

    per_page = 6

    if page < 1:
        page = 1

    connection = get_db_connection()
    cursor = connection.cursor()

    if search:

        search_value = f"%{search}%"

        cursor.execute("""
            SELECT COUNT(*)
            FROM suppliers
            WHERE name LIKE ?
               OR contact_name LIKE ?
               OR supplies LIKE ?
               OR status LIKE ?
        """, (
            search_value,
            search_value,
            search_value,
            search_value
        ))

    else:

        cursor.execute("""
            SELECT COUNT(*)
            FROM suppliers
        """)

    total_suppliers = cursor.fetchone()[0]
    total_pages = max(
        1,
        (total_suppliers + per_page - 1) // per_page
    )

    if page > total_pages:
        page = total_pages

    offset = (page - 1) * per_page

    if search:

        cursor.execute("""
            SELECT
                id,
                name,
                contact_name,
                phone,
                email,
                supplies,
                status
            FROM suppliers
            WHERE name LIKE ?
               OR contact_name LIKE ?
               OR supplies LIKE ?
               OR status LIKE ?
            ORDER BY id ASC
            LIMIT ? OFFSET ?
        """, (
            search_value,
            search_value,
            search_value,
            search_value,
            per_page,
            offset
        ))

    else:

        cursor.execute("""
            SELECT
                id,
                name,
                contact_name,
                phone,
                email,
                supplies,
                status
            FROM suppliers
            ORDER BY id ASC
            LIMIT ? OFFSET ?
        """, (
            per_page,
            offset
        ))

    suppliers = cursor.fetchall()

    connection.close()

    return render_template(
        "supplier_management.html",
        suppliers=suppliers,
        page=page,
        total_pages=total_pages,
        search=search
    )

@app.route("/supplier/add", methods=["POST"])
def add_supplier():

    name = request.form.get("name", "").strip()
    contact_name = request.form.get("contact_name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    supplies = request.form.get("supplies", "").strip()
    status = request.form.get("status", "Active").strip()


    # Supplier name은 필수

    if not name:
        return redirect(url_for("supplier_management"))


    # 허용된 Status만 저장

    if status not in ("Active", "Inactive"):
        status = "Active"


    connection = get_db_connection()
    cursor = connection.cursor()


    cursor.execute("""
        INSERT INTO suppliers (
            name,
            contact_name,
            email,
            phone,
            supplies,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        name,
        contact_name,
        email,
        phone,
        supplies,
        status
    ))


    connection.commit()


    # 새 supplier가 마지막 페이지에 표시되도록 계산

    cursor.execute("""
        SELECT COUNT(*)
        FROM suppliers
    """)

    total_suppliers = cursor.fetchone()[0]
    per_page = 6

    last_page = max(
        1,
        (total_suppliers + per_page - 1) // per_page
    )


    connection.close()


    return redirect(
        url_for(
            "supplier_management",
            page=last_page
        )
    )

@app.route("/supplier/edit", methods=["POST"])
def edit_supplier():

    supplier_id = request.form["supplier_id"]

    name = request.form.get("name", "").strip()
    contact_name = request.form.get("contact_name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    supplies = request.form.get("supplies", "").strip()
    status = request.form.get("status", "Active").strip()

    page = request.form.get("page", 1, type=int)
    search = request.form.get("search", "").strip()


    if not name:
        return redirect(
            url_for(
                "supplier_management",
                page=page,
                search=search
            )
        )


    if status not in ("Active", "Inactive"):
        status = "Active"


    connection = get_db_connection()
    cursor = connection.cursor()


    cursor.execute("""
        UPDATE suppliers
        SET
            name = ?,
            contact_name = ?,
            email = ?,
            phone = ?,
            supplies = ?,
            status = ?
        WHERE id = ?
    """, (
        name,
        contact_name,
        email,
        phone,
        supplies,
        status,
        supplier_id
    ))


    connection.commit()
    connection.close()


    return redirect(
        url_for(
            "supplier_management",
            page=page,
            search=search
        )
    )

@app.route("/supplier/delete", methods=["POST"])
def delete_supplier():

    supplier_id = request.form["supplier_id"]

    page = request.form.get("page", 1, type=int)
    search = request.form.get("search", "").strip()

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        DELETE FROM restock_orders
        WHERE supplier_id = ?
    """, (supplier_id,))

    cursor.execute("""
        UPDATE inventory
        SET supplier_id = NULL
        WHERE supplier_id = ?
    """, (supplier_id,))

    cursor.execute("""
        DELETE FROM suppliers
        WHERE id = ?
    """, (supplier_id,))


    connection.commit()
    connection.close()


    return redirect(
        url_for(
            "supplier_management",
            page=page,
            search=search
        )
    )

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