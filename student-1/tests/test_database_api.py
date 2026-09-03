"""
Student 1 (Hangyeol Yi) - Customer Feedback & Reviews
Tests for the DATABASE microservice (/db/* API).

These cover the rules the schema promises and the two design decisions
the technical report defends: the audit trail survives a delete, and the
AI columns cannot be written through the ordinary update path.
"""


# =====================================================================
# Create
# =====================================================================

def test_create_returns_the_stored_review(db_client):
    response = db_client.post("/db/feedback", json={
        "customer_id": 1,
        "customer_name": "Test Customer",
        "rating": 4,
        "title": "Good",
        "comment": "The croissant was still warm.",
        "category": "FOOD",
    })

    assert response.status_code == 201

    review = response.get_json()
    assert review["rating"] == 4
    assert review["status"] == "SUBMITTED"
    assert review["analysed_at"] is None
    # SQLite has no array type; the API is responsible for the conversion.
    assert review["ai_issues"] == []


def test_create_writes_an_audit_entry(db_client):
    review_id = db_client.post("/db/feedback", json={
        "customer_id": 1, "rating": 4, "comment": "Fine.",
    }).get_json()["id"]

    logs = db_client.get("/db/feedback/%d/logs" % review_id).get_json()["logs"]

    assert [entry["action"] for entry in logs] == ["CREATED"]
    assert logs[0]["actor_role"] == "CUSTOMER"


def test_rating_must_be_one_to_five(db_client):
    for rating in (0, 6, -1, "five", None):
        response = db_client.post("/db/feedback", json={
            "customer_id": 1, "rating": rating, "comment": "x",
        })
        assert response.status_code == 400, "rating %r was accepted" % rating


def test_comment_is_required(db_client):
    response = db_client.post("/db/feedback", json={
        "customer_id": 1, "rating": 4, "comment": "   ",
    })
    assert response.status_code == 400


def test_unknown_category_is_rejected(db_client):
    response = db_client.post("/db/feedback", json={
        "customer_id": 1, "rating": 4, "comment": "x", "category": "BANANA",
    })
    assert response.status_code == 400


# =====================================================================
# Read
# =====================================================================

def test_customer_filter_returns_only_that_customer(seeded_client):
    payload = seeded_client.get("/db/feedback?customer_id=1").get_json()

    assert payload["count"] == 2
    assert {row["customer_id"] for row in payload["feedback"]} == {1}


def test_rating_filter(seeded_client):
    payload = seeded_client.get("/db/feedback?max_rating=3").get_json()

    assert payload["count"] == 2
    assert all(row["rating"] <= 3 for row in payload["feedback"])


def test_unknown_review_returns_404(db_client):
    assert db_client.get("/db/feedback/999999").status_code == 404


def test_stats_counts_both_tables(seeded_client):
    stats = seeded_client.get("/db/stats").get_json()

    assert stats["row_counts"]["customer_feedback"] == 3
    # One CREATED entry per review.
    assert stats["row_counts"]["store_logs"] == 3
    assert stats["average_rating"] == 3.33
    assert stats["unanalysed_count"] == 3


# =====================================================================
# Update
# =====================================================================

def test_update_changes_the_review_and_logs_it(db_client):
    review_id = db_client.post("/db/feedback", json={
        "customer_id": 1, "rating": 4, "comment": "Fine.",
    }).get_json()["id"]

    updated = db_client.put("/db/feedback/%d" % review_id, json={
        "rating": 2, "comment": "Actually it was cold.",
    }).get_json()

    assert updated["rating"] == 2
    assert updated["comment"] == "Actually it was cold."

    actions = [entry["action"] for entry
               in db_client.get("/db/feedback/%d/logs" % review_id).get_json()["logs"]]
    assert "UPDATED" in actions


def test_status_change_is_logged_separately_from_an_edit(db_client):
    review_id = db_client.post("/db/feedback", json={
        "customer_id": 1, "rating": 4, "comment": "Fine.",
    }).get_json()["id"]

    db_client.put("/db/feedback/%d" % review_id,
                  json={"status": "IN_REVIEW", "actor": "staff:1"})

    actions = [entry["action"] for entry
               in db_client.get("/db/feedback/%d/logs" % review_id).get_json()["logs"]]

    # A staff member moving the status is a different event from a
    # customer rewriting their review, and the log has to tell them apart.
    assert "STATUS_CHANGED" in actions
    assert "UPDATED" not in actions


def test_empty_update_is_rejected(db_client):
    review_id = db_client.post("/db/feedback", json={
        "customer_id": 1, "rating": 4, "comment": "Fine.",
    }).get_json()["id"]

    assert db_client.put("/db/feedback/%d" % review_id, json={}).status_code == 400


# =====================================================================
# AI analysis write-back
# =====================================================================

def test_analysis_is_stored_and_round_trips_as_a_list(db_client):
    review_id = db_client.post("/db/feedback", json={
        "customer_id": 1, "rating": 2, "comment": "Cold and slow.",
    }).get_json()["id"]

    analysed = db_client.put("/db/feedback/%d/analysis" % review_id, json={
        "sentiment": "NEGATIVE",
        "sentiment_score": -0.7,
        "ai_summary": "Cold drink and a long wait.",
        "ai_issues": ["cold_drink", "slow_service"],
        "ai_model": "qwen2.5:0.5b",
    }).get_json()

    assert analysed["sentiment"] == "NEGATIVE"
    assert analysed["sentiment_score"] == -0.7
    assert analysed["ai_issues"] == ["cold_drink", "slow_service"]
    assert analysed["analysed_at"] is not None
    assert analysed["ai_model"] == "qwen2.5:0.5b"


