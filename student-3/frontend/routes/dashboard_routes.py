from flask import Blueprint, jsonify, render_template, request

from backend_client import BackendError, call_backend


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/inventory/", methods=["GET", "POST"])
def inventory_dashboard():
    data = call_backend("GET", "/api/dashboard")
    summary = data["summary"]
    low_stock_items = []
    for item in data["low_stock_items"]:
        low_stock_items.append({
            **item,
            "quantity": f"{float(item['quantity']):g} {item['unit']}",
            "minimum_stock": f"{float(item['minimum_stock']):g} {item['unit']}",
        })
    recent_restock_orders = []
    for order in data["recent_restock_orders"]:
        recent_restock_orders.append({**order, "name": order["item_name"]})
    ai_question = ""
    ai_answer = ""
    if request.method == "POST":
        ai_question = request.form.get("question", "").strip()
        if ai_question:
            try:
                ai_answer = call_backend("POST", "/api/ai/restock-recommendation", timeout=120, json={"question": ai_question})["adapt"]
            except BackendError as exc:
                ai_answer = exc.message
    return render_template(
        "inventory_dashboard.html",
        total_items=summary["total_items"],
        low_stock_count=summary["low_stock_count"],
        out_of_stock_count=summary["out_of_stock_count"],
        pending_orders_count=summary["pending_orders_count"],
        low_stock_items=low_stock_items,
        recent_restock_orders=recent_restock_orders,
        ai_question=ai_question,
        ai_answer=ai_answer,
    )


@dashboard_bp.post("/ai-restock-recommendation")
def ai_restock_recommendation():
    body = request.get_json(silent=True) or {}
    return jsonify(call_backend("POST", "/api/ai/restock-recommendation", timeout=120, json=body))
