"""Manual smoke test for the /db/* API: create, read, update, AI write-back, delete,
then check store_logs recorded every step. Needs the database service on 7100.

    python student-1/tests/smoke_database.py
"""

import os
import sys

import requests

DB_URL = os.environ.get("DB_URL", "http://localhost:7100").rstrip("/")

passed = 0
failed = 0


def check(label, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print("  PASS  %s" % label)
    else:
        failed += 1
        print("  FAIL  %s  %s" % (label, detail))


print("Student 1 - database microservice smoke test against %s\n" % DB_URL)

# READ
stats = requests.get(DB_URL + "/db/stats", timeout=5).json()
print("Seeded data")
check("customer_feedback has >= 10 rows",
      stats["row_counts"]["customer_feedback"] >= 10,
      stats["row_counts"])
check("store_logs has >= 10 rows",
      stats["row_counts"]["store_logs"] >= 10,
      stats["row_counts"])
# Some reviews must carry a rule-based verdict for the re-check button to work on.
rule_based = [
    row for row in requests.get(
        DB_URL + "/db/feedback", params={"limit": 500}, timeout=5
    ).json()["feedback"]
    if row.get("ai_model") == "rules"
]

check("every review carries a verdict (none left unanalysed)",
      stats["unanalysed_count"] == 0, stats["unanalysed_count"])
check("some verdicts are rule-based, awaiting an LLM re-check",
      len(rule_based) > 0, len(rule_based))

# CREATE
print("\nCreate")
created = requests.post(
    DB_URL + "/db/feedback",
    json={
        "customer_id": 1,
        "customer_name": "Test Customer",
        "order_id": 7,
        "order_number": "A-1007",
        "rating": 4,
        "title": "Smoke test review",
        "comment": "Written by student-1/tests/smoke_database.py.",
        "category": "SERVICE",
    },
    timeout=5,
)
check("POST /db/feedback returns 201", created.status_code == 201,
      created.text[:120])

review = created.json()
review_id = review["id"]
check("new review starts as SUBMITTED", review["status"] == "SUBMITTED",
      review["status"])
check("new review has no AI result yet", review["analysed_at"] is None)
check("ai_issues comes back as a list", isinstance(review["ai_issues"], list))

# VALIDATION
print("\nValidation is enforced by the database service, not the caller")
for label, payload in [
    ("rating 9 rejected", {"customer_id": 1, "rating": 9, "comment": "x"}),
    ("empty comment rejected", {"customer_id": 1, "rating": 4, "comment": "   "}),
    ("bad category rejected",
     {"customer_id": 1, "rating": 4, "comment": "x", "category": "NOPE"}),
    ("missing customer_id rejected", {"rating": 4, "comment": "x"}),
]:
    response = requests.post(DB_URL + "/db/feedback", json=payload, timeout=5)
    check(label, response.status_code == 400, response.status_code)

# READ
print("\nRead")
fetched = requests.get(DB_URL + "/db/feedback/%d" % review_id, timeout=5)
check("GET /db/feedback/<id> returns 200", fetched.status_code == 200)
check("GET /db/feedback/999999 returns 404",
      requests.get(DB_URL + "/db/feedback/999999", timeout=5).status_code == 404)

mine = requests.get(
    DB_URL + "/db/feedback", params={"customer_id": 1}, timeout=5
).json()
check("customer_id filter only returns that customer",
      all(f["customer_id"] == 1 for f in mine["feedback"]) and mine["count"] > 0,
      mine["count"])

# UPDATE
print("\nUpdate")
updated = requests.put(
    DB_URL + "/db/feedback/%d" % review_id,
    json={"rating": 2, "comment": "Edited by the smoke test.",
          "actor": "customer:1"},
    timeout=5,
).json()
check("rating was updated", updated["rating"] == 2, updated["rating"])
check("comment was updated",
      updated["comment"] == "Edited by the smoke test.", updated["comment"])

status_moved = requests.put(
    DB_URL + "/db/feedback/%d" % review_id,
    json={"status": "IN_REVIEW", "actor": "staff:1", "actor_role": "STAFF"},
    timeout=5,
).json()
check("status was updated", status_moved["status"] == "IN_REVIEW",
      status_moved["status"])

check("PUT with an unknown status is rejected",
      requests.put(DB_URL + "/db/feedback/%d" % review_id,
                   json={"status": "BANANA"}, timeout=5).status_code == 400)
check("PUT with an empty body is rejected",
      requests.put(DB_URL + "/db/feedback/%d" % review_id,
                   json={}, timeout=5).status_code == 400)

# AI WRITE-BACK
print("\nAI analysis write-back")
analysed = requests.put(
    DB_URL + "/db/feedback/%d/analysis" % review_id,
    json={
        "sentiment": "NEGATIVE",
        "sentiment_score": -0.4,
        "ai_summary": "Smoke test sentiment.",
        "ai_issues": ["smoke_test", "slow_service"],
        "ai_model": "smoke-test",
    },
    timeout=5,
).json()
check("sentiment stored", analysed["sentiment"] == "NEGATIVE")
check("analysed_at stamped", analysed["analysed_at"] is not None)
check("ai_issues round-trips as a list",
      analysed["ai_issues"] == ["smoke_test", "slow_service"],
      analysed["ai_issues"])
check("out-of-range sentiment_score rejected",
      requests.put(DB_URL + "/db/feedback/%d/analysis" % review_id,
                   json={"sentiment": "POSITIVE", "sentiment_score": 5},
                   timeout=5).status_code == 400)

# AI FIELDS ARE PROTECTED
print("\nAI columns cannot be forged through the ordinary PUT")
forged = requests.put(
    DB_URL + "/db/feedback/%d" % review_id,
    json={"sentiment": "POSITIVE", "sentiment_score": 1.0, "rating": 3},
    timeout=5,
).json()
check("sentiment ignored by PUT /db/feedback/<id>",
      forged["sentiment"] == "NEGATIVE", forged["sentiment"])

# AUDIT LOG
print("\nAudit trail")
logs = requests.get(
    DB_URL + "/db/feedback/%d/logs" % review_id, timeout=5
).json()["logs"]
actions = [entry["action"] for entry in logs]

for action in ("CREATED", "UPDATED", "STATUS_CHANGED", "ANALYSED"):
    check("store_logs recorded %s" % action, action in actions, actions)

# DELETE
print("\nDelete")
deleted = requests.delete(
    DB_URL + "/db/feedback/%d" % review_id,
    json={"actor": "customer:1"}, timeout=5,
)
check("DELETE returns 200", deleted.status_code == 200, deleted.text[:120])
check("review is gone",
      requests.get(DB_URL + "/db/feedback/%d" % review_id,
                   timeout=5).status_code == 404)
check("deleting it twice returns 404",
      requests.delete(DB_URL + "/db/feedback/%d" % review_id,
                      timeout=5).status_code == 404)

after_delete = requests.get(
    DB_URL + "/db/feedback/%d/logs" % review_id, timeout=5
).json()["logs"]
check("DELETED was logged",
      "DELETED" in [entry["action"] for entry in after_delete])
check("the audit trail SURVIVED the delete (no ON DELETE CASCADE)",
      len(after_delete) >= len(logs), "%d -> %d" % (len(logs), len(after_delete)))

print("\n%d passed, %d failed" % (passed, failed))
sys.exit(1 if failed else 0)
