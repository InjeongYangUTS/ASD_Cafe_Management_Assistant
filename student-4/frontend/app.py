"""
Student 4 (Stella Kwon) - Order & Kitchen Management
FRONTEND MICROSERVICE  (container: student-4-frontend, port 5400)

Three screens required by my feature allocation:

    /pos      POS order placement UI
    /kitchen  Kitchen display system
    /status   Order status interface

Rendered server-side with Jinja and driven by HTMX, so the browser only ever
talks to this service. Every piece of data comes from my backend/API
microservice over HTTP - this container holds no database of its own.

It also serves the shared team assets (/shared/...) read-only so the group
stylesheet is reused rather than copied.
"""

import os
from functools import wraps
from datetime import datetime

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

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8400").rstrip("/")
SHARED_DIR = os.path.abspath(
    os.environ.get("SHARED_DIR", os.path.join(BASE_DIR, "..", "..", "shared"))
)

# Link back to the shared entry point. Resolved per request from the host the
# BROWSER used - see inject_shared_home() below - so it works from any device.
SHARED_PORT = os.environ.get("SHARED_PORT", "5100")

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")

HTTP_TIMEOUT = float(os.environ.get("HTTP_TIMEOUT", 5))
AI_HTTP_TIMEOUT = float(os.environ.get("AI_HTTP_TIMEOUT", 60))

STATION_LABELS = {
    "BAR": "Coffee & drinks",
    "KITCHEN": "Kitchen",
    "PASTRY": "Bakery & cake",
}

ALL_STATUSES = ["PENDING", "CONFIRMED", "PREPARING", "READY",
                "COMPLETED", "CANCELLED"]

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "temporary-secret-key")


# =====================================================================
# Backend helper
# =====================================================================

class BackendError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def call_backend(method, path, timeout=None, **kwargs):
    """Single place where this service talks to student-4-backend."""
    try:
        response = requests.request(
            method,
            BACKEND_URL + path,
            timeout=timeout or HTTP_TIMEOUT,
            **kwargs
        )
    except requests.RequestException:
        raise BackendError(
            "The order service (student-4-backend) is not responding. "
            "Check that the container is running on %s." % BACKEND_URL
        )

    try:
        data = response.json()
    except ValueError:
        raise BackendError("The order service returned an unreadable response.")

    if response.status_code >= 400:
        raise BackendError(data.get("error") or "Request failed.")

    return data



# =====================================================================
# Roles
# =====================================================================
# Authentication belongs to the shared service on :5100. This feature only
# reads the session it issued, so a customer cannot open the staff screens.

STAFF_PATH = os.environ.get("STAFF_PATH", "/staff-dashboard")
CUSTOMER_PATH = os.environ.get("CUSTOMER_PATH", "/customer-dashboard")


def is_staff():
    return "staff_id" in session


def is_customer():
    return "customer_id" in session and "staff_id" not in session


def shared_link(path):
    """Absolute URL back to the shared app, on the host the browser used."""
    host = request.host.split(":")[0]
    return "%s://%s:%s%s" % (request.scheme, host, SHARED_PORT, path)


def staff_only(view):
    """Send a signed-in customer back to their own dashboard."""
    @wraps(view)
    def guarded(*args, **kwargs):
        if is_customer():
            return redirect(shared_link(CUSTOMER_PATH))
        return view(*args, **kwargs)
    return guarded


def staff_only_partial(view):
    """Same rule for the HTMX fragments the staff screens call."""
    @wraps(view)
    def guarded(*args, **kwargs):
        if is_customer():
            return ('<div class="s4-alert error"><strong>Staff only</strong>'
                    'This view is not available on a customer account.</div>'), 403
        return view(*args, **kwargs)
    return guarded


@app.context_processor
def inject_shared_home():
    """
    Give every template the right way home for whoever is signed in.

    The address is built from the host in the incoming request, not from
    "localhost", so the link resolves wherever the page is opened from - the
    marker's laptop, a phone on the same Wi-Fi, another machine on the
    network. A customer goes back to the customer dashboard, staff to the
    staff dashboard.
    """
    customer = is_customer()

    return {
        "shared_home": shared_link(CUSTOMER_PATH if customer else STAFF_PATH),
        "shared_home_label": ("Back to Customer Dashboard" if customer
                              else "Back to Staff Dashboard"),
        "is_customer": customer,
        "is_staff": is_staff(),
    }


