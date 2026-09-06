import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
from flask import (
    Flask,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8100").rstrip("/")
SHARED_DIR = os.path.abspath(
    os.environ.get("SHARED_DIR", os.path.join(BASE_DIR, "..", "..", "shared"))
)

SHARED_HOME_URL = os.environ.get("SHARED_HOME_URL")
SHARED_PORT = os.environ.get("SHARED_PORT", "5100")

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")

CAFE_TZ = ZoneInfo(os.environ.get("CAFE_TIMEZONE", "Australia/Sydney"))

HTTP_TIMEOUT = float(os.environ.get("HTTP_TIMEOUT", 6))
AI_HTTP_TIMEOUT = float(os.environ.get("AI_HTTP_TIMEOUT", 240))

STATUS_LABELS = {
    "SUBMITTED": "New",
    "ACKNOWLEDGED": "Acknowledged",
    "IN_REVIEW": "Being looked at",
    "RESOLVED": "Resolved",
    "ARCHIVED": "Archived",
}

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY", "temporary-secret-key")


class BackendError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def call_backend(method, path, timeout=None, **kwargs):
    """Single place this service talks to student-1-backend; forwards the signed session cookie."""
    kwargs.setdefault("cookies", request.cookies)

    try:
        response = requests.request(
            method, BACKEND_URL + path, timeout=timeout or HTTP_TIMEOUT, **kwargs
        )
    except requests.RequestException:
        raise BackendError(
            "The feedback service (student-1-backend) is not responding. "
            "Check that the container is running on %s." % BACKEND_URL
        )

    try:
        data = response.json()
    except ValueError:
        raise BackendError("The feedback service returned an unreadable response.")

    if response.status_code >= 400:
        raise BackendError(data.get("error") or "Request failed.")

    return data


@app.context_processor
def inject_shared():
    """Make the shared dashboard links, built from the incoming request host, available to every template."""
    if SHARED_HOME_URL:
        base = SHARED_HOME_URL.rstrip("/")
    else:
        base = "%s://%s:%s" % (
            request.scheme, request.host.split(":")[0], SHARED_PORT
        )

    return {
        "shared_base": base,
        "customer_home": base + "/customer-dashboard",
        "staff_home": base + "/staff-dashboard",
        "customer_login": base + "/shared/auth/customer_login.html",
        "staff_login": base + "/shared/auth/staff_login.html",
        "status_labels": STATUS_LABELS,
        "ollama_model": OLLAMA_MODEL,
    }


def trigger(html, *events):
    """Return an HTMX partial that also fires client-side events."""
    response = make_response(html)
    if events:
        response.headers["HX-Trigger"] = ", ".join(events)
    return response


@app.template_filter("cafe_time")
def cafe_time(value):
    """Render a UTC timestamp in the cafe's local time (Australia/Sydney)."""
    if not value:
        return ""

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            stamp = datetime.strptime(str(value)[:19], fmt)
            break
        except ValueError:
            continue
    else:
        return value

    local = stamp.replace(tzinfo=timezone.utc).astimezone(CAFE_TZ)

    return "%d %s %d, %d:%02d %s" % (
        local.day,
        local.strftime("%b"),
        local.year,
        local.hour % 12 or 12,
        local.minute,
        "am" if local.hour < 12 else "pm",
    )


def current_customer():
    """The signed-in customer, or None. Read from the shared session only."""
    if "customer_id" not in session:
        return None
    return {
        "id": session["customer_id"],
        "name": session.get("customer_name") or "Customer",
        "email": session.get("customer_email"),
    }


def current_staff():
    """The signed-in staff member, or None. Read from the shared session only."""
    if "staff_id" not in session:
        return None
    return {
        "id": session["staff_id"],
        "name": session.get("staff_name") or "Staff",
        "role": session.get("staff_role") or "staff",
    }


@app.get("/shared/<path:filename>")
def shared_assets(filename):
    """Serve the group stylesheet and icons read-only, straight from ./shared."""
    return send_from_directory(SHARED_DIR, filename)


@app.get("/health")
def health():
    try:
        backend = call_backend("GET", "/api/health")
        status = backend.get("status", "unknown")
    except BackendError as exc:
        backend = {"error": exc.message}
        status = "degraded"

    return {
        "service": "student-1-frontend",
        "feature": "Customer Feedback & Reviews",
        "owner": "Student 1 - Hangyeol Yi",
        "status": status,
        "backend": backend,
    }, 200 if status == "healthy" else 503


@app.get("/")
def index():
    return redirect("/review")


def my_reviews(customer):
    try:
        return call_backend(
            "GET", "/api/feedback",
            params={"customer_id": customer["id"], "limit": 50},
        )["feedback"]
    except BackendError:
        return []


@app.get("/review")
def review_page():
    customer = current_customer()

    if customer is None:
        return render_template("signin_required.html",
                               audience="customer", active="review")

    return render_template(
        "review.html",
        active="review",
        customer=customer,
        reviews=my_reviews(customer),
    )


@app.post("/review")
def submit_review():
    """HTMX: create a review, then re-render the customer's own list."""
    customer = current_customer()
    if customer is None:
        return render_template("partials/message.html", tone="error",
                               message="Your session has expired. "
                                       "Please sign in again."), 401

    try:
        call_backend("POST", "/api/feedback", json={
            "customer_id": customer["id"],
            "customer_name": customer["name"],
            "rating": request.form.get("rating"),
            "title": request.form.get("title"),
            "comment": request.form.get("comment"),
        })
    except BackendError as exc:
        return render_template("partials/my_reviews.html",
                               customer=customer,
                               reviews=my_reviews(customer),
                               error=exc.message)

    return trigger(
        render_template("partials/my_reviews.html",
                        customer=customer,
                        reviews=my_reviews(customer),
                        notice="Thank you - your review has been posted."),
        "review-saved",
    )


@app.get("/review/<int:feedback_id>/edit")
def edit_form(feedback_id):
    """HTMX: swap one review card for an inline edit form."""
    customer = current_customer()
    if customer is None:
        return render_template("partials/message.html", tone="error",
                               message="Please sign in again."), 401

    review = call_backend("GET", "/api/feedback/%d" % feedback_id)

    if int(review["customer_id"]) != int(customer["id"]):
        return render_template("partials/message.html", tone="error",
                               message="That review belongs to "
                                       "another customer."), 403

    return render_template("partials/review_edit.html", review=review)


@app.get("/review/<int:feedback_id>/confirm-delete")
def confirm_delete(feedback_id):
    """HTMX: swap one review card for a delete confirmation."""
    customer = current_customer()
    if customer is None:
        return render_template("partials/message.html", tone="error",
                               message="Please sign in again."), 401

    review = call_backend("GET", "/api/feedback/%d" % feedback_id)

    if int(review["customer_id"]) != int(customer["id"]):
        return render_template("partials/message.html", tone="error",
                               message="That review belongs to "
                                       "another customer."), 403

    return render_template("partials/review_delete_confirm.html", review=review)


@app.get("/review/<int:feedback_id>/card")
def review_card(feedback_id):
    """HTMX: cancel an edit or a delete and swap the form back for the card."""
    customer = current_customer()
    if customer is None:
        return render_template("partials/message.html", tone="error",
                               message="Please sign in again."), 401

    review = call_backend("GET", "/api/feedback/%d" % feedback_id)

    if int(review["customer_id"]) != int(customer["id"]):
        return render_template("partials/message.html", tone="error",
                               message="That review belongs to "
                                       "another customer."), 403

    return render_template("partials/review_card.html",
                           review=review, customer=customer)


@app.post("/review/<int:feedback_id>/update")
def update_review(feedback_id):
    customer = current_customer()
    if customer is None:
        return render_template("partials/message.html", tone="error",
                               message="Please sign in again."), 401

    try:
        call_backend("PUT", "/api/feedback/%d" % feedback_id, json={
            "customer_id": customer["id"],
            "rating": request.form.get("rating"),
            "title": request.form.get("title"),
            "comment": request.form.get("comment"),
        })
        notice = "Your review has been updated."
        error = None
    except BackendError as exc:
        notice, error = None, exc.message

    return render_template("partials/my_reviews.html",
                           customer=customer,
                           reviews=my_reviews(customer),
                           notice=notice, error=error)


@app.post("/review/<int:feedback_id>/delete")
def delete_review(feedback_id):
    customer = current_customer()
    if customer is None:
        return render_template("partials/message.html", tone="error",
                               message="Please sign in again."), 401

    try:
        call_backend("DELETE", "/api/feedback/%d" % feedback_id,
                     json={"customer_id": customer["id"]})
        notice, error = "Your review has been deleted.", None
    except BackendError as exc:
        notice, error = None, exc.message

    return render_template("partials/my_reviews.html",
                           customer=customer,
                           reviews=my_reviews(customer),
                           notice=notice, error=error)


SORT_ORDERS = ["newest", "oldest", "lowest", "highest"]


def staff_filters():
    sort = request.values.get("sort") or "newest"

    return {
        "search": (request.values.get("search") or "").strip()[:100],
        "date_from": (request.values.get("date_from") or "").strip(),
        "date_to": (request.values.get("date_to") or "").strip(),
        "sort": sort if sort in SORT_ORDERS else "newest",
    }


def local_date_to_utc(value, end_of_day=False):
    """Turn a date picked in the cafe's timezone into the UTC datetime the database stores."""
    try:
        day = datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError):
        return None

    if end_of_day:
        local = day.replace(hour=23, minute=59, second=59, tzinfo=CAFE_TZ)
    else:
        local = day.replace(hour=0, minute=0, second=0, tzinfo=CAFE_TZ)

    return local.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def staff_reviews(filters):
    params = {"limit": 200, "sort": filters["sort"]}

    if filters["search"]:
        params["search"] = filters["search"]

    start = local_date_to_utc(filters["date_from"])
    if start:
        params["submitted_from"] = start

    end = local_date_to_utc(filters["date_to"], end_of_day=True)
    if end:
        params["submitted_to"] = end

    return call_backend("GET", "/api/feedback", params=params)["feedback"]


