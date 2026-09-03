"""
Student 1 (Hangyeol Yi) - Customer Feedback & Reviews
BACKEND / API MICROSERVICE  (container: student-1-backend, port 8100)

Business logic for customer reviews. Owns no data of its own: it reads
and writes reviews through student-1-database, reads order history
through the Order service's API, and runs AI-Mode through the shared
Ollama runtime.

Endpoints
    GET    /api/health

    GET    /api/feedback                ?customer_id= &status= &sentiment=
                                        &category= &min_rating= &limit=
    POST   /api/feedback
    GET    /api/feedback/<id>
    PUT    /api/feedback/<id>
    DELETE /api/feedback/<id>
    POST   /api/feedback/<id>/response
    GET    /api/feedback/<id>/logs

    GET    /api/logs
    GET    /api/summary                 store-wide figures for other services

    POST   /api/ai/ask                  answer one free-text staff question
    POST   /api/ai/analyse-pending      analyse every unanalysed review
"""

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

# Same key as the shared entry point and the frontend, so the signed
# session cookie the browser already carries can be verified here. This
# service issues no cookie of its own; it only reads.
app.secret_key = os.environ.get("SECRET_KEY", "temporary-secret-key")

db = DatabaseClient()
orders = OrderClient()
menu = MenuClient()

# AI-Mode: the OpenAI SDK pointed at the local Ollama /v1 endpoint, as set
# out in the course configuration guide. Model comes from student-1/.env.
llm = LLMClient()

# How many reviews one /api/ai/analyse-pending call will process. An
# Ollama generation takes seconds, so an unbounded batch would time the
# request out; the frontend simply calls again for the next batch.
AI_BATCH_LIMIT = int(os.environ.get("AI_BATCH_LIMIT", 5))


def menu_context(reviews):
    """
    Everything the analysis needs to attribute reviews to menu items:
    the menu vocabulary, and the order lines behind any review that does
    not name an item itself. Both come over HTTP and both degrade to
    empty, in which case the per-item breakdown is simply absent rather
    than wrong.
    """
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
    """
    A customer may only edit or delete their OWN review.

    Identity comes from the SIGNED SESSION COOKIE, never from the request
    body. An earlier version trusted a customer_id field, which meant
    anyone who knew whose review it was could edit it by claiming to be
    that person - and the owner's id is visible in the staff board and in
    /api/summary. A body field states an intention; a signed cookie the
    caller cannot forge states a fact.

    403 rather than 404 is deliberate: the review does exist, the caller
    simply may not touch it. Hiding that would mislead the owner too.
    """
    # Staff identity is read from the cookie too. An earlier version
    # accepted actor_role="STAFF" from the request body, which meant a
    # single extra JSON field let anyone edit any review.
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


# =====================================================================
# Health
# =====================================================================

@app.get("/api/health")
def health():
    """
    Liveness for the container healthcheck, and - with ?deep=1 - the full
    dependency report used on screen and in the technical report.

    The shallow check probes only the feedback database. That is
    deliberate: the Order service, the Menu API and Ollama are all
    OPTIONAL to this feature, and probing three services that may be down
    took roughly twelve seconds, which is longer than the Docker
    healthcheck timeout. A slow health endpoint would mark this container
    unhealthy and block every service that depends on it - the health
    check would be the outage.
    """
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
        # Only the database decides health: reviews can be written and read
        # without any of the optional services.
        "status": "healthy" if database.get("reachable") else "degraded",
        "optional_dependencies_checked": deep,
        "dependencies": dependencies,
    }), 200 if database.get("reachable") else 503


# =====================================================================
# Feedback : CRUD
# =====================================================================

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

    # The customer gives a star rating and a comment. The category is
    # derived from the wording, so the staff screen can still filter by
    # problem area.
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

    # No order is attached. The order_id and order_number columns exist and
    # the seed populates them, but nothing verifies the link yet - that is
    # Release 1 work with the Order service.

    created = db.create_feedback(payload)

    # Analyse straight away with the rules. Calling the LLM here would make
    # the customer wait for their own Post button, and a review the staff
    # board shows as unanalysed cannot be triaged. The LLM pass upgrades it
    # later - see /api/ai/analyse-pending.
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
        # The review is saved and that is what matters. An unanalysed
        # review is a smaller problem than a lost one.
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

    # Editing the wording can change what the review is about, so the
    # derived category is recomputed rather than left stale.
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
        # Attributed to whoever is actually signed in, not to whatever the
        # caller put in the body.
        "actor": "staff:%s" % session["staff_id"],
        "actor_role": "STAFF",
    }

    # Answering a review is what "handled" means, so a response moves an
    # untouched review out of SUBMITTED without the staff member having
    # to remember a second click.
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


# =====================================================================
# Store-wide data for other services
# =====================================================================

@app.get("/api/summary")
def summary():
    """
    Feedback data for store-wide analysis, exposed for the rest of the
    team. Any other backend that wants review figures calls this - it
    never reads feedback.db.
    """
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
        # Reviews still carrying a rule-based verdict rather than an
        # LLM one. Nothing is ever simply "unanalysed" any more.
        "unanalysed_count": len(rule_based_reviews()),
        "top_issues": metrics["top_issues"][:5],
        "top_praise": metrics["top_praise"],
        "weakest_categories": metrics["weakest_categories"],
        "menu_source": menu_source,
        "menu_feedback": metrics["menu_feedback"],
        "worst_menu_items": metrics["worst_menu_items"],
        "best_menu_items": metrics["best_menu_items"],
    })


# =====================================================================
# AI-Mode
# =====================================================================

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
    """
    Reviews whose verdict came from the rules rather than the LLM.

    Every review is analysed on arrival, so "not analysed" no longer
    exists. What is still worth doing is upgrading a rule-based verdict
    with the model, and that is what this selects. Filtering here rather
    than in SQL keeps the database service unaware of which model is
    current - that is the backend's business.
    """
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
    """
    Answer one free-text question a staff member typed about the reviews.

    The question is grounded in exactly the same measured summary the full
    analysis uses, so an answer here cannot contradict the tables on the
    same screen.
    """
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

    # The full metrics block is large and the caller only needs the answer,
    # so it is dropped here rather than shipped to the browser.
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