def trigger(html, *events):
    """Return an HTMX partial that also fires client-side events."""
    response = make_response(html)
    if events:
        response.headers["HX-Trigger"] = ", ".join(events)
    return response


# =====================================================================
# Cart (kept in the browser session, not in the database)
# =====================================================================

def get_cart():
    return session.get("cart", {})


def save_cart(cart):
    session["cart"] = cart
    session.modified = True


def cart_context():
    """Resolve the session cart against the live menu for rendering."""
    cart = get_cart()

    if not cart:
        return {"lines": [], "total": 0.0, "item_count": 0, "prep_minutes": 0.0}

    try:
        catalog = {
            str(item["menu_id"]): item
            for item in call_backend("GET", "/api/menu")["items"]
        }
    except BackendError:
        catalog = {}

    lines = []
    total = 0.0
    item_count = 0
    prep_seconds = 0

    for menu_id, quantity in cart.items():
        item = catalog.get(str(menu_id))
        if item is None:
            continue

        line_total = item["price"] * quantity
        total += line_total
        item_count += quantity
        prep_seconds += item.get("prep_seconds", 90) * quantity

        lines.append({
            "menu_id": int(menu_id),
            "name": item["name"],
            "price": item["price"],
            "quantity": quantity,
            "line_total": line_total,
            "station": item.get("station", "BAR"),
        })

    lines.sort(key=lambda line: line["menu_id"])

    return {
        "lines": lines,
        "total": total,
        "item_count": item_count,
        "prep_minutes": prep_seconds / 60.0,
    }


# =====================================================================
# Shared assets (read-only reuse of the group theme)
# =====================================================================

@app.get("/shared/<path:filename>")
def shared_assets(filename):
    return send_from_directory(SHARED_DIR, filename)


@app.get("/health")
def health():
    try:
        call_backend("GET", "/api/health")
        backend_ok = True
    except BackendError:
        backend_ok = False

    return {
        "service": "student-4-frontend",
        "status": "healthy" if backend_ok else "degraded",
        "backend_url": BACKEND_URL,
    }, 200 if backend_ok else 503


# =====================================================================
# Pages
# =====================================================================

@app.get("/")
def home():
    return redirect("/pos")


@app.get("/pos")
def pos():
    try:
        menu = call_backend("GET", "/api/menu")
        menu_count, menu_source = menu["count"], menu["source"]
    except BackendError:
        menu_count, menu_source = 0, "unavailable"

    return render_template(
        "pos.html",
        active="pos",
        menu_count=menu_count,
        menu_source=menu_source,
        customer_name=session.get("customer_name", ""),
    )


@app.get("/kitchen")
@staff_only
def kitchen():
    return render_template(
        "kitchen.html",
        active="kitchen",
        ollama_model=OLLAMA_MODEL,
    )


@app.get("/status")
@staff_only
def status_page():
    return render_template(
        "status.html",
        active="status",
        statuses=ALL_STATUSES,
    )


# =====================================================================
# HTMX partials - service strip
# =====================================================================

@app.get("/ui/services")
def ui_services():
    services = []

    try:
        health_report = call_backend("GET", "/api/health")
        dependencies = health_report["dependencies"]

        services.append({"label": "Order API",
                         "up": True})
        services.append({"label": "Order DB",
                         "up": bool(dependencies["order_database"].get("reachable"))})
        services.append({"label": "Menu API (S2)",
                         "up": bool(dependencies["menu_service_student_2"].get("reachable"))})
        services.append({"label": "Inventory API (S3)",
                         "up": bool(dependencies["inventory_service_student_3"].get("reachable"))})
        services.append({"label": "Ollama",
                         "up": bool(dependencies["ollama"].get("reachable"))})

    except BackendError:
        services = [
            {"label": "Order API", "up": False},
            {"label": "Order DB", "up": False},
            {"label": "Menu API (S2)", "up": False},
            {"label": "Inventory API (S3)", "up": False},
            {"label": "Ollama", "up": False},
        ]

    return render_template("partials/services.html", services=services)


# =====================================================================
# HTMX partials - POS
# =====================================================================

