from flask import Blueprint, render_template

restock_bp = Blueprint(
    "restock",
    __name__
)

# =========================================================
# Restock Order Management
# =========================================================

@restock_bp.route("/restock-order-management")
def restock_order_management():
    return render_template("restock_order_management.html")
