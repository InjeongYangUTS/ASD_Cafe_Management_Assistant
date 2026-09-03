"""
Student 1 (Hangyeol Yi) - Customer Feedback & Reviews
FRONTEND MICROSERVICE  (container: student-1-frontend, port 5110)

Two screens, one per audience:

    /review    Customer - leave a star rating and a comment at the top,
               manage your previous reviews (edit / delete) underneath.
    /reviews   Staff    - ask the AI a question at the top, then every
               customer review from the database.

Rendered server-side with Jinja and driven by HTMX, so the browser only
ever talks to this service. Every piece of data comes from my backend/API
microservice over HTTP - this container holds no database of its own.

It also serves the shared team assets (/shared/...) read-only, so the
group stylesheet is reused rather than copied.

SIGN-IN
    The shared entry point (port 5100) signs the user in and stores the
    identity in a Flask session cookie. Cookies are scoped to the host,
    not the port, so this service reads that same cookie by using the
    same SECRET_KEY. No second login, and no identity is ever taken from
    the URL or a form field - a customer cannot edit someone else's
    review by changing a number in the address bar.
"""

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

# Link back to the shared entry point. Resolved per request from the host
# the BROWSER used - see inject_shared() - so the links work from any
# device. Set SHARED_HOME_URL only to override that with a fixed address.
SHARED_HOME_URL = os.environ.get("SHARED_HOME_URL")
SHARED_PORT = os.environ.get("SHARED_PORT", "5100")

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")

# The cafe's own timezone. Timestamps are stored in UTC and shown in this
# zone, so a time on screen means what it meant to the customer standing
# at the counter. Overridable for a cafe somewhere else.
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

# Must match shared/frontend/app.py so the signed session cookie set at
# login can be read here. Override in both places for a real deployment.
app.secret_key = os.environ.get("SECRET_KEY", "temporary-secret-key")


# =====================================================================
# Backend helper
# =====================================================================

class BackendError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def call_backend(method, path, timeout=None, **kwargs):
    """
    Single place where this service talks to student-1-backend.

    The browser's signed session cookie is forwarded with every call. The
    backend verifies it with the same SECRET_KEY and takes the customer's
    identity from there, so a caller cannot simply claim to be customer
    102 in a JSON body - a body field is a wish, a signed cookie is proof.
    """
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
    """
    Make the shared dashboard links available to every template.

    Built from the host in the incoming request, not from "localhost", so
    the links resolve wherever the page is opened from - the marker's
    laptop, a phone on the same Wi-Fi, or another machine on the network.
    """
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


# =====================================================================
# Time display
# =====================================================================

@app.template_filter("cafe_time")
def cafe_time(value):
    """
    Render a stored timestamp in the cafe's own local time.

    Timestamps are STORED in UTC - SQLite's datetime('now') - because that
    is the only clock that cannot drift between the three containers, and
    because a stored local time silently breaks twice a year when the
    clocks change.

    They are DISPLAYED in Australia/Sydney, because that is when the thing
    actually happened to the people reading it. Showing a review posted at
    8am as "22:00 the previous day" makes the morning-rush complaints
    impossible to find, which is exactly what staff come to this screen
    for. zoneinfo applies AEST or AEDT for the date in question, so the
    daylight-saving switch needs no code.
    """
    if not value:
        return ""

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            stamp = datetime.strptime(str(value)[:19], fmt)
            break
        except ValueError:
            continue
    else:
        # Unparseable: show it as stored rather than inventing a time.
        return value

    local = stamp.replace(tzinfo=timezone.utc).astimezone(CAFE_TZ)

    # %-d / %-I are not portable to Windows, so the leading zeros are
    # stripped by hand and the same output appears everywhere.
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


# =====================================================================
# Shared assets
# =====================================================================

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


# =====================================================================
# Customer screen : leave a review, manage your own reviews
# =====================================================================

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
    """
    HTMX: swap one review card for a delete confirmation.

    Asked in the page rather than through hx-confirm, which relies on the
    browser's confirm() dialog. Where that dialog is blocked, HTMX reads
    the block as "no" and cancels the request silently, so Delete appears
    to do nothing - the worst outcome for a destructive control.
    """
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
    """
    HTMX: cancel an edit or a delete - swap the form back for the card.

    This checks ownership like every other route that takes a review id.
    It is only ever reached by pressing Cancel, so the id "should" always
    be the customer's own - but a route that trusts that assumption is a
    route that returns any review to anyone who edits the URL, and the
    read is as much of a leak as the write would be.
    """
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


# =====================================================================
# Staff screen : every review + AI analysis
# =====================================================================

# The staff board offers a search box, a date range and a sort order.
#
# It used to filter by Status, Category, Sentiment and Rating. Status
# became meaningless once the status buttons went. Category is derived
# from the wording, so filtering by it asked staff to guess how the
# classifier had read a review. A search box answers more: staff arrive
# looking for a particular review, or for what people said about one thing.
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
    """
    Turn a date the user picked - in the cafe's timezone - into the UTC
    datetime the database stores.

    This conversion is the whole reason the filter works. Timestamps are
    stored in UTC; the date picker shows Sydney dates. Comparing a Sydney
    date against a UTC column directly loses the first ten hours of every
    day, so a review left at 8am would not appear when its own date was
    selected.
    """
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
    """
    HTMX: answer one free-text question a staff member typed.

        browser -> student-1-frontend -> student-1-backend
                -> Ollama -> LLM -> back again
    """
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