@app.get("/ui/menu")
def ui_menu():
    try:
        menu = call_backend("GET", "/api/menu")
    except BackendError as exc:
        return render_template("partials/menu.html", error=exc.message)

    grouped = {}
    for station in ("BAR", "KITCHEN", "PASTRY"):
        items = [i for i in menu["items"] if i.get("station", "BAR") == station]
        if items:
            grouped[station] = items

    return render_template(
        "partials/menu.html",
        grouped=grouped,
        station_labels=STATION_LABELS,
    )


@app.get("/ui/cart")
def ui_cart():
    return render_template("partials/cart.html", **cart_context())


@app.post("/ui/cart/add")
def ui_cart_add():
    menu_id = request.values.get("menu_id")

    if menu_id:
        cart = get_cart()
        cart[str(menu_id)] = cart.get(str(menu_id), 0) + 1
        save_cart(cart)

    return render_template("partials/cart.html", **cart_context())


@app.post("/ui/cart/update")
def ui_cart_update():
    menu_id = str(request.values.get("menu_id", ""))
    try:
        delta = int(request.values.get("delta", 0))
    except ValueError:
        delta = 0

    cart = get_cart()
    if menu_id in cart:
        cart[menu_id] += delta
        if cart[menu_id] < 1:
            del cart[menu_id]
        save_cart(cart)

    return render_template("partials/cart.html", **cart_context())


@app.post("/ui/cart/clear")
def ui_cart_clear():
    save_cart({})
    return render_template("partials/cart.html", **cart_context())


@app.post("/ui/orders")
def ui_place_order():
    context = cart_context()

    if not context["lines"]:
        return render_template(
            "partials/order_result.html",
            error="Add at least one item before placing the order.",
        )

    payload = {
        "channel": request.form.get("channel", "DINE_IN"),
        "table_number": request.form.get("table_number") or None,
        "customer_id": session.get("customer_id"),
        "customer_name": request.form.get("customer_name") or None,
        "staff_name": session.get("staff_name", "POS Terminal"),
        "note": request.form.get("note") or None,
        "items": [
            {"menu_id": line["menu_id"], "quantity": line["quantity"]}
            for line in context["lines"]
        ],
    }

    try:
        result = call_backend("POST", "/api/orders", json=payload)
    except BackendError as exc:
        return render_template("partials/order_result.html", error=exc.message)

    save_cart({})

    html = render_template(
        "partials/order_result.html",
        order=result["order"],
        integration=result["integration"],
    )

    return trigger(html, "cartChanged", "orderPlaced")


@app.get("/ui/orders/recent")
def ui_recent_orders():
    try:
        data = call_backend("GET", "/api/orders", params={"limit": 10})
    except BackendError as exc:
        return render_template("partials/recent_orders.html", error=exc.message)

    orders = data["orders"]
    customer_view = is_customer()

    if customer_view:
        customer_id = session.get("customer_id")
        orders = [
             order
             for order in orders
             if order.get("customer_id") == customer_id
    ]

    return render_template(
        "partials/recent_orders.html",
         orders=orders,
        customer_view=customer_view,
)


# =====================================================================
# HTMX partials - Kitchen display
# =====================================================================

def render_board():
    try:
        data = call_backend("GET", "/api/order-status")
    except BackendError as exc:
        return render_template("partials/board.html", error=exc.message)

    return render_template(
        "partials/board.html",
        columns=data["columns"],
        board=data["board"],
        refreshed_at=datetime.now().strftime("%H:%M:%S"),
    )


@app.get("/ui/kitchen/board")
@staff_only_partial
def ui_board():
    return render_board()


@app.put("/ui/kitchen/advance/<int:order_id>")
@staff_only_partial
def ui_advance(order_id):
    target = request.values.get("status")

    try:
        call_backend(
            "PUT",
            "/api/order-status/%d" % order_id,
            json={"status": target, "changed_by": "kitchen display"},
        )
    except BackendError as exc:
        board = render_board()
        return ('<div class="s4-alert error"><strong>Status not changed</strong>%s</div>%s'
                % (exc.message, board))

    return trigger(render_board(), "orderChanged")


