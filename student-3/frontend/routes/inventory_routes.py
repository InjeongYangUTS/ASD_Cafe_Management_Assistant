from flask import Blueprint, redirect, render_template, request, url_for

from backend_client import call_backend


inventory_bp = Blueprint("inventory", __name__)


@inventory_bp.get("/inventory-management")
def inventory_management():
    page = request.args.get("page", 1, type=int)
    category = request.args.get("category", "").strip()
    data = call_backend("GET", "/api/inventory", params={"page": page, "category": category, "per_page": 6})
    supplier_data = call_backend("GET", "/api/suppliers", params={"page": 1, "per_page": 100})
    return render_template(
        "inventory_management.html",
        inventory_items=data["items"],
        suppliers=supplier_data["suppliers"],
        page=data["page"],
        total_pages=data["total_pages"],
        selected_category=category,
    )


def inventory_payload():
    return {
        "name": request.form.get("name", "").strip(),
        "category": request.form.get("category", "").strip(),
        "unit": request.form.get("unit", "").strip(),
        "quantity": request.form.get("quantity"),
        "minimum_stock": request.form.get("minimum_stock"),
        "supplier_id": request.form.get("supplier_id") or None,
    }


@inventory_bp.post("/inventory/add")
def add_inventory_item():
    call_backend("POST", "/api/inventory", json=inventory_payload())
    return redirect(url_for("inventory.inventory_management"))


@inventory_bp.post("/inventory/edit")
def edit_inventory_item():
    item_id = request.form["item_id"]
    call_backend("PUT", f"/api/inventory/{item_id}", json=inventory_payload())
    return redirect(url_for("inventory.inventory_management"))


@inventory_bp.post("/inventory/delete")
def delete_inventory_item():
    call_backend("DELETE", f"/api/inventory/{request.form['item_id']}")
    return redirect(url_for("inventory.inventory_management"))
