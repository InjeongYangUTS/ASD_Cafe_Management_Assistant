"""
Student 4 - Order & Kitchen Management
Unit tests for the DATABASE microservice (/db/* CRUD API).

These run with no containers and no network: the service is imported with a
throwaway SQLite file, so GitHub Actions can validate CRUD on every push.
"""

from conftest import sample_order_payload


# ---------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------

def test_health_reports_the_service_name(db_client):
    response = db_client.get("/db/health")

    assert response.status_code == 200
    assert response.get_json()["service"] == "student-4-database"


# ---------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------

def test_create_order_returns_totals_and_first_status(db_client):
    response = db_client.post("/db/orders", json=sample_order_payload())

    assert response.status_code == 201
    order = response.get_json()

    assert order["order_number"] == "A-1001"
    assert order["item_count"] == 3
    assert order["total_amount"] == 14.00        # 2 x 4.50 + 1 x 5.00
    assert order["prep_seconds"] == 220          # 2 x 90 + 1 x 40
    assert order["status"] == "PENDING"
    assert len(order["items"]) == 2
    assert order["status_history"][0]["status"] == "PENDING"


def test_order_numbers_increment(db_client):
    first = db_client.post("/db/orders", json=sample_order_payload()).get_json()
    second = db_client.post("/db/orders", json=sample_order_payload()).get_json()

    assert first["order_number"] == "A-1001"
    assert second["order_number"] == "A-1002"


def test_create_order_rejects_an_empty_basket(db_client):
    response = db_client.post("/db/orders", json={"items": []})

    assert response.status_code == 400
    assert "at least one item" in response.get_json()["error"]


def test_create_order_rejects_zero_quantity(db_client):
    payload = sample_order_payload()
    payload["items"][0]["quantity"] = 0

    response = db_client.post("/db/orders", json=payload)

    assert response.status_code == 400


# ---------------------------------------------------------------------
# READ
# ---------------------------------------------------------------------

def test_read_order_includes_items_and_history(db_client):
    created = db_client.post("/db/orders", json=sample_order_payload()).get_json()

    response = db_client.get("/db/orders/%d" % created["id"])

    assert response.status_code == 200
    order = response.get_json()
    assert order["id"] == created["id"]
    assert len(order["items"]) == 2
    assert len(order["status_history"]) == 1


def test_read_missing_order_is_404(db_client):
    assert db_client.get("/db/orders/9999").status_code == 404


def test_list_orders_can_filter_by_status(db_client):
    first = db_client.post("/db/orders", json=sample_order_payload()).get_json()
    db_client.post("/db/orders", json=sample_order_payload())

    db_client.post("/db/orders/%d/statuses" % first["id"],
                   json={"status": "CONFIRMED"})

    pending = db_client.get("/db/orders?status=PENDING").get_json()
    confirmed = db_client.get("/db/orders?status=CONFIRMED").get_json()

    assert pending["count"] == 1
    assert confirmed["count"] == 1
    assert confirmed["orders"][0]["id"] == first["id"]


def test_list_orders_rejects_an_unknown_status(db_client):
    response = db_client.get("/db/orders?status=FLYING")

    assert response.status_code == 400


# ---------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------

def test_update_order_changes_editable_fields(db_client):
    created = db_client.post("/db/orders", json=sample_order_payload()).get_json()

    response = db_client.put(
        "/db/orders/%d" % created["id"],
        json={"table_number": "T12", "note": "extra napkins"},
    )

    assert response.status_code == 200
    updated = response.get_json()
    assert updated["table_number"] == "T12"
    assert updated["note"] == "extra napkins"


def test_update_item_quantity_recalculates_the_order_total(db_client):
    created = db_client.post("/db/orders", json=sample_order_payload()).get_json()
    latte = created["items"][0]

    db_client.put("/db/order-items/%d" % latte["id"], json={"quantity": 4})

    order = db_client.get("/db/orders/%d" % created["id"]).get_json()

    assert order["item_count"] == 5               # 4 lattes + 1 croissant
    assert order["total_amount"] == 23.00         # 4 x 4.50 + 5.00


def test_cancelled_lines_still_count_towards_the_order_value(db_client):
    """
    Regression test for the defect the agentic review loop found:
    a cancelled order must keep its value for reporting, so recalc_order
    counts every line it still holds. Removing a line is a DELETE.
    """
    created = db_client.post("/db/orders", json=sample_order_payload()).get_json()
    latte = created["items"][0]

    db_client.put("/db/order-items/%d" % latte["id"],
                  json={"item_status": "CANCELLED"})
    db_client.post("/db/orders/%d/statuses" % created["id"],
                   json={"status": "CANCELLED"})

    order = db_client.get("/db/orders/%d" % created["id"]).get_json()

    assert order["status"] == "CANCELLED"
    assert order["total_amount"] == 14.00


def test_update_item_rejects_an_unknown_item_status(db_client):
    created = db_client.post("/db/orders", json=sample_order_payload()).get_json()
    item_id = created["items"][0]["id"]

    response = db_client.put("/db/order-items/%d" % item_id,
                             json={"item_status": "BURNT"})

    assert response.status_code == 400


def test_adding_a_status_updates_the_current_status(db_client):
    created = db_client.post("/db/orders", json=sample_order_payload()).get_json()

    db_client.post("/db/orders/%d/statuses" % created["id"],
                   json={"status": "CONFIRMED", "changed_by": "kitchen"})

    order = db_client.get("/db/orders/%d" % created["id"]).get_json()

    assert order["status"] == "CONFIRMED"
    assert [row["status"] for row in order["status_history"]] == \
           ["PENDING", "CONFIRMED"]


def test_adding_an_invalid_status_is_rejected(db_client):
    created = db_client.post("/db/orders", json=sample_order_payload()).get_json()

    response = db_client.post("/db/orders/%d/statuses" % created["id"],
                              json={"status": "NOT_A_STATUS"})

    assert response.status_code == 400


# ---------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------

def test_delete_order_removes_items_and_history(db_client):
    created = db_client.post("/db/orders", json=sample_order_payload()).get_json()
    order_id = created["id"]

    response = db_client.delete("/db/orders/%d" % order_id)

    assert response.status_code == 200
    assert response.get_json()["deleted"] is True
    assert db_client.get("/db/orders/%d" % order_id).status_code == 404

    # Cascade: the status history for that order is gone too.
    remaining = db_client.get("/db/order-statuses").get_json()
    assert all(row["order_id"] != order_id
               for row in remaining["status_history"])


def test_delete_item_recalculates_the_order(db_client):
    created = db_client.post("/db/orders", json=sample_order_payload()).get_json()
    croissant = created["items"][1]

    db_client.delete("/db/order-items/%d" % croissant["id"])
    order = db_client.get("/db/orders/%d" % created["id"]).get_json()

    assert len(order["items"]) == 1
    assert order["total_amount"] == 9.00


def test_delete_missing_order_is_404(db_client):
    assert db_client.delete("/db/orders/4242").status_code == 404


# ---------------------------------------------------------------------
# Stats (used by the kitchen board and AI-Mode)
# ---------------------------------------------------------------------

def test_stats_counts_rows_and_open_items_per_station(db_client):
    db_client.post("/db/orders", json=sample_order_payload())

    stats = db_client.get("/db/stats").get_json()

    assert stats["row_counts"]["orders"] == 1
    assert stats["row_counts"]["order_items"] == 2
    assert stats["orders_by_status"]["PENDING"] == 1
    assert stats["open_items_by_station"]["BAR"] == 2
    assert stats["open_items_by_station"]["PASTRY"] == 1
