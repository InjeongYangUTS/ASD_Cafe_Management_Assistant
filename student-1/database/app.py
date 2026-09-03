"""
Student 1 (Hangyeol Yi) - Customer Feedback & Reviews
DATABASE MICROSERVICE  (container: student-1-database, port 7100)

This service is the ONLY process that opens feedback.db. Every other
microservice - including my own backend/API - reads and writes this data
exclusively through the /db/* HTTP endpoints below. That is the
Cross-Feature Database API Integration rule for Release 0.

Writes to customer_feedback always append a matching store_logs row in
the SAME transaction. Putting that here rather than in the backend means
the audit trail cannot be bypassed by whichever service called us.

Endpoints
    GET    /db/health
    GET    /db/stats

    GET    /db/feedback              ?customer_id= &status= &sentiment=
                                     &category= &min_rating= &max_rating=
                                     &analysed= &days= &needs_reply=
                                     &submitted_from= &submitted_to=
                                     &search= &sort= &limit= &offset=
    POST   /db/feedback
    GET    /db/feedback/<id>
    PUT    /db/feedback/<id>
    DELETE /db/feedback/<id>
    PUT    /db/feedback/<id>/analysis
    GET    /db/feedback/<id>/logs

    GET    /db/logs                  ?feedback_id= &action= &limit=
"""

import json
import os
import re
import sqlite3

from flask import Flask, jsonify, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("FEEDBACK_DB_PATH", os.path.join(BASE_DIR, "feedback.db"))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

VALID_STATUSES = ["SUBMITTED", "ACKNOWLEDGED", "IN_REVIEW", "RESOLVED", "ARCHIVED"]
VALID_CATEGORIES = ["FOOD", "DRINK", "SERVICE", "CLEANLINESS",
                    "WAIT_TIME", "PRICE", "GENERAL"]
VALID_SENTIMENTS = ["POSITIVE", "NEUTRAL", "NEGATIVE"]
VALID_ACTIONS = ["CREATED", "UPDATED", "DELETED", "ANALYSED",
                 "STATUS_CHANGED", "RESPONDED"]
VALID_ACTOR_ROLES = ["CUSTOMER", "STAFF", "SYSTEM", "AI"]

# Sort orders the staff board offers. Whitelisted rather than accepting a
# column name from the caller: this string is interpolated into SQL, and
# an ORDER BY is one of the few places a parameter marker cannot go.
SORT_ORDERS = {
    "newest":  "submitted_at DESC, id DESC",
    "oldest":  "submitted_at ASC, id ASC",
    "lowest":  "rating ASC, submitted_at DESC",
    "highest": "rating DESC, submitted_at DESC",
}

# Fields a client is allowed to change through PUT /db/feedback/<id>.
# The AI columns are deliberately NOT here - they only move through
# PUT /db/feedback/<id>/analysis, so a customer edit can never forge a
# sentiment score.
EDITABLE_FIELDS = ["rating", "title", "comment", "category",
                   "status", "staff_response", "order_id", "order_number"]

app = Flask(__name__)


# =====================================================================
# Connection helpers
# =====================================================================

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_schema():
    """Create the tables on first boot so the container never starts empty."""
    conn = get_conn()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
        conn.executescript(schema_file.read())
    conn.commit()
    conn.close()


def error(message, status_code=400, **extra):
    payload = {"error": message}
    payload.update(extra)
    return jsonify(payload), status_code


def row_to_feedback(row):
    """
    Turn a sqlite Row into the JSON shape callers expect.

    ai_issues is stored as a JSON string (SQLite has no array type) and is
    handed back as a real list, so the backend and the templates never have
    to parse it themselves.
    """
    if row is None:
        return None

    item = dict(row)
    raw_issues = item.get("ai_issues")

    if raw_issues:
        try:
            parsed = json.loads(raw_issues)
            item["ai_issues"] = parsed if isinstance(parsed, list) else [str(parsed)]
        except (TypeError, ValueError):
            item["ai_issues"] = [raw_issues]
    else:
        item["ai_issues"] = []

    return item