@app.get("/reviews")
def staff_page():
    staff = current_staff()

    if staff is None:
        return render_template("signin_required.html",
                               audience="staff", active="reviews")

    filters = staff_filters()

    try:
        summary = call_backend("GET", "/api/summary")
        reviews = staff_reviews(filters)
        error = None
    except BackendError as exc:
        summary, reviews, error = {}, [], exc.message

    return render_template(
        "reviews.html",
        active="reviews",
        staff=staff,
        summary=summary,
        reviews=reviews,
        filters=filters,
        error=error,
    )


@app.get("/reviews/list")
def staff_list():
    """HTMX: re-render just the review table when a filter changes."""
    filters = staff_filters()

    try:
        return render_template("partials/staff_reviews.html",
                               reviews=staff_reviews(filters),
                               filters=filters)
    except BackendError as exc:
        return render_template("partials/staff_reviews.html",
                               reviews=[], filters=filters, error=exc.message)


@app.post("/reviews/<int:feedback_id>/response")
def staff_respond(feedback_id):
    staff = current_staff()
    if staff is None:
        return render_template("partials/message.html", tone="error",
                               message="Please sign in again."), 401

    filters = staff_filters()
    error = None

    try:
        call_backend("POST", "/api/feedback/%d/response" % feedback_id, json={
            "staff_response": request.form.get("staff_response"),
            "actor": "staff:%s" % staff["id"],
        })
    except BackendError as exc:
        error = exc.message

    return trigger(
        render_template("partials/staff_reviews.html",
                        reviews=staff_reviews(filters),
                        filters=filters, error=error),
        "reviews-changed",
    )


