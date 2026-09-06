import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("FEEDBACK_DB_PATH", os.path.join(BASE_DIR, "feedback.db"))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

NOW = datetime.now(timezone.utc)


def hours_ago(hours):
    return (NOW - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")


FEEDBACK = [

    (104, "Marcus Reid", None, None, 5,
     "Best croissant in the neighbourhood",
     "The croissant is genuinely the best I have had in Sydney and it was "
     "still warm. Will be back on the weekend.",
     "FOOD", "RESOLVED", "Glad you enjoyed it - the pastries are baked at 6am daily.",
     "POSITIVE", 0.91,
     "Strong praise for pastry quality and freshness.",
     [], "qwen2.5:0.5b", 1080),

    (113, "Noah Wilson", None, None, 4,
     "Reliable morning stop",
     "I come in most days before work. The flat white is consistent and the "
     "team is quick even when there is a queue.",
     "DRINK", "ARCHIVED", None,
     "POSITIVE", 0.74,
     "Regular customer praising consistency and speed.",
     [], "qwen2.5:0.5b", 1010),

    (114, "Isla Fraser", None, None, 2,
     "Blueberry muffin was stale",
     "The blueberry muffin tasted like it had been out since the day before. "
     "Dry and crumbly.",
     "FOOD", "RESOLVED", "Sorry about that - muffins are now pulled after 24 hours.",
     "NEGATIVE", -0.68,
     "Stale pastry, since addressed by a stock rotation change.",
     ["food_quality"], "qwen2.5:0.5b", 960),

    (115, "Oliver Bennett", None, None, 3,
     "Fine but nothing special",
     "The chicken sandwich was fine. Bread was fresh, filling was a bit thin "
     "for the price.",
     "PRICE", "ARCHIVED", None,
     "NEUTRAL", -0.12,
     "Adequate food, perceived as slightly overpriced.",
     ["price"], "qwen2.5:0.5b", 890),

    (1, "Test Customer", 1, "A-1001", 5,
     "Best flat white in the area",
     "The flat white was perfectly extracted and the barista remembered my "
     "usual order. Table service was quick even though the shop was busy.",
     "DRINK", "RESOLVED", "Thank you! We will pass this on to the team.",
     "POSITIVE", 0.88,
     "Customer praises coffee quality and staff recall of their regular order.",
     [], "qwen2.5:0.5b", 720),

    (105, "Priya Nair", None, None, 1,
     "Cold food and a dirty table",
     "The avocado toast was lukewarm and the table had not been wiped from "
     "the previous customer. I had to ask twice for it to be cleaned.",
     "CLEANLINESS", "RESOLVED", "We have added a fixed table-wipe round during service.",
     "NEGATIVE", -0.85,
     "Two separate failures in one visit: food served cold and an uncleaned table.",
     ["cold_food", "cleanliness"], "qwen2.5:0.5b", 620),

    (116, "Chloe Adams", None, None, 5,
     "Chocolate cake is excellent",
     "Had the chocolate cake with a long black. The cake was rich and not too "
     "sweet, exactly right.",
     "FOOD", "ARCHIVED", None,
     "POSITIVE", 0.83,
     "Praise for the chocolate cake.",
     [], "qwen2.5:0.5b", 540),

    (117, "Ryan Kelly", None, None, 2,
     "Long black went cold on the pass",
     "Ordered a long black and it sat on the counter for a good ten minutes "
     "before anyone called it. Cold by the time I got it.",
     "WAIT_TIME", "ACKNOWLEDGED", None,
     "NEGATIVE", -0.71,
     "Drink left uncollected on the pass.",
     ["cold_drink", "slow_service"], "qwen2.5:0.5b", 480),

    (102, "Daniel Park", 2, "A-1002", 2,
     "Waited 25 minutes for a takeaway",
     "Ordered a takeaway latte at 8:10am and did not get it until 8:35. "
     "Three people who ordered after me were served first. I was late for work.",
     "WAIT_TIME", "IN_REVIEW", None,
     "NEGATIVE", -0.72,
     "Long morning-peak wait and takeaway orders served out of sequence.",
     ["slow_service", "order_accuracy"], "qwen2.5:0.5b", 400),

    (118, "Mia Turner", None, None, 4,
     "Lovely hot chocolate",
     "The hot chocolate is properly made, not a powder mix. Good on a cold "
     "morning.",
     "DRINK", "ARCHIVED", None,
     "POSITIVE", 0.66,
     "Praise for the hot chocolate.",
     [], "qwen2.5:0.5b", 330),

    (103, "Amelia Chen", 3, "A-1003", 4,
     "Lovely brunch, tiny mix-up",
     "The avocado toast was excellent and came out hot. One coffee was the "
     "wrong order but the staff fixed it straight away.",
     "FOOD", "ACKNOWLEDGED", None,
     "POSITIVE", 0.41,
     "Food quality praised; a minor order error was recovered well by staff.",
     ["order_accuracy"], "qwen2.5:0.5b", 260),

    (119, "Jack Sullivan", None, None, 1,
     "Toastie was burnt",
     "The ham and cheese toastie came out burnt on one side. I did not have "
     "time to send it back.",
     "FOOD", "IN_REVIEW", None,
     "NEGATIVE", -0.79,
     "Burnt toastie, not raised at the counter.",
     ["food_quality"], "qwen2.5:0.5b", 200),

    (1, "Test Customer", 4, "A-1004", 3,
     "Order cancelled without much explanation",
     "My order was cancelled at the counter and I only found out when I asked. "
     "The refund was quick but nobody explained what went wrong.",
     "SERVICE", "IN_REVIEW", None,
     "NEUTRAL", -0.20,
     "Refund handled quickly but the cancellation was not communicated.",
     ["communication"], "qwen2.5:0.5b", 150),

    (120, "Sophie Laurent", None, None, 5,
     "The iced latte is my summer order",
     "The iced latte is properly strong instead of watered down. Staff are "
     "always friendly.",
     "DRINK", "SUBMITTED", None,
     "POSITIVE", 0.86,
     "Praise for the iced latte and the staff.",
     [], "llama3.2", 120),

    (106, "Jordan Lee", 8, "A-1008", 2,
     "Coffee was cold by the time it reached me",
     "Sat for ten minutes on the pass before anyone called my name. By then the "
     "long black was cold. Same thing happened last week during the 8am rush.",
     "WAIT_TIME", "SUBMITTED", None,
     "NEGATIVE", -0.68,
     "Repeat complaint: drinks sitting on the pass uncollected at the morning peak.",
     ["cold_drink", "slow_service"], "llama3.2", 100),

    (121, "Ben Carter", None, None, 3,
     "Cappuccino was average",
     "The cappuccino was fine but the foam was flat. Not what I expect at "
     "this price.",
     "DRINK", "SUBMITTED", None,
     None, None, None, None, None, 80),

    (107, "Sofia Rossi", 9, "A-1009", 4,
     "Nice spot to work from",
     "Good wifi, plenty of power points and the staff never rush you out. The "
     "oat flat white is well made. Only downside is how loud the grinder is.",
     "GENERAL", "SUBMITTED", None,
     None, None, None, None, None, 70),

    (122, "Hannah Wright", None, None, 1,
     "Wrong milk again",
     "I asked for oat milk in my cappuccino and got regular. This is the "
     "second time. Please check the ticket before making it.",
     "SERVICE", "SUBMITTED", None,
     None, None, None, None, None, 60),

    (108, "Henry Wu", 10, "A-1010", 2,
     "Prices have gone up a lot",
     "A regular latte is now $5.80 which is more than anywhere else on this "
     "street. The coffee is good but not that much better than next door.",
     "PRICE", "SUBMITTED", None,
     None, None, None, None, None, 52),

    (123, "Lucas Meyer", None, None, 4,
     "Great croissant, tight seating",
     "The croissant was flaky and fresh. Only issue is how cramped the tables "
     "are at lunch.",
     "FOOD", "SUBMITTED", None,
     None, None, None, None, None, 44),

    (1, "Test Customer", 7, "A-1007", 5,
     "Staff went out of their way",
     "I left my laptop charger behind and the team put it aside and messaged me. "
     "Small thing but it made my week.",
     "SERVICE", "SUBMITTED", None,
     None, None, None, None, None, 22),

    (124, "Emily Novak", None, None, 2,
     "Chocolate cake was dry today",
     "Usually the chocolate cake is great but today's slice was dry, like it "
     "had been cut hours earlier.",
     "FOOD", "SUBMITTED", None,
     None, None, None, None, None, 18),

    (109, "Olivia Brown", 12, "A-1012", 3,
     "Good coffee, very slow at peak",
     "No complaints about the drinks themselves but 8-9am is chaos. You can see "
     "the single barista drowning. Needs a second person on the machine.",
     "WAIT_TIME", "SUBMITTED", None,
     None, None, None, None, None, 14),

    (110, "Ethan Nguyen", None, None, 1,
     "Wrong order twice in one week",
     "Asked for oat milk twice and got dairy both times. I am lactose intolerant "
     "so this is not a small mistake. Nobody checked the ticket.",
     "SERVICE", "SUBMITTED", None,
     None, None, None, None, None, 11),

    (125, "Ava Robinson", None, None, 5,
     "Flat white is consistently excellent",
     "Third time this week. The flat white is well made every single time and "
     "the staff are friendly.",
     "DRINK", "SUBMITTED", None,
     None, None, None, None, None, 8),

    (111, "Grace Miller", 11, "A-1011", 4,
     "Consistent and friendly",
     "Been coming here three times a week for a year. The quality never drops "
     "and they always remember the regulars. Seating is a bit tight at lunch.",
     "GENERAL", "SUBMITTED", None,
     None, None, None, None, None, 6),

    (126, "Tom Baxter", None, None, 2,
     "Avocado toast arrived cold",
     "The avocado toast was cold in the middle. Sent it back and the second "
     "one was fine, but it cost me twenty minutes.",
     "FOOD", "SUBMITTED", None,
     None, None, None, None, None, 5),

    (1, "Test Customer", None, None, 4,
     "Quiet in the afternoon, which I like",
     "Came in at 3pm and it was calm. The blueberry muffin was fresh and the "
     "long black was hot.",
     "GENERAL", "SUBMITTED", None,
     None, None, None, None, None, 4),

    (127, "Zara Hussain", None, None, 5,
     "Remade my drink without me asking",
     "They noticed the milk had split and remade my flat white before handing "
     "it over. That is the kind of attention to detail I keep coming back for.",
     "DRINK", "SUBMITTED", None,
     None, None, None, None, None, 3),

    (112, "Liam O'Connor", None, None, 3,
     "Table was sticky",
     "Coffee was good but the table had crumbs and a sticky patch. Had to move "
     "to another one.",
     "CLEANLINESS", "SUBMITTED", None,
     None, None, None, None, None, 2),
]


ORPHAN_LOGS = [
    (1001, "CREATED", "customer:131", "CUSTOMER", "rating 2, category FOOD", 300),
    (1001, "ANALYSED", "ai", "AI", "NEGATIVE (-0.50) via rules", 299),
    (1001, "DELETED", "customer:131", "CUSTOMER",
     "deleted review by Peter Zhang (rating 2)", 250),

    (1002, "CREATED", "customer:132", "CUSTOMER", "rating 1, category SERVICE", 96),
    (1002, "DELETED", "staff:1", "STAFF",
     "removed review by Anonymous (rating 1) - abusive language", 90),
]


ISSUE_PHRASES = {
    "slow_service": ["wait", "waited", "slow", "queue", "late"],
    "cold_food": ["lukewarm", "cold food", "went cold"],
    "cold_drink": ["cold coffee", "was cold", "gone cold"],
    "order_accuracy": ["wrong", "mistake", "instead of", "mix-up"],
    "cleanliness": ["dirty", "not wiped", "unclean", "sticky"],
    "communication": ["nobody explained", "no explanation", "not told"],
    "price": ["expensive", "pricey", "price", "prices"],
    "noise": ["loud", "noisy"],
    "seating": ["tight", "cramped", "crowded", "seating"],
    "allergen_handling": ["lactose", "intolerant", "allergy", "dairy"],
}


def rule_based_verdict(rating, title, comment):
    text = ("%s %s" % (title or "", comment or "")).lower()

    score = max(-1.0, min(1.0, (rating - 3) / 2.0))
    sentiment = ("POSITIVE" if score >= 0.25
                 else "NEGATIVE" if score <= -0.25 else "NEUTRAL")

    issues = [tag for tag, phrases in ISSUE_PHRASES.items()
              if any(phrase in text for phrase in phrases)]

    if issues:
        summary = ("%d-star review reporting %s."
                   % (rating, ", ".join(tag.replace("_", " ")
                                        for tag in issues[:3])))
    else:
        summary = "%d-star review with no specific issue detected." % rating

    return sentiment, round(score, 3), issues, summary, "rules"


def seed():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    with open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
        conn.executescript(schema_file.read())

    existing = conn.execute(
        "SELECT COUNT(*) FROM customer_feedback"
    ).fetchone()[0]

    if existing:
        print("feedback.db already holds %d review(s) - leaving it alone."
              % existing)
        conn.close()
        return

    for row in FEEDBACK:
        (customer_id, customer_name, order_id, order_number, rating, title,
         comment, category, status, staff_response, sentiment, score,
         ai_summary, ai_issues, ai_model, age) = row

        submitted_at = hours_ago(age)

        if not sentiment:
            sentiment, score, ai_issues, ai_summary, ai_model = (
                rule_based_verdict(rating, title, comment)
            )

        analysed_at = hours_ago(age - 1)

        cursor = conn.execute(
            """
            INSERT INTO customer_feedback
                (customer_id, customer_name, order_id, order_number, rating,
                 title, comment, category, status, staff_response,
                 sentiment, sentiment_score, ai_summary, ai_issues, ai_model,
                 analysed_at, submitted_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                customer_id, customer_name, order_id, order_number, rating,
                title, comment, category, status, staff_response,
                sentiment, score, ai_summary,
                json.dumps(ai_issues) if ai_issues else None,
                ai_model, analysed_at, submitted_at, submitted_at,
            ),
        )

        feedback_id = cursor.lastrowid

        def log(action, actor, actor_role, detail, at):
            conn.execute(
                "INSERT INTO store_logs (feedback_id, entity, action, actor, "
                "actor_role, detail, created_at) "
                "VALUES (?, 'customer_feedback', ?, ?, ?, ?, ?)",
                (feedback_id, action, actor, actor_role, detail, at),
            )

        log("CREATED", "customer:%d" % customer_id, "CUSTOMER",
            "rating %d, category %s" % (rating, category), submitted_at)

        log("ANALYSED", "ai", "AI",
            "%s (%.2f) via %s" % (sentiment, score, ai_model), analysed_at)

        if status != "SUBMITTED":
            log("STATUS_CHANGED", "staff:1", "STAFF",
                "SUBMITTED -> %s" % status, hours_ago(max(age - 2, 0)))

        if staff_response:
            log("RESPONDED", "staff:1", "STAFF",
                "staff response recorded", hours_ago(max(age - 3, 0)))

    for feedback_id, action, actor, actor_role, detail, age in ORPHAN_LOGS:
        conn.execute(
            "INSERT INTO store_logs (feedback_id, entity, action, actor, "
            "actor_role, detail, created_at) "
            "VALUES (?, 'customer_feedback', ?, ?, ?, ?, ?)",
            (feedback_id, action, actor, actor_role, detail, hours_ago(age)),
        )

    conn.commit()

    feedback_count = conn.execute(
        "SELECT COUNT(*) FROM customer_feedback"
    ).fetchone()[0]
    log_count = conn.execute("SELECT COUNT(*) FROM store_logs").fetchone()[0]
    rule_based = conn.execute(
        "SELECT COUNT(*) FROM customer_feedback WHERE ai_model = 'rules'"
    ).fetchone()[0]

    conn.close()

    print("Seeded %s" % DB_PATH)
    print("  customer_feedback : %d rows (%d awaiting an LLM re-check)"
          % (feedback_count, rule_based))
    print("  store_logs        : %d rows" % log_count)


if __name__ == "__main__":
    seed()
