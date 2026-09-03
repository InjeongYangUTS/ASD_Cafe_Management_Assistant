from flask import Blueprint, render_template, request, redirect, url_for
from db import get_db_connection

supplier_bp = Blueprint(
    "supplier",
    __name__
)

# =========================================================
# Supplier Management
# =========================================================

@supplier_bp.route("/supplier-management")
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

@supplier_bp.route("/supplier/add", methods=["POST"])
def add_supplier():

    name = request.form.get("name", "").strip()
    contact_name = request.form.get("contact_name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    supplies = request.form.get("supplies", "").strip()
    status = request.form.get("status", "Active").strip()


    # Supplier name은 필수

    if not name:
        return redirect(url_for("supplier.supplier_management"))


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
            "supplier.supplier_management",
            page=last_page
        )
    )

@supplier_bp.route("/supplier/edit", methods=["POST"])
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
                "supplier.supplier_management",
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
            "supplier.supplier_management",
            page=page,
            search=search
        )
    )

@supplier_bp.route("/supplier/delete", methods=["POST"])
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
            "supplier.supplier_management",
            page=page,
            search=search
        )
    )