@app.post("/reviews/ai/ask")
def staff_ask():
    """HTMX: answer one free-text question a staff member typed."""
    if current_staff() is None:
        return render_template("partials/message.html", tone="error",
                               message="Please sign in again."), 401

    question = (request.form.get("question") or "").strip()

    if not question:
        return render_template("partials/ai_answer.html",
                               error="Type a question first.")

    try:
        result = call_backend("POST", "/api/ai/ask",
                              json={"question": question},
                              timeout=AI_HTTP_TIMEOUT)
    except BackendError as exc:
        return render_template("partials/ai_answer.html", error=exc.message)

    return render_template("partials/ai_answer.html", result=result)


@app.post("/reviews/ai/analyse-pending")
def staff_analyse_pending():
    """HTMX: run AI-Mode over the reviews that have never been analysed."""
    if current_staff() is None:
        return render_template("partials/message.html", tone="error",
                               message="Please sign in again."), 401

    try:
        result = call_backend("POST", "/api/ai/analyse-pending",
                              timeout=AI_HTTP_TIMEOUT)
    except BackendError as exc:
        return render_template("partials/ai_batch.html", error=exc.message)

    return trigger(
        render_template("partials/ai_batch.html", result=result),
        "reviews-changed",
    )


@app.errorhandler(BackendError)
def handle_backend_error(exc):
    return render_template("partials/message.html", tone="error",
                           message=exc.message), 502


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5110)),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
