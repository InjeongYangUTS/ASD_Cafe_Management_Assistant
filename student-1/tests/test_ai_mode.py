"""Tests for AI-Mode. Deterministic only - the LLM path is demonstrated live, not asserted here."""

import ai
from services.prompt_loader import load_prompt, render, PromptNotFound

import pytest


# Sentiment measurement

def test_star_rating_anchors_the_sentiment():
    assert ai.measure_review({"rating": 5, "comment": "Great."})["sentiment"] == "POSITIVE"
    assert ai.measure_review({"rating": 3, "comment": "It was a cafe."})["sentiment"] == "NEUTRAL"
    assert ai.measure_review({"rating": 1, "comment": "Awful."})["sentiment"] == "NEGATIVE"


def test_wording_moves_the_score_within_the_rating():
    bare = ai.measure_review({"rating": 3, "comment": "It was fine."})
    angry = ai.measure_review({
        "rating": 3,
        "comment": "Slow, cold, wrong order and a dirty table.",
    })

    assert angry["sentiment_score"] < bare["sentiment_score"]


def test_score_stays_within_bounds():
    extreme = ai.measure_review({
        "rating": 1,
        "comment": "slow cold wrong rude dirty expensive bad worst terrible "
                   "disappointing late mistake ignored poor unacceptable",
    })
    assert -1.0 <= extreme["sentiment_score"] <= 1.0


# Issue and praise detection

def test_detects_the_complaint_themes():
    issues = ai.detect_issues("I waited 20 minutes and the table was dirty.")

    assert "slow_service" in issues
    assert "cleanliness" in issues


def test_detects_praise():
    praise = ai.detect_praise("The staff were friendly and the coffee delicious.")

    assert "staff_friendliness" in praise
    assert "food_quality" in praise


def test_allergen_handling_outranks_a_noisy_grinder():
    """Severity weighting: a health issue must not sit below an annoyance."""
    assert ai.issue_weight("allergen_handling") > ai.issue_weight("noise")


# Menu attribution

def test_specific_item_is_not_double_counted_as_the_generic_one(menu_vocabulary):
    """
    "vanilla latte" belongs to Vanilla Latte only. Without longest-alias
    masking every specialty coffee would also inflate the plain Latte, and
    the per-item ranking would be meaningless.
    """
    matched = ai.match_menu_items("The vanilla latte was cold.", menu_vocabulary)

    assert "Vanilla Latte" in matched
    assert "Latte" not in matched


def test_plain_item_still_matches(menu_vocabulary):
    assert "Latte" in ai.match_menu_items("my latte was cold", menu_vocabulary)


def test_customer_wording_matches_the_menu_name(menu_vocabulary):
    assert "Avocado Toast" in ai.match_menu_items("the avo toast", menu_vocabulary)


def test_unmentioned_items_are_not_matched(menu_vocabulary):
    assert ai.match_menu_items("The service was slow.", menu_vocabulary) == []


# Derived category

def test_category_comes_from_what_went_wrong(menu_vocabulary):
    assert ai.classify_category(
        "Waited 25 minutes for my coffee", menu_vocabulary) == "WAIT_TIME"
    assert ai.classify_category(
        "The table was dirty", menu_vocabulary) == "CLEANLINESS"
    assert ai.classify_category(
        "A latte is now $5.80, far too expensive", menu_vocabulary) == "PRICE"


def test_category_falls_back_to_the_menu_item_when_nothing_went_wrong(menu_vocabulary):
    assert ai.classify_category(
        "The flat white was perfect", menu_vocabulary) == "DRINK"


def test_category_defaults_to_general(menu_vocabulary):
    assert ai.classify_category("Nice spot.", menu_vocabulary) == "GENERAL"


# Store-wide measurement

REVIEWS = [
    {"id": 1, "rating": 5, "title": "", "comment": "The flat white was perfect.",
     "category": "DRINK", "submitted_at": "2026-09-01 09:00:00"},
    {"id": 2, "rating": 2, "title": "", "comment": "Waited 25 minutes for a latte.",
     "category": "WAIT_TIME", "submitted_at": "2026-09-01 10:00:00"},
    {"id": 3, "rating": 1, "title": "", "comment": "My latte was cold and the table was dirty.",
     "category": "CLEANLINESS", "submitted_at": "2026-09-01 11:00:00"},
]


def test_menu_breakdown_separates_praise_from_complaint(menu_vocabulary):
    metrics = ai.measure_store(REVIEWS, menu_vocabulary=menu_vocabulary)
    by_item = {row["menu_item"]: row for row in metrics["menu_feedback"]}

    assert by_item["Flat White"]["verdict"] == "PRAISED"
    assert by_item["Latte"]["verdict"] == "COMPLAINED_ABOUT"
    assert by_item["Latte"]["reviews"] == 2