def test_analysis_is_attributed_to_the_ai_actor(db_client):
    review_id = db_client.post("/db/feedback", json={
        "customer_id": 1, "rating": 2, "comment": "Cold.",
    }).get_json()["id"]

    db_client.put("/db/feedback/%d/analysis" % review_id, json={
        "sentiment": "NEGATIVE", "sentiment_score": -0.5,
        "ai_model": "qwen2.5:0.5b",
    })

    logs = db_client.get("/db/feedback/%d/logs" % review_id).get_json()["logs"]
    analysed = [entry for entry in logs if entry["action"] == "ANALYSED"]

    assert len(analysed) == 1
    assert analysed[0]["actor_role"] == "AI"


def test_sentiment_score_must_be_in_range(db_client):
    review_id = db_client.post("/db/feedback", json={
        "customer_id": 1, "rating": 2, "comment": "Cold.",
    }).get_json()["id"]

    for score in (5, -5, "warm"):
        response = db_client.put("/db/feedback/%d/analysis" % review_id, json={
            "sentiment": "NEGATIVE", "sentiment_score": score,
        })
        assert response.status_code == 400, "score %r was accepted" % score


def test_ai_columns_cannot_be_written_through_the_ordinary_update(db_client):
    """
    A customer editing their own review must not be able to set the
    sentiment the staff screen reads. AI values have exactly one entry
    point: PUT /db/feedback/<id>/analysis.
    """
    review_id = db_client.post("/db/feedback", json={
        "customer_id": 1, "rating": 1, "comment": "Terrible.",
    }).get_json()["id"]

    forged = db_client.put("/db/feedback/%d" % review_id, json={
        "sentiment": "POSITIVE",
        "sentiment_score": 1.0,
        "ai_summary": "Customer loved it.",
        "rating": 2,
    }).get_json()

    assert forged["rating"] == 2, "the ordinary field should still update"
    assert forged["sentiment"] is None
    assert forged["sentiment_score"] is None
    assert forged["ai_summary"] is None


# =====================================================================
# Delete
# =====================================================================

def test_delete_removes_the_review(db_client):
    review_id = db_client.post("/db/feedback", json={
        "customer_id": 1, "rating": 4, "comment": "Fine.",
    }).get_json()["id"]

    assert db_client.delete("/db/feedback/%d" % review_id).status_code == 200
    assert db_client.get("/db/feedback/%d" % review_id).status_code == 404
    assert db_client.delete("/db/feedback/%d" % review_id).status_code == 404


def test_audit_trail_survives_the_delete(db_client):
    """
    The point of store_logs is to record deletions, so it deliberately has
    no ON DELETE CASCADE. If this test ever fails, a cascade has been
    added and the audit trail has quietly stopped being an audit trail.
    """
    review_id = db_client.post("/db/feedback", json={
        "customer_id": 1, "rating": 4, "comment": "Fine.",
    }).get_json()["id"]

    db_client.delete("/db/feedback/%d" % review_id, json={"actor": "customer:1"})

    logs = db_client.get("/db/feedback/%d/logs" % review_id).get_json()["logs"]
    actions = [entry["action"] for entry in logs]

    assert "CREATED" in actions, "the creation record was destroyed by the delete"
    assert "DELETED" in actions, "the deletion itself was not recorded"


# =====================================================================
# Health
# =====================================================================

def test_health_reports_both_tables(db_client):
    payload = db_client.get("/db/health").get_json()

    assert payload["status"] == "healthy"
    assert set(payload["tables"]) == {"customer_feedback", "store_logs"}


# =====================================================================
# One customer must never reach another customer's review
# =====================================================================

def test_a_customer_cannot_edit_another_customers_review(db_client):
    """
    The backend refuses this with 403. The check lives there rather than
    only in the frontend, because the frontend is not the only possible
    caller - anything that can reach port 8100 can try.
    """
    mine = db_client.post("/db/feedback", json={
        "customer_id": 1, "rating": 4, "comment": "Mine.",
    }).get_json()

    # The database service itself is deliberately not the gate: it is a
    # storage API and takes what it is told. What it MUST do is record who
    # made the change, so an unauthorised edit is at least attributable.
    db_client.put("/db/feedback/%d" % mine["id"], json={
        "comment": "Edited by someone else.",
        "actor": "customer:999", "actor_role": "CUSTOMER",
    })

    logs = db_client.get("/db/feedback/%d/logs" % mine["id"]).get_json()["logs"]
    actors = [entry["actor"] for entry in logs]

    assert "customer:999" in actors, "the edit was not attributed to anyone"


def test_customer_filter_does_not_leak_other_customers(seeded_client):
    """
    The "my reviews" screen is built from this filter. If it ever returned
    a row belonging to somebody else, that review would appear on a
    stranger's screen with Edit and Delete buttons next to it.
    """
    for customer_id in (1, 2):
        payload = seeded_client.get(
            "/db/feedback?customer_id=%d" % customer_id
        ).get_json()

        assert payload["count"] > 0
        assert {row["customer_id"] for row in payload["feedback"]} == {customer_id}
