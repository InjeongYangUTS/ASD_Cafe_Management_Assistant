"""
Student 4 - Order & Kitchen Management
Role separation between the counter and the kitchen.

Authentication is owned by the shared service on :5100. This feature reads
the session that service issued and decides what a signed-in customer may
open. A customer places orders; the kitchen board and the order-status
screen belong to staff.
"""

STAFF_PAGES = ["/kitchen", "/status"]
STAFF_FRAGMENTS = ["/ui/kitchen/board", "/ui/status/list"]

CUSTOMER = {"customer_id": 7, "customer_name": "Mina"}
STAFF = {"staff_id": 1, "staff_name": "Stella", "staff_role": "staff"}


def client_as(frontend_app, session_data):
    client = frontend_app.test_client()
    with client.session_transaction() as sess:
        sess.clear()
        sess.update(session_data)
    return client


# ---------------------------------------------------------------------
# A customer stays at the counter
# ---------------------------------------------------------------------

def test_customer_can_reach_the_pos(frontend_app):
    assert client_as(frontend_app, CUSTOMER).get("/pos").status_code == 200


def test_customer_is_sent_back_from_the_staff_pages(frontend_app):
    client = client_as(frontend_app, CUSTOMER)

    for page in STAFF_PAGES:
        response = client.get(page)
        assert response.status_code == 302, page
        assert "/customer-dashboard" in response.headers["Location"], page


def test_customer_cannot_pull_the_staff_fragments_directly(frontend_app):
    """Hiding the links is not enough - the fragments refuse the request."""
    client = client_as(frontend_app, CUSTOMER)

    for fragment in STAFF_FRAGMENTS:
        assert client.get(fragment).status_code == 403, fragment


def test_customer_cannot_advance_a_ticket(frontend_app):
    client = client_as(frontend_app, CUSTOMER)
    response = client.put("/ui/kitchen/advance/1", data={"status": "READY"})
    assert response.status_code == 403


def test_customer_cannot_run_the_ai_analysis(frontend_app):
    client = client_as(frontend_app, CUSTOMER)
    assert client.post("/ui/ai/analyse").status_code == 403


def test_the_customer_navigation_hides_the_staff_screens(frontend_app):
    body = client_as(frontend_app, CUSTOMER).get("/pos").get_data(as_text=True)

    assert 'href="/kitchen"' not in body
    assert 'href="/status"' not in body
    assert 'href="/pos"' in body


# ---------------------------------------------------------------------
# Staff keep the whole feature
# ---------------------------------------------------------------------

def test_staff_can_open_every_screen(frontend_app):
    client = client_as(frontend_app, STAFF)

    for page in ["/pos"] + STAFF_PAGES:
        assert client.get(page).status_code == 200, page


def test_the_staff_navigation_shows_the_staff_screens(frontend_app):
    body = client_as(frontend_app, STAFF).get("/pos").get_data(as_text=True)

    assert 'href="/kitchen"' in body
    assert 'href="/status"' in body


# ---------------------------------------------------------------------
# The way home matches who is signed in
# ---------------------------------------------------------------------

def test_a_customer_is_sent_home_to_the_customer_dashboard(frontend_app):
    body = client_as(frontend_app, CUSTOMER).get("/pos").get_data(as_text=True)

    assert "Back to Customer Dashboard" in body
    assert "/customer-dashboard" in body


def test_staff_are_sent_home_to_the_staff_dashboard(frontend_app):
    body = client_as(frontend_app, STAFF).get("/pos").get_data(as_text=True)

    assert "Back to Staff Dashboard" in body
    assert "/staff-dashboard" in body
