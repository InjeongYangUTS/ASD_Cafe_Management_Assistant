from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from backend_client import BackendError, call_backend


restock_bp = Blueprint("restock", __name__)
ALLOWED_STATUSES = ("Pending", "Ordered", "Delivered", "Cancelled")


@restock_bp.get("/restock-order-management")
def restock_order_management():
    selected_status = request.args.get("status", "All").strip()
    if selected_status not in ("All", *ALLOWED_STATUSES):
        selected_status = "All"
    page = request.args.get("page", 1, type=int)
    data = call_backend("GET", "/api/restock-orders", params={"page": page, "status": selected_status, "per_page": 6})
    suppliers = call_backend("GET", "/api/suppliers", params={"page": 1, "per_page": 100})["suppliers"]
    inventory = call_backend("GET", "/api/inventory", params={"page": 1, "per_page": 100})["items"]
    return render_template(
        "restock_order_management.html",
        orders=data["orders"],
        suppliers=suppliers,
        inventory_items=inventory,
        selected_status=selected_status,
        page=data["page"],
        total_pages=data["total_pages"],
    )


def order_payload():
    return {
        "supplier_id": request.form.get("supplier_id"),
        "inventory_id": request.form.get("inventory_id"),
        "quantity": request.form.get("quantity"),
        "order_date": request.form.get("order_date", "").strip() or date.today().isoformat(),
        "status": request.form.get("status", "Pending").strip(),
    }


@restock_bp.post("/restock/add")
def add_restock_order():
    try:
        call_backend("POST", "/api/restock-orders", json=order_payload())
        flash("Restock order created successfully.", "success")
    except BackendError as exc:
        flash(exc.message, "error")
    return redirect(url_for("restock.restock_order_management"))


@restock_bp.post("/restock/edit")
def edit_restock_order():
    try:
        call_backend("PUT", f"/api/restock-orders/{request.form.get('order_id')}", json=order_payload())
        flash("Restock order updated successfully.", "success")
    except BackendError as exc:
        flash(exc.message, "error")
    return redirect(url_for("restock.restock_order_management"))


@restock_bp.post("/restock/delete")
def delete_restock_order():
    try:
        call_backend("DELETE", f"/api/restock-orders/{request.form.get('order_id')}")
        flash("Restock order deleted successfully.", "success")
    except BackendError as exc:
        flash(exc.message, "error")
    return redirect(url_for("restock.restock_order_management"))
