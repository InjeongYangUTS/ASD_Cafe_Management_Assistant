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

@dashboard_bp.get("/api/mcp/test")
def mcp_test():
    result = call_backend(
        "GET",
        "/api/mcp/test",
        timeout = 30,
    )
    return jsonify(result)

@dashboard_bp.post("/api/rag/query")
def rag_query():
    body = request.get_json(silent=True) or {}
    
    result = call_backend(
        "POST",
        "/api/rag/query",
        timeout = 180,
        json = body,
    )
    
    return jsonify(result)

@dashboard_bp.post("/api/multi-agent/workflows")
def multi_agent_start():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "A JSON object is required."}), 400
    task = body.get("task", "")
    if not isinstance(task, str) or not task.strip():
        return jsonify({"error": "Enter a review task."}), 400
    if len(task) > 1000:
        return jsonify({"error": "Task is too long."}), 400
    result = call_backend(
        "POST", "/api/multi-agent/workflows",
        timeout=135, json={"task": task.strip()},
    )
    return jsonify(result), 201


@dashboard_bp.get("/api/multi-agent/workflows/<workflow_id>")
def multi_agent_details(workflow_id):
    result = call_backend(
        "GET", f"/api/multi-agent/workflows/{workflow_id}", timeout=20,
    )
    return jsonify(result)


@dashboard_bp.post("/api/multi-agent/workflows/<workflow_id>/human-review")
def multi_agent_review(workflow_id):
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "A JSON object is required."}), 400
    decision = body.get("decision")
    comments = body.get("comments", "")
    if decision not in {"approve", "correct", "reject", "partial_accept"}:
        return jsonify({"error": "Invalid review decision."}), 400
    if not isinstance(comments, str):
        return jsonify({"error": "Comments must be text."}), 400
    if decision == "correct" and not comments.strip():
        return jsonify({"error": "Enter correction comments."}), 400
    result = call_backend(
        "POST", f"/api/multi-agent/workflows/{workflow_id}/human-review",
        timeout=135, json={"decision": decision, "comments": comments},
    )
    return jsonify(result)
