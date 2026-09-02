"""
Student 4 - Order & Kitchen Management
Unit tests for AI-Mode.

summarise_queue() and heuristic_analysis() are deterministic, so they can be
tested without Ollama running. That also proves the fallback path works -
which is exactly what keeps the POS usable when the LLM container is down.
"""

from datetime import datetime, timedelta


def make_order(order_id, number, status, minutes_ago, items, channel="DINE_IN",
               now=None):
    now = now or datetime.now()
    placed = now - timedelta(minutes=minutes_ago)

    return {
        "id": order_id,
        "order_number": number,
        "status": status,
        "channel": channel,
        "table_number": "T1",
        "item_count": sum(i["quantity"] for i in items),
        "placed_at": placed.strftime("%Y-%m-%d %H:%M:%S"),
        "items": items,
    }


def latte(quantity=1):
    return {"menu_name": "Latte", "quantity": quantity,
            "station": "BAR", "prep_seconds": 90}


def sandwich(quantity=1):
    return {"menu_name": "Chicken Sandwich", "quantity": quantity,
            "station": "KITCHEN", "prep_seconds": 300}


# ---------------------------------------------------------------------

def test_empty_queue_reports_low_congestion(ai_module):
    metrics = ai_module.summarise_queue([])

    assert metrics["open_order_count"] == 0
    assert metrics["congestion_level"] == "LOW"
    assert metrics["tickets"] == []


def test_completed_orders_are_not_counted_as_open(ai_module):
    now = datetime.now()
    orders = [
        make_order(1, "A-1001", "COMPLETED", 30, [latte()], now=now),
        make_order(2, "A-1002", "PREPARING", 5, [latte()], now=now),
    ]

    metrics = ai_module.summarise_queue(orders, now=now)

    assert metrics["open_order_count"] == 1
    assert metrics["tickets"][0]["order_number"] == "A-1002"


def test_workload_is_split_across_stations(ai_module):
    now = datetime.now()
    orders = [
        make_order(1, "A-1001", "CONFIRMED", 2,
                   [latte(2), sandwich(1)], now=now),
    ]

    metrics = ai_module.summarise_queue(orders, now=now)

    assert metrics["station_load"]["BAR"]["queued_items"] == 2
    assert metrics["station_load"]["KITCHEN"]["queued_items"] == 1
    assert metrics["station_load"]["BAR"]["workload_minutes"] == 3.0
    assert metrics["station_load"]["KITCHEN"]["workload_minutes"] == 5.0
    assert metrics["busiest_station"] == "KITCHEN"


def test_orders_past_the_service_target_are_flagged_at_risk(ai_module):
    now = datetime.now()
    orders = [
        make_order(1, "A-1001", "PREPARING", 25, [latte()], now=now),
        make_order(2, "A-1002", "PENDING", 2, [latte()], now=now),
    ]

    metrics = ai_module.summarise_queue(orders, now=now)

    assert "A-1001" in metrics["at_risk_orders"]
    assert "A-1002" not in metrics["at_risk_orders"]
    assert metrics["congestion_level"] == "HIGH"


def test_older_tickets_are_prioritised_over_newer_ones(ai_module):
    now = datetime.now()
    orders = [
        make_order(1, "A-NEW", "PENDING", 1, [latte()], now=now),
        make_order(2, "A-OLD", "PENDING", 18, [latte()], now=now),
    ]

    metrics = ai_module.summarise_queue(orders, now=now)

    assert metrics["tickets"][0]["order_number"] == "A-OLD"


def test_a_quick_ticket_beats_a_slow_one_of_the_same_age(ai_module):
    now = datetime.now()
    orders = [
        make_order(1, "A-SLOW", "PENDING", 5, [sandwich(2)], now=now),
        make_order(2, "A-FAST", "PENDING", 5, [latte()], now=now),
    ]

    metrics = ai_module.summarise_queue(orders, now=now)

    assert metrics["tickets"][0]["order_number"] == "A-FAST"


# ---------------------------------------------------------------------
# Fallback analysis
# ---------------------------------------------------------------------