def write_log(conn, feedback_id, action, actor="system",
              actor_role="SYSTEM", detail=None):
    """Append one store_logs row. Runs inside the caller's transaction."""
    if action not in VALID_ACTIONS:
        action = "UPDATED"
    if actor_role not in VALID_ACTOR_ROLES:
        actor_role = "SYSTEM"

    conn.execute(
        "INSERT INTO store_logs (feedback_id, entity, action, actor, "
        "actor_role, detail) VALUES (?, 'customer_feedback', ?, ?, ?, ?)",
        (feedback_id, action, str(actor), actor_role, detail),
    )


def fetch_feedback(conn, feedback_id):
    row = conn.execute(
        "SELECT * FROM customer_feedback WHERE id = ?", (feedback_id,)
    ).fetchone()
    return row_to_feedback(row)


def parse_int(value, field, minimum=None, maximum=None):
    """Return (number, error_message) - error_message is None when valid."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None, "%s must be a whole number" % field

    if minimum is not None and number < minimum:
        return None, "%s must be %d or more" % (field, minimum)
    if maximum is not None and number > maximum:
        return None, "%s must be %d or less" % (field, maximum)

    return number, None


# =====================================================================
# Health / stats
# =====================================================================

@app.get("/db/health")
def health():
    try:
        conn = get_conn()
        conn.execute("SELECT 1 FROM customer_feedback LIMIT 1").fetchone()
        conn.close()
        return jsonify({
            "service": "student-1-database",
            "status": "healthy",
            "database": os.path.basename(DB_PATH),
            "tables": ["customer_feedback", "store_logs"],
        })
    except sqlite3.Error as exc:
        return jsonify({
            "service": "student-1-database",
            "status": "unhealthy",
            "detail": str(exc),
        }), 503


@app.get("/db/stats")
def stats():
    """
    Aggregates used by the staff screen and, more importantly, as the
    factual context handed to the LLM in AI-Mode. Computing them in SQL
    keeps the prompt small: we send counts, not hundreds of raw reviews.
    """
    conn = get_conn()

    def group_count(column):
        return {
            row[column]: row["c"]
            for row in conn.execute(
                "SELECT %s, COUNT(*) AS c FROM customer_feedback "
                "WHERE %s IS NOT NULL GROUP BY %s" % (column, column, column)
            ).fetchall()
        }

    totals = conn.execute(
        """
        SELECT COUNT(*)                              AS feedback,
               (SELECT COUNT(*) FROM store_logs)     AS store_logs,
               COALESCE(ROUND(AVG(rating), 2), 0)    AS average_rating,
               COALESCE(SUM(CASE WHEN analysed_at IS NULL THEN 1 ELSE 0 END), 0)
                                                     AS unanalysed
        FROM customer_feedback
        """
    ).fetchone()

    rating_distribution = {
        str(row["rating"]): row["c"]
        for row in conn.execute(
            "SELECT rating, COUNT(*) AS c FROM customer_feedback GROUP BY rating"
        ).fetchall()
    }

    # Every read has to finish before the connection closes.
    by_status = group_count("status")
    by_category = group_count("category")
    by_sentiment = group_count("sentiment")

    conn.close()

    return jsonify({
        "service": "student-1-database",
        "row_counts": {
            "customer_feedback": totals["feedback"],
            "store_logs": totals["store_logs"],
        },
        "average_rating": totals["average_rating"],
        "unanalysed_count": totals["unanalysed"],
        "rating_distribution": {str(n): rating_distribution.get(str(n), 0)
                                for n in range(1, 6)},
        "by_status": by_status,
        "by_category": by_category,
        "by_sentiment": by_sentiment,
    })


# =====================================================================
# customer_feedback : CRUD
# =====================================================================

@app.get("/db/feedback")
def list_feedback():
    sql = "SELECT * FROM customer_feedback WHERE 1 = 1"
    params = []

    if request.args.get("customer_id"):
        customer_id, message = parse_int(
            request.args["customer_id"], "customer_id", minimum=1
        )
        if message:
            return error(message)
        sql += " AND customer_id = ?"
        params.append(customer_id)

    for field, allowed in (("status", VALID_STATUSES),
                           ("category", VALID_CATEGORIES),
                           ("sentiment", VALID_SENTIMENTS)):
        raw = request.args.get(field)
        if not raw:
            continue

        wanted = [value.strip().upper() for value in raw.split(",") if value.strip()]
        invalid = [value for value in wanted if value not in allowed]
        if invalid:
            return error("unknown %s: %s" % (field, ", ".join(invalid)))

        sql += " AND %s IN (%s)" % (field, ",".join("?" * len(wanted)))
        params.extend(wanted)

    for arg, comparison in (("min_rating", ">="), ("max_rating", "<=")):
        if request.args.get(arg):
            rating, message = parse_int(request.args[arg], arg, 1, 5)
            if message:
                return error(message)
            sql += " AND rating %s ?" % comparison
            params.append(rating)

    analysed = request.args.get("analysed")
    if analysed:
        if str(analysed).lower() in ("1", "true", "yes"):
            sql += " AND analysed_at IS NOT NULL"
        else:
            sql += " AND analysed_at IS NULL"

    # "Reviews from the last N days". Computed in SQLite against the same
    # datetime('now') the rows were stamped with, so the window cannot
    # drift with the caller's clock or timezone.
    if request.args.get("days"):
        days, message = parse_int(request.args["days"], "days", 1, 3650)
        if message:
            return error(message)
        sql += " AND submitted_at >= datetime('now', ?)"
        params.append("-%d days" % days)

    # Explicit window. The caller supplies UTC datetimes, because that is
    # what the rows are stamped with - converting a user's local date into
    # this range is the frontend's job, since only it knows the cafe's
    # timezone.
    for arg, comparison in (("submitted_from", ">="), ("submitted_to", "<=")):
        value = request.args.get(arg)
        if not value:
            continue
        if not re.match(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2}:\d{2})?$", value):
            return error("%s must be YYYY-MM-DD or YYYY-MM-DD HH:MM:SS" % arg)
        sql += " AND submitted_at %s ?" % comparison
        params.append(value)

    # Free-text search over what the customer actually wrote, plus their
    # name so staff can find "that review from Priya".
    search = (request.args.get("search") or "").strip()
    if search:
        if len(search) > 100:
            return error("search must be 100 characters or fewer")

        # LIKE treats % and _ as wildcards, so searching for "50%" would
        # otherwise match every review. The backslash is escaped first,
        # then the two wildcards, and ESCAPE tells SQLite to read them
        # literally.
        pattern = "%" + (search.replace("\\", "\\\\")
                               .replace("%", "\\%")
                               .replace("_", "\\_")) + "%"
        sql += (" AND (title LIKE ? ESCAPE '\\' "
                "OR comment LIKE ? ESCAPE '\\' "
                "OR customer_name LIKE ? ESCAPE '\\')")
        params.extend([pattern, pattern, pattern])

    # Reviews nobody has answered yet.
    if request.args.get("needs_reply"):
        if str(request.args["needs_reply"]).lower() in ("1", "true", "yes"):
            sql += " AND (staff_response IS NULL OR TRIM(staff_response) = '')"
        else:
            sql += " AND staff_response IS NOT NULL AND TRIM(staff_response) != ''"

    limit, message = parse_int(request.args.get("limit", 100), "limit", 1)
    if message:
        return error(message)

    offset, message = parse_int(request.args.get("offset", 0), "offset", 0)
    if message:
        return error(message)

    sort = str(request.args.get("sort") or "newest").lower()
    if sort not in SORT_ORDERS:
        return error("sort must be one of %s" % list(SORT_ORDERS))

    sql += " ORDER BY %s LIMIT ? OFFSET ?" % SORT_ORDERS[sort]
    params.extend([min(limit, 500), offset])

    conn = get_conn()
    rows = [row_to_feedback(row) for row in conn.execute(sql, params).fetchall()]
    conn.close()

    return jsonify({"count": len(rows), "feedback": rows})


@app.post("/db/feedback")
def create_feedback():
    body = request.get_json(silent=True) or {}

    customer_id, message = parse_int(body.get("customer_id"), "customer_id", 1)
    if message:
        return error(message)

    rating, message = parse_int(body.get("rating"), "rating", 1, 5)
    if message:
        return error(message)

    comment = str(body.get("comment") or "").strip()
    if not comment:
        return error("comment cannot be empty")
    if len(comment) > 2000:
        return error("comment must be 2000 characters or fewer")

    category = str(body.get("category") or "GENERAL").upper()
    if category not in VALID_CATEGORIES:
        return error("category must be one of %s" % VALID_CATEGORIES)

    order_id = None
    if body.get("order_id") not in (None, ""):
        order_id, message = parse_int(body.get("order_id"), "order_id", 1)
        if message:
            return error(message)

    conn = get_conn()
    cursor = conn.execute(
        """
        INSERT INTO customer_feedback
            (customer_id, customer_name, order_id, order_number,
             rating, title, comment, category, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'SUBMITTED')
        """,
        (
            customer_id, body.get("customer_name"), order_id,
            body.get("order_number"), rating, body.get("title"),
            comment, category,
        ),
    )
    feedback_id = cursor.lastrowid

    write_log(
        conn, feedback_id, "CREATED",
        actor=body.get("actor") or ("customer:%d" % customer_id),
        actor_role="CUSTOMER",
        detail="rating %d, category %s" % (rating, category),
    )
    conn.commit()

    created = fetch_feedback(conn, feedback_id)
    conn.close()

    return jsonify(created), 201


@app.get("/db/feedback/<int:feedback_id>")
def get_feedback(feedback_id):
    conn = get_conn()
    item = fetch_feedback(conn, feedback_id)
    conn.close()

    if item is None:
        return error("feedback %d not found" % feedback_id, 404)

    return jsonify(item)


@app.put("/db/feedback/<int:feedback_id>")
def update_feedback(feedback_id):
    body = request.get_json(silent=True) or {}
    updates = {field: body[field] for field in EDITABLE_FIELDS if field in body}

    if not updates:
        return error("nothing to update")

    if "rating" in updates:
        updates["rating"], message = parse_int(updates["rating"], "rating", 1, 5)
        if message:
            return error(message)

    if "comment" in updates:
        comment = str(updates["comment"] or "").strip()
        if not comment:
            return error("comment cannot be empty")
        if len(comment) > 2000:
            return error("comment must be 2000 characters or fewer")
        updates["comment"] = comment

    if "category" in updates:
        updates["category"] = str(updates["category"]).upper()
        if updates["category"] not in VALID_CATEGORIES:
            return error("category must be one of %s" % VALID_CATEGORIES)

    if "status" in updates:
        updates["status"] = str(updates["status"]).upper()
        if updates["status"] not in VALID_STATUSES:
            return error("status must be one of %s" % VALID_STATUSES)

    conn = get_conn()
    existing = fetch_feedback(conn, feedback_id)

    if existing is None:
        conn.close()
        return error("feedback %d not found" % feedback_id, 404)

    conn.execute(
        "UPDATE customer_feedback SET %s WHERE id = ?" %
        ", ".join("%s = ?" % column for column in updates),
        list(updates.values()) + [feedback_id],
    )

    # A status move and a content edit are different events to anyone
    # reading the audit trail, so they are logged as different actions.
    if "status" in updates and updates["status"] != existing["status"]:
        write_log(
            conn, feedback_id, "STATUS_CHANGED",
            actor=body.get("actor", "staff"),
            actor_role=body.get("actor_role", "STAFF"),
            detail="%s -> %s" % (existing["status"], updates["status"]),
        )

    if "staff_response" in updates:
        write_log(
            conn, feedback_id, "RESPONDED",
            actor=body.get("actor", "staff"),
            actor_role=body.get("actor_role", "STAFF"),
            detail="staff response recorded",
        )

    content_fields = [field for field in updates
                      if field not in ("status", "staff_response")]
    if content_fields:
        write_log(
            conn, feedback_id, "UPDATED",
            actor=body.get("actor") or ("customer:%s" % existing["customer_id"]),
            actor_role=body.get("actor_role", "CUSTOMER"),
            detail="changed: %s" % ", ".join(sorted(content_fields)),
        )

    conn.commit()
    updated = fetch_feedback(conn, feedback_id)
    conn.close()

    return jsonify(updated)


@app.delete("/db/feedback/<int:feedback_id>")
def delete_feedback(feedback_id):
    body = request.get_json(silent=True) or {}

    conn = get_conn()
    existing = fetch_feedback(conn, feedback_id)

    if existing is None:
        conn.close()
        return error("feedback %d not found" % feedback_id, 404)

    conn.execute("DELETE FROM customer_feedback WHERE id = ?", (feedback_id,))

    # store_logs has no FK cascade on purpose, so this row survives the
    # delete and the audit trail stays complete.
    write_log(
        conn, feedback_id, "DELETED",
        actor=body.get("actor") or ("customer:%s" % existing["customer_id"]),
        actor_role=body.get("actor_role", "CUSTOMER"),
        detail="deleted review by %s (rating %s)"
               % (existing.get("customer_name") or "customer", existing["rating"]),
    )
    conn.commit()
    conn.close()

    return jsonify({"deleted": True, "id": feedback_id})


@app.put("/db/feedback/<int:feedback_id>/analysis")
def save_analysis(feedback_id):
    """
    Write back one AI-Mode result. Kept separate from the general PUT so
    the AI columns have exactly one entry point and every write is logged
    as an ANALYSED event by the AI actor.
    """
    body = request.get_json(silent=True) or {}

    sentiment = str(body.get("sentiment") or "").upper()
    if sentiment not in VALID_SENTIMENTS:
        return error("sentiment must be one of %s" % VALID_SENTIMENTS)

    try:
        score = float(body.get("sentiment_score", 0.0))
    except (TypeError, ValueError):
        return error("sentiment_score must be a number between -1 and 1")

    if not -1.0 <= score <= 1.0:
        return error("sentiment_score must be between -1 and 1")

    issues = body.get("ai_issues") or []
    if not isinstance(issues, list):
        issues = [str(issues)]

    conn = get_conn()
    if fetch_feedback(conn, feedback_id) is None:
        conn.close()
        return error("feedback %d not found" % feedback_id, 404)

    conn.execute(
        """
        UPDATE customer_feedback
        SET sentiment = ?, sentiment_score = ?, ai_summary = ?,
            ai_issues = ?, ai_model = ?, analysed_at = datetime('now')
        WHERE id = ?
        """,
        (
            sentiment, round(score, 3), body.get("ai_summary"),
            json.dumps([str(issue) for issue in issues]),
            body.get("ai_model") or "unknown", feedback_id,
        ),
    )

    write_log(
        conn, feedback_id, "ANALYSED", actor="ai", actor_role="AI",
        detail="%s (%.2f) via %s"
               % (sentiment, score, body.get("ai_model") or "unknown"),
    )
    conn.commit()

    updated = fetch_feedback(conn, feedback_id)
    conn.close()

    return jsonify(updated)


@app.get("/db/feedback/<int:feedback_id>/logs")
def feedback_logs(feedback_id):
    conn = get_conn()
    rows = [dict(row) for row in conn.execute(
        "SELECT * FROM store_logs WHERE feedback_id = ? "
        "ORDER BY created_at DESC, id DESC", (feedback_id,)
    ).fetchall()]
    conn.close()

    return jsonify({"feedback_id": feedback_id, "count": len(rows), "logs": rows})


# =====================================================================
# store_logs : CRUD
# =====================================================================

@app.get("/db/logs")
def list_logs():
    sql = "SELECT * FROM store_logs WHERE 1 = 1"
    params = []

    if request.args.get("feedback_id"):
        feedback_id, message = parse_int(
            request.args["feedback_id"], "feedback_id", 1
        )
        if message:
            return error(message)
        sql += " AND feedback_id = ?"
        params.append(feedback_id)

    if request.args.get("action"):
        wanted = [action.strip().upper()
                  for action in request.args["action"].split(",") if action.strip()]
        invalid = [action for action in wanted if action not in VALID_ACTIONS]
        if invalid:
            return error("unknown action: %s" % ", ".join(invalid))
        sql += " AND action IN (%s)" % ",".join("?" * len(wanted))
        params.extend(wanted)

    limit, message = parse_int(request.args.get("limit", 100), "limit", 1)
    if message:
        return error(message)

    sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(min(limit, 500))

    conn = get_conn()
    rows = [dict(row) for row in conn.execute(sql, params).fetchall()]
    conn.close()

    return jsonify({"count": len(rows), "logs": rows})


@app.errorhandler(404)
def not_found(_):
    return error("endpoint not found", 404)


ensure_schema()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 7100)),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
