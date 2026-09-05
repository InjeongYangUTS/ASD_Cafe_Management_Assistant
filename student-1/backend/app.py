import os

from flask import Flask, jsonify, request, session

import ai
from services.database_api import (
    DatabaseClient,
    MenuClient,
    OrderClient,
    ServiceError,
)
from services.llm_client import LLMClient

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY", "temporary-secret-key")

db = DatabaseClient()
orders = OrderClient()
menu = MenuClient()

llm = LLMClient()

AI_BATCH_LIMIT = int(os.environ.get("AI_BATCH_LIMIT", 5))


def menu_context(reviews):
    """The menu vocabulary and order lines used to attribute reviews to menu items; both degrade to empty."""
    vocabulary, source = menu.get_vocabulary()
    order_ids = [review.get("order_id") for review in reviews
                 if review.get("order_id")]
    return vocabulary, orders.items_by_order(order_ids), source


@app.errorhandler(ServiceError)
def handle_service_error(exc):
    payload = {"error": exc.message}
    if exc.detail:
        payload["detail"] = exc.detail
    return jsonify(payload), exc.status_code


def bad_request(message, **extra):
    payload = {"error": message}
    payload.update(extra)
    return jsonify(payload), 400


def require_owner(review, body):
    """Allow the request only if the signed session cookie owns the review; 403 otherwise."""
    if session.get("staff_id"):
        return None

    signed_in = session.get("customer_id")

    if signed_in in (None, ""):
        return jsonify({
            "error": "You must be signed in to change your own review."
        }), 401

    if int(signed_in) != int(review["customer_id"]):
        return jsonify({
            "error": "this review belongs to another customer"
        }), 403

    return None


@app.get("/api/health")
def health():
    """Liveness for the container healthcheck; ?deep=1 adds the optional dependencies."""
    try:
        database = db.health()
        database["reachable"] = True
    except ServiceError as exc:
        database = {"reachable": False, "detail": exc.message}

    dependencies = {"feedback_database": database}
    deep = request.args.get("deep") in ("1", "true", "yes")

    if deep:
        dependencies["order_service"] = orders.health()
        dependencies["menu_service"] = menu.health()
        dependencies["ollama"] = llm.health()

    return jsonify({
        "service": "student-1-backend",
        "feature": "Customer Feedback & Reviews",
        "owner": "Student 1 - Hangyeol Yi",
        "status": "healthy" if database.get("reachable") else "degraded",
        "optional_dependencies_checked": deep,
        "dependencies": dependencies,
    }), 200 if database.get("reachable") else 503


@app.get("/api/feedback")
def list_feedback():
    return jsonify(db.list_feedback(
        customer_id=request.args.get("customer_id"),
        status=request.args.get("status"),
        sentiment=request.args.get("sentiment"),
        category=request.args.get("category"),
        min_rating=request.args.get("min_rating"),
        max_rating=request.args.get("max_rating"),
        analysed=request.args.get("analysed"),
        days=request.args.get("days"),
        needs_reply=request.args.get("needs_reply"),
        submitted_from=request.args.get("submitted_from"),
        submitted_to=request.args.get("submitted_to"),
        search=request.args.get("search"),
        sort=request.args.get("sort"),
        limit=request.args.get("limit", 100),
    ))


@app.post("/api/feedback")
def create_feedback():
    body = request.get_json(silent=True) or {}

    if not body.get("customer_id"):
        return bad_request("You must be signed in to leave a review.")

    if not str(body.get("comment") or "").strip():
        return bad_request("Please write a short comment before submitting.")

    try:
        rating = int(body.get("rating"))
    except (TypeError, ValueError):
        return bad_request("Please choose a star rating from 1 to 5.")

    if not 1 <= rating <= 5:
        return bad_request("Please choose a star rating from 1 to 5.")

    comment = body["comment"].strip()
    title = (body.get("title") or "").strip() or None

    vocabulary, _source = menu.get_vocabulary()
    category = ai.classify_category("%s %s" % (title or "", comment), vocabulary)

    payload = {
        "customer_id": body["customer_id"],
        "customer_name": body.get("customer_name"),
        "rating": rating,
        "title": title,
        "comment": comment,
        "category": category,
        "actor": "customer:%s" % body["customer_id"],
    }


    created = db.create_feedback(payload)

    try:
        measured = ai.measure_review(created)
        created = db.save_analysis(created["id"], {
            "sentiment": measured["sentiment"],
            "sentiment_score": measured["sentiment_score"],
            "ai_summary": ai.fallback_summary(created, measured),
            "ai_issues": measured["issues"],
            "ai_model": ai.RULES_MODEL,
        })
    except ServiceError:
        pass

    return jsonify(created), 201


@app.get("/api/feedback/<int:feedback_id>")
def get_feedback(feedback_id):
    return jsonify(db.get_feedback(feedback_id))


@app.put("/api/feedback/<int:feedback_id>")
def update_feedback(feedback_id):
    body = request.get_json(silent=True) or {}
    review = db.get_feedback(feedback_id)

    denied = require_owner(review, body)
    if denied:
        return denied

    if review["status"] == "ARCHIVED":
        return bad_request("An archived review can no longer be edited.")

    updates = {field: body[field]
               for field in ("rating", "title", "comment")
               if field in body}

    if not updates:
        return bad_request("Nothing to update.")

    if "comment" in updates and not str(updates["comment"] or "").strip():
        return bad_request("Please write a short comment before saving.")

    if "comment" in updates or "title" in updates:
        vocabulary, _source = menu.get_vocabulary()
        updates["category"] = ai.classify_category(
            "%s %s" % (updates.get("title", review.get("title")) or "",
                       updates.get("comment", review.get("comment")) or ""),
            vocabulary,
        )

    updates["actor"] = "customer:%s" % review["customer_id"]
    updates["actor_role"] = "CUSTOMER"

    return jsonify(db.update_feedback(feedback_id, updates))


