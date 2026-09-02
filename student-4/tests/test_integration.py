"""
Student 4 - Order & Kitchen Management
Integration tests against the RUNNING containers.

Skipped unless the service URLs are set, so `pytest` still works on a laptop
with nothing started. GitHub Actions sets them after `docker compose up`:

    S4_DB_URL=http://localhost:7400
    S4_BACKEND_URL=http://localhost:8400
    S4_FRONTEND_URL=http://localhost:5400
"""

import os

import pytest
import requests

DB_URL = os.environ.get("S4_DB_URL")
BACKEND_URL = os.environ.get("S4_BACKEND_URL")
FRONTEND_URL = os.environ.get("S4_FRONTEND_URL")

pytestmark = pytest.mark.skipif(
    not (DB_URL and BACKEND_URL and FRONTEND_URL),
    reason="service URLs not set - integration tests need the containers running",
)

TIMEOUT = 15


# ---------------------------------------------------------------------
# Health of all three containers
# ---------------------------------------------------------------------

def test_database_container_is_healthy():
    body = requests.get(DB_URL + "/db/health", timeout=TIMEOUT).json()
    assert body["status"] == "healthy"


def test_backend_container_is_healthy():
    response = requests.get(BACKEND_URL + "/api/health", timeout=TIMEOUT)
    body = response.json()

    assert response.status_code == 200
    assert body["service"] == "student-4-backend"
    assert body["dependencies"]["order_database"]["reachable"] is True


def test_frontend_container_is_healthy():
    body = requests.get(FRONTEND_URL + "/health", timeout=TIMEOUT).json()
    assert body["service"] == "student-4-frontend"


# ---------------------------------------------------------------------
# The three screens render
# ---------------------------------------------------------------------

@pytest.mark.parametrize("path,marker", [
    ("/pos", "Point of Sale"),
    ("/kitchen", "Kitchen Display System"),
    ("/status", "Order Status"),
])
def test_screens_render(path, marker):
    response = requests.get(FRONTEND_URL + path, timeout=TIMEOUT)

    assert response.status_code == 200
    assert marker in response.text
    assert "/shared/css/style.css" in response.text


def test_shared_theme_is_served_by_the_frontend():
    response = requests.get(FRONTEND_URL + "/shared/css/style.css",
                            timeout=TIMEOUT)
    assert response.status_code == 200


# ---------------------------------------------------------------------
# Seeded data
# ---------------------------------------------------------------------

def test_database_has_at_least_ten_seeded_orders():
    stats = requests.get(DB_URL + "/db/stats", timeout=TIMEOUT).json()

    assert stats["row_counts"]["orders"] >= 10
    assert stats["row_counts"]["order_items"] >= 10
    assert stats["row_counts"]["order_statuses"] >= 10


def test_menu_is_available_through_the_backend():
    body = requests.get(BACKEND_URL + "/api/menu", timeout=TIMEOUT).json()

    assert body["count"] >= 15
    assert body["source"] in ("menu-service", "fallback")


# ---------------------------------------------------------------------
# Full CRUD round trip through the real stack
# ---------------------------------------------------------------------

def test_full_crud_round_trip():
    # CREATE
    created = requests.post(
        BACKEND_URL + "/api/orders",
        json={
            "channel": "TAKEAWAY",
            "customer_name": "CI Integration Test",
            "items": [{"menu_id": 2, "quantity": 2},
                      {"menu_id": 15, "quantity": 1}],
        },
        timeout=TIMEOUT,
    )
    assert created.status_code == 201

    order = created.json()["order"]
    order_id = order["id"]
    assert order["item_count"] == 3
    assert order["status"] == "PENDING"

    try:
        # READ
        read = requests.get(BACKEND_URL + "/api/orders/%d" % order_id,
                            timeout=TIMEOUT).json()
        assert read["order_number"] == order["order_number"]
        assert len(read["items"]) == 2

        # UPDATE - order details
        requests.put(
            BACKEND_URL + "/api/orders/%d" % order_id,
            json={"note": "updated by CI"}, timeout=TIMEOUT,
        )
        assert requests.get(
            BACKEND_URL + "/api/orders/%d" % order_id, timeout=TIMEOUT
        ).json()["note"] == "updated by CI"

        # UPDATE - item quantity, order total recalculated
        item_id = read["items"][0]["id"]
        requests.put(BACKEND_URL + "/api/order-items/%d" % item_id,
                     json={"quantity": 5}, timeout=TIMEOUT)

        assert requests.get(
            BACKEND_URL + "/api/orders/%d" % order_id, timeout=TIMEOUT
        ).json()["item_count"] == 6

        # UPDATE - status lifecycle, and an illegal jump is refused
        illegal = requests.put(
            BACKEND_URL + "/api/order-status/%d" % order_id,
            json={"status": "COMPLETED"}, timeout=TIMEOUT,
        )
        assert illegal.status_code == 409

        for target in ("CONFIRMED", "PREPARING", "READY"):
            moved = requests.put(
                BACKEND_URL + "/api/order-status/%d" % order_id,
                json={"status": target}, timeout=TIMEOUT,
            )
            assert moved.status_code == 200
            assert moved.json()["status"] == target

        history = requests.get(
            BACKEND_URL + "/api/order-status/%d" % order_id, timeout=TIMEOUT
        ).json()["status_history"]
        assert [row["status"] for row in history] == \
               ["PENDING", "CONFIRMED", "PREPARING", "READY"]

        # A READY order must not be deletable
        assert requests.delete(
            BACKEND_URL + "/api/orders/%d" % order_id, timeout=TIMEOUT
        ).status_code == 409

        requests.put(BACKEND_URL + "/api/order-status/%d" % order_id,
                     json={"status": "COMPLETED"}, timeout=TIMEOUT)

    finally:
        # DELETE - straight through the database service so CI leaves no trace
        requests.delete(DB_URL + "/db/orders/%d" % order_id, timeout=TIMEOUT)

    assert requests.get(
        BACKEND_URL + "/api/orders/%d" % order_id, timeout=TIMEOUT
    ).status_code == 404


def test_unknown_menu_item_is_rejected():
    response = requests.post(
        BACKEND_URL + "/api/orders",
        json={"items": [{"menu_id": 999, "quantity": 1}]},
        timeout=TIMEOUT,
    )

    assert response.status_code == 400
    assert "999" in response.json()["error"]


# ---------------------------------------------------------------------
# AI-Mode reachable through the stack (works with or without Ollama)
# ---------------------------------------------------------------------

def test_ai_endpoint_always_answers():
    response = requests.post(BACKEND_URL + "/api/ai/kitchen-analysis",
                             timeout=90)
    body = response.json()

    assert response.status_code == 200
    assert body["mode"] in ("ollama", "heuristic")
    assert "congestion_level" in body["metrics"]
    assert body["analysis"]["action"]


def test_kitchen_board_groups_orders_by_status():
    body = requests.get(BACKEND_URL + "/api/order-status", timeout=TIMEOUT).json()

    assert body["columns"] == ["PENDING", "CONFIRMED", "PREPARING", "READY"]
    for column in body["columns"]:
        assert column in body["board"]
