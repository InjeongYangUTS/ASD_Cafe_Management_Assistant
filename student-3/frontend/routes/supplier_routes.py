import math

from flask import Blueprint, redirect, render_template, request, url_for

from backend_client import call_backend


supplier_bp = Blueprint("supplier", __name__)


@supplier_bp.get("/supplier-management")
def supplier_management():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "").strip()
    data = call_backend("GET", "/api/suppliers", params={"page": page, "search": search, "per_page": 6})
    return render_template("supplier_management.html", suppliers=data["suppliers"], page=data["page"], total_pages=data["total_pages"], search=search)


def supplier_payload():
    return {
        "name": request.form.get("name", "").strip(),
        "contact_name": request.form.get("contact_name", "").strip(),
        "email": request.form.get("email", "").strip(),
        "phone": request.form.get("phone", "").strip(),
        "supplies": request.form.get("supplies", "").strip(),
        "status": request.form.get("status", "Active").strip(),
    }


@supplier_bp.post("/supplier/add")
def add_supplier():
    data = call_backend("POST", "/api/suppliers", json=supplier_payload())
    last_page = max(1, math.ceil(data["total"] / 6))
    return redirect(url_for("supplier.supplier_management", page=last_page))


@supplier_bp.post("/supplier/edit")
def edit_supplier():
    supplier_id = request.form["supplier_id"]
    page = request.form.get("page", 1, type=int)
    search = request.form.get("search", "").strip()
    call_backend("PUT", f"/api/suppliers/{supplier_id}", json=supplier_payload())
    return redirect(url_for("supplier.supplier_management", page=page, search=search))


@supplier_bp.post("/supplier/delete")
def delete_supplier():
    supplier_id = request.form["supplier_id"]
    page = request.form.get("page", 1, type=int)
    search = request.form.get("search", "").strip()
    call_backend("DELETE", f"/api/suppliers/{supplier_id}")
    return redirect(url_for("supplier.supplier_management", page=page, search=search))