@app.delete("/api/feedback/<int:feedback_id>")
def delete_feedback(feedback_id):
    body = request.get_json(silent=True) or {}
    review = db.get_feedback(feedback_id)

    denied = require_owner(review, body)
    if denied:
        return denied

    return jsonify(db.delete_feedback(feedback_id, {
        "actor": body.get("actor") or ("customer:%s" % review["customer_id"]),
        "actor_role": body.get("actor_role", "CUSTOMER"),
    }))


@app.post("/api/feedback/<int:feedback_id>/response")
def respond(feedback_id):
    """Staff-only: publish a reply to the customer."""
    if not session.get("staff_id"):
        return jsonify({
            "error": "Only signed-in staff can reply to a review."
        }), 401

    body = request.get_json(silent=True) or {}
    message = str(body.get("staff_response") or "").strip()

    if not message:
        return bad_request("Write a response before publishing it.")

    review = db.get_feedback(feedback_id)

    updates = {
        "staff_response": message,
        "actor": "staff:%s" % session["staff_id"],
        "actor_role": "STAFF",
    }

    if review["status"] == "SUBMITTED":
        updates["status"] = "ACKNOWLEDGED"

    return jsonify(db.update_feedback(feedback_id, updates))


@app.get("/api/feedback/<int:feedback_id>/logs")
def feedback_logs(feedback_id):
    return jsonify(db.feedback_logs(feedback_id))


@app.get("/api/logs")
def list_logs():
    return jsonify(db.list_logs(
        feedback_id=request.args.get("feedback_id"),
        action=request.args.get("action"),
        limit=request.args.get("limit", 50),
    ))


@app.get("/api/summary")
def summary():
    """Feedback figures for the rest of the team; no other service reads feedback.db."""
    stats = db.stats()
    reviews = db.list_feedback(limit=500)["feedback"]
    vocabulary, order_items, menu_source = menu_context(reviews)
    metrics = ai.measure_store(reviews, menu_vocabulary=vocabulary,
                               order_items=order_items)

    return jsonify({
        "service": "student-1-backend",
        "review_count": stats["row_counts"]["customer_feedback"],
        "average_rating": stats["average_rating"],
        "rating_distribution": stats["rating_distribution"],
        "by_status": stats["by_status"],
        "by_category": stats["by_category"],
        "by_sentiment": stats["by_sentiment"],
        "unanalysed_count": len(rule_based_reviews()),
        "top_issues": metrics["top_issues"][:5],
        "top_praise": metrics["top_praise"],
        "weakest_categories": metrics["weakest_categories"],
        "menu_source": menu_source,
        "menu_feedback": metrics["menu_feedback"],
        "worst_menu_items": metrics["worst_menu_items"],
        "best_menu_items": metrics["best_menu_items"],
    })


def _store_analysis(feedback_id, analysis):
    """Persist one AI result through the database API and return the row."""
    return db.save_analysis(feedback_id, {
        "sentiment": analysis["sentiment"],
        "sentiment_score": analysis["sentiment_score"],
        "ai_summary": analysis["ai_summary"],
        "ai_issues": analysis["ai_issues"],
        "ai_model": analysis["model"],
    })


def rule_based_reviews(limit=None):
    """Reviews whose verdict came from the rules and can still be upgraded by the LLM."""
    reviews = db.list_feedback(limit=500)["feedback"]
    pending = [review for review in reviews
               if (review.get("ai_model") or ai.RULES_MODEL) == ai.RULES_MODEL
               or not review.get("analysed_at")]
    return pending[:limit] if limit else pending


@app.post("/api/ai/analyse-pending")
def analyse_pending():
    """Upgrade rule-based verdicts with the language model."""
    pending = rule_based_reviews(AI_BATCH_LIMIT)

    processed = []
    for review in pending:
        analysis = ai.analyse_review(review, llm)
        _store_analysis(review["id"], analysis)
        processed.append({
            "id": review["id"],
            "rating": review["rating"],
            "title": review["title"],
            "sentiment": analysis["sentiment"],
            "sentiment_score": analysis["sentiment_score"],
            "ai_issues": analysis["ai_issues"],
            "ai_summary": analysis["ai_summary"],
            "mode": analysis["mode"],
            "corrections": analysis["corrections"],
        })

    remaining = len(rule_based_reviews())

    return jsonify({
        "analysed": len(processed),
        "remaining": remaining,
        "batch_limit": AI_BATCH_LIMIT,
        "model": llm.model,
        "results": processed,
    })


@app.post("/api/ai/ask")
def ask():
    """Answer one free-text staff question against the same measured summary shown on screen."""
    body = request.get_json(silent=True) or {}
    question = str(body.get("question") or "").strip()

    if not question:
        return bad_request("Type a question first.")
    if len(question) > 300:
        return bad_request("Please keep the question under 300 characters.")

    reviews = db.list_feedback(limit=500)["feedback"]
    vocabulary, order_items, menu_source = menu_context(reviews)
    result = ai.answer_question(question, reviews, llm,
                                menu_vocabulary=vocabulary,
                                order_items=order_items)
    result["menu_source"] = menu_source

    result.pop("metrics", None)

    return jsonify(result)


@app.errorhandler(404)
def not_found(_):
    return jsonify({"error": "endpoint not found"}), 404


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8100)),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