@app.post("/ui/ai/analyse")
@staff_only_partial
def ui_ai_analyse():
    try:
        result = call_backend(
            "POST", "/api/ai/kitchen-analysis", timeout=AI_HTTP_TIMEOUT
        )
    except BackendError as exc:
        return render_template("partials/ai_panel.html", error=exc.message)

    return render_template(
        "partials/ai_panel.html",
        result=result,
        metrics=result["metrics"],
        analysis=result["analysis"],
    )


# =====================================================================
# HTMX partials - Order status screen
# =====================================================================

@app.get("/ui/status/list")
@staff_only_partial
def ui_status_list():
    params = {"limit": 50}

    if request.args.get("status"):
        params["status"] = request.args["status"]
    if request.args.get("channel"):
        params["channel"] = request.args["channel"]

    try:
        data = call_backend("GET", "/api/orders", params=params)
    except BackendError as exc:
        return render_template("partials/status_list.html", error=exc.message)

    return render_template("partials/status_list.html", orders=data["orders"])


def render_detail(order_id, message=None, message_kind="ok"):
    try:
        order = call_backend("GET", "/api/orders/%d" % order_id)
        status = call_backend("GET", "/api/order-status/%d" % order_id)
    except BackendError as exc:
        return render_template("partials/order_detail.html", error=exc.message)

    return render_template(
        "partials/order_detail.html",
        order=order,
        history=status["status_history"],
        next_statuses=status["next_statuses"],
        editable=order["status"] in ("PENDING", "CONFIRMED"),
        deletable=order["status"] in ("PENDING", "CONFIRMED", "CANCELLED"),
        message=message,
        message_kind=message_kind,
    )


@app.get("/ui/status/<int:order_id>")
@staff_only_partial
def ui_status_detail(order_id):
    return render_detail(order_id)


@app.put("/ui/status/<int:order_id>/set")
def ui_status_set(order_id):
    target = request.values.get("status")

    try:
        call_backend(
            "PUT",
            "/api/order-status/%d" % order_id,
            json={"status": target, "changed_by": "order status screen"},
        )
    except BackendError as exc:
        return render_detail(order_id, message=exc.message, message_kind="error")

    html = render_detail(order_id, message="Status moved to %s." % target)
    return trigger(html, "orderChanged", "boardChanged")


@app.put("/ui/status/<int:order_id>/details")
def ui_status_update(order_id):
    payload = {
        "table_number": request.values.get("table_number") or None,
        "customer_name": request.values.get("customer_name") or None,
        "note": request.values.get("note") or None,
    }

    try:
        call_backend("PUT", "/api/orders/%d" % order_id, json=payload)
    except BackendError as exc:
        return render_detail(order_id, message=exc.message, message_kind="error")

    html = render_detail(order_id, message="Order details saved.")
    return trigger(html, "orderChanged")


@app.delete("/ui/status/<int:order_id>")
def ui_status_delete(order_id):
    try:
        order = call_backend("GET", "/api/orders/%d" % order_id)
        call_backend("DELETE", "/api/orders/%d" % order_id)
    except BackendError as exc:
        return render_detail(order_id, message=exc.message, message_kind="error")

    html = render_template(
        "partials/order_detail.html", deleted=order["order_number"]
    )
    return trigger(html, "orderChanged", "boardChanged")


@app.put("/ui/order-items/<int:item_id>")
def ui_item_update(item_id):
    order_id = int(request.values.get("order_id"))
    quantity = request.values.get("quantity")

    try:
        call_backend(
            "PUT", "/api/order-items/%d" % item_id, json={"quantity": int(quantity)}
        )
    except (BackendError, TypeError, ValueError) as exc:
        message = getattr(exc, "message", "Quantity must be a whole number.")
        return render_detail(order_id, message=message, message_kind="error")

    html = render_detail(order_id, message="Item quantity updated.")
    return trigger(html, "orderChanged")


@app.delete("/ui/order-items/<int:item_id>")
def ui_item_delete(item_id):
    order_id = int(request.values.get("order_id"))

    try:
        call_backend("DELETE", "/api/order-items/%d" % item_id)
    except BackendError as exc:
        return render_detail(order_id, message=exc.message, message_kind="error")

    html = render_detail(order_id, message="Item removed from the order.")
    return trigger(html, "orderChanged")


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5400)),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