def test_single_review_items_are_marked_low_confidence(menu_vocabulary):
    metrics = ai.measure_store(REVIEWS, menu_vocabulary=menu_vocabulary)
    by_item = {row["menu_item"]: row for row in metrics["menu_feedback"]}

    assert by_item["Flat White"]["confidence"] == "low"
    assert by_item["Latte"]["confidence"] == "normal"


def test_issue_priority_is_ranked(menu_vocabulary):
    metrics = ai.measure_store(REVIEWS, menu_vocabulary=menu_vocabulary)
    scores = [row["priority_score"] for row in metrics["top_issues"]]

    assert scores == sorted(scores, reverse=True)


def test_empty_review_set_does_not_crash(menu_vocabulary):
    metrics = ai.measure_store([], menu_vocabulary=menu_vocabulary)

    assert metrics["review_count"] == 0
    assert metrics["menu_feedback"] == []


# Question routing and the rule-based answer

def test_a_question_about_one_item_is_answered_about_that_item_only(menu_vocabulary):
    metrics = ai.measure_store(REVIEWS, menu_vocabulary=menu_vocabulary)
    answer = ai.heuristic_answer(
        "How do customers think about latte?", metrics, menu_vocabulary
    )

    assert "Latte" in answer
    assert "Flat White" not in answer


def test_a_question_about_an_unreviewed_item_says_so(menu_vocabulary):
    metrics = ai.measure_store(REVIEWS, menu_vocabulary=menu_vocabulary)
    answer = ai.heuristic_answer(
        "How is the chocolate cake doing?", metrics, menu_vocabulary
    )

    assert "Chocolate Cake" in answer
    assert "nothing to report" in answer


def test_a_general_question_gets_the_ranked_priority(menu_vocabulary):
    metrics = ai.measure_store(REVIEWS, menu_vocabulary=menu_vocabulary)
    answer = ai.heuristic_answer("What should we fix first?", metrics,
                                 menu_vocabulary)

    assert "Fix" in answer


# Prompt files

def test_every_service_prompt_loads():
    for name in ("ask_system_prompt.txt", "ask_task_prompt.txt",
                 "sentiment_system_prompt.txt", "sentiment_task_prompt.txt"):
        assert load_prompt("service/%s" % name)


def test_every_agentic_prompt_loads():
    for name in ("implementation_system_prompt.txt",
                 "implementation_task_prompt.txt",
                 "review_system_prompt.txt", "review_task_prompt.txt"):
        assert load_prompt("agentic/%s" % name)


def test_question_prompt_carries_the_question_and_the_evidence(menu_vocabulary):
    metrics = ai.measure_store(REVIEWS, menu_vocabulary=menu_vocabulary)
    prompt = ai.build_question_prompt(
        "How do customers think about latte?", metrics, menu_vocabulary
    )

    assert "How do customers think about latte?" in prompt
    assert "Latte" in prompt
    assert "{{" not in prompt, "a placeholder was left unfilled"


def test_an_unfilled_placeholder_is_an_error():
    """
    A placeholder that reaches the model is read as an instruction. It has
    to fail loudly rather than be sent as literal text.
    """
    with pytest.raises(PromptNotFound):
        render("Question: {{STAFF_QUESTION}} Evidence: {{REVIEW_SUMMARY}}",
               staff_question="only one of the two")


# Time display

def test_stored_utc_is_shown_in_sydney_time():
    """
    Timestamps are stored in UTC and shown in the cafe's own timezone.

    A review posted at 8am at the counter must read as 8am on the staff
    board, not as 10pm the previous day. Getting this wrong makes the
    morning-rush complaints impossible to find.
    """
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "frontend"))
    from app import cafe_time

    # 2026-09-03 02:05 UTC is 12:05pm in Sydney (AEST, UTC+10).
    assert cafe_time("2026-09-03 02:05:33") == "3 Sep 2026, 12:05 pm"

    # 2026-01-15 02:05 UTC is 1:05pm in Sydney (AEDT, UTC+11).
    assert cafe_time("2026-01-15 02:05:00") == "15 Jan 2026, 1:05 pm"

    # Midnight must read 12:00 am, not 0:00 am.
    assert cafe_time("2026-09-02 14:00:00") == "3 Sep 2026, 12:00 am"


def test_unparseable_timestamp_is_shown_as_stored():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "frontend"))
    from app import cafe_time

    assert cafe_time("") == ""
    assert cafe_time("not a date") == "not a date"
