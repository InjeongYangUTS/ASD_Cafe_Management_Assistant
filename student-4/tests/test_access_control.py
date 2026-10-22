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


# ---------------------------------------------------------------------
# The Multi-Agent panel is staff-only too          (Release 2)
#
# The human-review stage is a staff decision recorded against a named
# workflow, so a customer must not be able to start a run or decide on
# one - including by posting to the fragment directly, which is the
# only route that matters once the link is hidden.
# ---------------------------------------------------------------------

def test_customer_cannot_start_a_multi_agent_workflow(frontend_app):
    client = client_as(frontend_app, CUSTOMER)
    response = client.post("/ui/ai/multi-agent", data={"task": "anything"})
    assert response.status_code == 403


def test_customer_cannot_read_a_multi_agent_workflow(frontend_app):
    client = client_as(frontend_app, CUSTOMER)
    assert client.get("/ui/ai/multi-agent/wf-1").status_code == 403


def test_customer_cannot_decide_on_a_multi_agent_workflow(frontend_app):
    """The human-review stage is the one that must not be forgeable."""
    client = client_as(frontend_app, CUSTOMER)
    response = client.post("/ui/ai/multi-agent/wf-1/review",
                           data={"decision": "approve"})
    assert response.status_code == 403


def test_the_decision_is_refused_before_it_reaches_the_server(frontend_app):
    """A non-approval with no reason never leaves this service.

    Staff, not a customer - so this is the panel's own rule, not the
    role guard: a rejection with nothing written against it would leave
    whoever picks it up nothing to act on.
    """
    client = client_as(frontend_app, STAFF)
    response = client.post("/ui/ai/multi-agent/wf-1/review",
                           data={"decision": "reject", "comments": "   "})

    assert response.status_code == 200
    assert "Say what is wrong" in response.get_data(as_text=True)


def test_an_unknown_decision_is_refused(frontend_app):
    client = client_as(frontend_app, STAFF)
    response = client.post("/ui/ai/multi-agent/wf-1/review",
                           data={"decision": "maybe", "comments": "hm"})

    assert "four decisions" in response.get_data(as_text=True)