def test_heuristic_analysis_returns_every_section(ai_module):
    now = datetime.now()
    orders = [make_order(1, "A-1001", "PREPARING", 20, [sandwich(2)], now=now)]

    metrics = ai_module.summarise_queue(orders, now=now)
    analysis = ai_module.heuristic_analysis(metrics)

    assert analysis["congestion"]
    assert analysis["sequence"][0]["order_number"] == "A-1001"
    assert "A-1001" in analysis["delay_risk"]
    assert analysis["action"]


def test_analysis_falls_back_when_ollama_is_unreachable(ai_module):
    import requests

    class BrokenOllama:
        model = "llama3.2"

        def generate(self, prompt, system=None, temperature=0.2):
            raise requests.ConnectionError("ollama is down")

    now = datetime.now()
    orders = [make_order(1, "A-1001", "PENDING", 3, [latte(2)], now=now)]

    result = ai_module.analyse(orders, BrokenOllama(), now=now)

    assert result["mode"] == "heuristic"
    assert "Ollama unreachable" in result["note"]
    assert result["analysis"]["action"]
    assert result["metrics"]["open_order_count"] == 1


def test_analysis_uses_the_model_when_it_answers_in_format(ai_module):
    class FakeOllama:
        model = "qwen2.5"

        def generate(self, prompt, system=None, temperature=0.2):
            return (
                "CONGESTION: The bar is busy with two open tickets.\n"
                "SEQUENCE: A-1001 first because it has waited longest.\n"
                "DELAY RISK: none\n"
                "ACTION: Start the lattes now."
            )

    now = datetime.now()
    orders = [make_order(1, "A-1001", "PENDING", 3, [latte(2)], now=now)]

    result = ai_module.analyse(orders, FakeOllama(), now=now)

    assert result["mode"] == "ollama"
    assert result["model"] == "qwen2.5"
    assert "bar is busy" in result["analysis"]["congestion"].lower()
    assert result["analysis"]["action"] == "Start the lattes now."


def test_model_cannot_claim_no_delay_when_a_ticket_is_over_target(ai_module):
    """The measured facts override the model's narrative where they disagree."""

    class ContradictingOllama:
        model = "llama3.2"

        def generate(self, prompt, system=None, temperature=0.2):
            return (
                "CONGESTION: One ticket is over 12 minutes behind target.\n"
                "SEQUENCE: A-1013 first.\n"
                "DELAY RISK: none\n"
                "ACTION: Start it now."
            )

    now = datetime.now()
    orders = [make_order(1, "A-1013", "PENDING", 13, [latte(2)], now=now)]

    result = ai_module.analyse(orders, ContradictingOllama(), now=now)

    assert result["mode"] == "ollama"
    assert result["analysis"]["delay_risk"] != "none"
    assert "A-1013" in result["analysis"]["delay_risk"]
    assert result["corrections"]
    assert "A-1013" in result["corrections"][0]


def test_model_cannot_invent_a_delay_when_nothing_is_late(ai_module):
    class AlarmistOllama:
        model = "llama3.2"

        def generate(self, prompt, system=None, temperature=0.2):
            return (
                "CONGESTION: Quiet.\n"
                "SEQUENCE: A-2001 first.\n"
                "DELAY RISK: A-2001 will definitely be late.\n"
                "ACTION: Hurry."
            )

    now = datetime.now()
    orders = [make_order(1, "A-2001", "PENDING", 2, [latte()], now=now)]

    result = ai_module.analyse(orders, AlarmistOllama(), now=now)

    assert result["analysis"]["delay_risk"] == "none"
    assert result["corrections"]


def test_prompt_contains_the_queue_facts_and_no_raw_database_rows(ai_module):
    now = datetime.now()
    orders = [make_order(1, "A-1001", "PENDING", 3, [latte(2)], now=now)]

    metrics = ai_module.summarise_queue(orders, now=now)
    prompt = ai_module.build_prompt(metrics)

    assert "A-1001" in prompt
    assert "STATION LOAD" in prompt
    assert "CONGESTION:" in prompt
    # Context management: we never paste identifiers or SQL into the prompt.
    assert "SELECT" not in prompt.upper()
    assert "customer_id" not in prompt
