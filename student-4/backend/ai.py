"""
Student 4 (Stella Kwon) - Order & Kitchen Management
AI-Mode : kitchen congestion and preparation-priority analysis.

Request path (as required by the Release 0 brief):

    Frontend -> Backend/API -> Ollama -> LLM (Llama / Qwen) -> Backend -> Frontend

The backend, not the frontend, builds the prompt. That keeps the model
name, the system prompt and the amount of context we send in one place,
and stops order data leaking into the browser.

Two layers:
  1. summarise_queue()  - deterministic metrics computed from the live queue.
     These numbers are what we put into the prompt (context management: we
     send a compact summary, not every row in the database).
  2. analyse()          - asks the LLM for the reasoning on top of those
     metrics; falls back to a deterministic rule-based analysis with the
     same output shape when Ollama is unreachable, so the POS never breaks.
"""

from datetime import datetime

import requests

# How many tickets each station can genuinely work on at once.
STATION_CAPACITY = {"BAR": 1, "KITCHEN": 1, "PASTRY": 1}

# A ticket older than this is treated as at risk of being late.
SLA_MINUTES = 12

OPEN_STATUSES = ("PENDING", "CONFIRMED", "PREPARING")

SYSTEM_PROMPT = (
    "You are the kitchen operations assistant for a small Australian cafe. "
    "You receive a factual summary of the live order queue and reply with "
    "short, practical guidance for the staff on the pass. "
    "Be concrete, never invent orders that are not in the summary, and keep "
    "the whole reply under 180 words."
)


def _parse_time(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(value)[:19], fmt)
        except ValueError:
            continue
    return None


def age_minutes(order, now):
    placed = _parse_time(order.get("placed_at"))
    if placed is None:
        return 0.0
    return max(0.0, (now - placed).total_seconds() / 60.0)


def summarise_queue(orders, now=None):
    """Deterministic metrics for the open queue. This is the AI's context."""
    now = now or datetime.now()

    open_orders = [o for o in orders if o.get("status") in OPEN_STATUSES]

    station_seconds = {"BAR": 0, "KITCHEN": 0, "PASTRY": 0}
    station_items = {"BAR": 0, "KITCHEN": 0, "PASTRY": 0}

    ticket_rows = []

    for order in open_orders:
        items = order.get("items") or []
        prep_seconds = 0
        complexity = 0

        for item in items:
            station = item.get("station", "BAR")
            quantity = int(item.get("quantity", 1))
            seconds = int(item.get("prep_seconds", 60)) * quantity

            if station not in station_seconds:
                station = "BAR"

            station_seconds[station] += seconds
            station_items[station] += quantity
            prep_seconds += seconds
            # Complexity: distinct lines weigh more than repeats of one drink.
            complexity += 1 + (quantity - 1) * 0.3

        age = age_minutes(order, now)
        prep_minutes = round(prep_seconds / 60.0, 1)

        # Priority score:
        #   + age          keeps the queue fair (nobody waits forever)
        #   - prep time    clears quick tickets so the board drains faster
        #   + takeaway     that customer is standing at the counter
        score = (age * 1.2) - (prep_minutes * 0.6)
        if order.get("channel") == "TAKEAWAY":
            score += 2.0
        if order.get("status") == "PREPARING":
            score += 1.5

        ticket_rows.append({
            "id": order.get("id"),
            "order_number": order.get("order_number"),
            "status": order.get("status"),
            "channel": order.get("channel"),
            "table_number": order.get("table_number"),
            "age_minutes": round(age, 1),
            "prep_minutes": prep_minutes,
            "item_count": order.get("item_count", len(items)),
            "complexity": round(complexity, 1),
            "priority_score": round(score, 2),
            "at_risk": age >= SLA_MINUTES,
            "items": [
                "%dx %s" % (int(i.get("quantity", 1)), i.get("menu_name", "?"))
                for i in items
            ],
        })

    ticket_rows.sort(key=lambda row: row["priority_score"], reverse=True)

    station_load = {}
    for station, seconds in station_seconds.items():
        capacity = STATION_CAPACITY.get(station, 1)
        station_load[station] = {
            "queued_items": station_items[station],
            "workload_minutes": round(seconds / 60.0 / capacity, 1),
        }

    busiest = max(station_load, key=lambda s: station_load[s]["workload_minutes"])
    total_minutes = round(
        sum(load["workload_minutes"] for load in station_load.values()), 1
    )
    longest_wait = max([row["age_minutes"] for row in ticket_rows], default=0.0)

    if total_minutes >= 25 or longest_wait >= 20:
        congestion = "HIGH"
    elif total_minutes >= 12 or longest_wait >= SLA_MINUTES:
        congestion = "MODERATE"
    else:
        congestion = "LOW"

    return {
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "open_order_count": len(open_orders),
        "total_workload_minutes": total_minutes,
        "longest_wait_minutes": round(longest_wait, 1),
        "busiest_station": busiest,
        "congestion_level": congestion,
        "station_load": station_load,
        "tickets": ticket_rows,
        "at_risk_orders": [r["order_number"] for r in ticket_rows if r["at_risk"]],
    }


def build_prompt(metrics):
    """Compact, factual context for the LLM - not the whole database."""
    lines = [
        "LIVE KITCHEN QUEUE SUMMARY (%s)" % metrics["generated_at"],
        "",
        "Open orders: %d" % metrics["open_order_count"],
        "Total workload: %.1f minutes" % metrics["total_workload_minutes"],
        "Longest ticket wait: %.1f minutes (service target %d minutes)"
        % (metrics["longest_wait_minutes"], SLA_MINUTES),
        "Measured congestion: %s" % metrics["congestion_level"],
        "",
        "STATION LOAD",
    ]

    for station, load in metrics["station_load"].items():
        lines.append(
            "  %-8s %2d items, %.1f minutes of work"
            % (station, load["queued_items"], load["workload_minutes"])
        )

    lines += ["", "OPEN TICKETS (already sorted by our priority score)"]

    for row in metrics["tickets"][:12]:
        lines.append(
            "  %s | %s | %s | waiting %.1f min | prep %.1f min | %s%s"
            % (
                row["order_number"],
                row["status"],
                row["channel"],
                row["age_minutes"],
                row["prep_minutes"],
                ", ".join(row["items"][:4]) or "no items",
                "  <-- OVER TARGET" if row["at_risk"] else "",
            )
        )

    lines += [
        "",
        "Using only the data above, reply with exactly these four sections:",
        "CONGESTION: one sentence on how busy the kitchen is and why.",
        "SEQUENCE: the order numbers to prepare next, best first, with a "
        "short reason for each (maximum 5).",
        "DELAY RISK: which tickets may be late and what is causing it. "
        "Write 'none' if there are none.",
        "ACTION: one instruction for the staff right now.",
    ]

    return "\n".join(lines)


def heuristic_analysis(metrics):
    """Deterministic fallback with the same shape as the LLM answer."""
    tickets = metrics["tickets"]

    if not tickets:
        return {
            "congestion": "The queue is empty - no open orders.",
            "sequence": [],
            "delay_risk": "none",
            "action": "Restock the pass and prep milk while it is quiet.",
        }

    busiest = metrics["busiest_station"]
    busiest_load = metrics["station_load"][busiest]

    congestion = (
        "Congestion is %s: %d open orders and %.1f minutes of work, "
        "concentrated on the %s station (%.1f minutes)."
        % (
            metrics["congestion_level"].lower(),
            metrics["open_order_count"],
            metrics["total_workload_minutes"],
            busiest,
            busiest_load["workload_minutes"],
        )
    )

    sequence = []
    for row in tickets[:5]:
        reasons = []
        if row["at_risk"]:
            reasons.append("waiting %.0f min, over the %d min target"
                           % (row["age_minutes"], SLA_MINUTES))
        if row["prep_minutes"] <= 2:
            reasons.append("quick ticket, clears the board")
        if row["channel"] == "TAKEAWAY":
            reasons.append("takeaway customer waiting at the counter")
        if row["status"] == "PREPARING":
            reasons.append("already started")
        if not reasons:
            reasons.append("next in queue order")

        sequence.append({
            "order_number": row["order_number"],
            "reason": "; ".join(reasons),
        })

    at_risk = [row for row in tickets if row["at_risk"]]
    if at_risk:
        delay_risk = "; ".join(
            "%s has waited %.0f min (%.1f min of prep still to do)"
            % (row["order_number"], row["age_minutes"], row["prep_minutes"])
            for row in at_risk[:4]
        )
    else:
        delay_risk = "none"

    if metrics["congestion_level"] == "HIGH":
        action = ("Move a second hand onto %s and hold new dine-in tickets "
                  "for a few minutes." % busiest)
    elif at_risk:
        action = "Push %s out next before starting anything new." % \
                 at_risk[0]["order_number"]
    else:
        action = "Keep working the sequence above in order."

    return {
        "congestion": congestion,
        "sequence": sequence,
        "delay_risk": delay_risk,
        "action": action,
    }


def parse_llm_reply(text):
    """Split the four labelled sections out of the model's reply."""
    sections = {"congestion": "", "sequence": "", "delay_risk": "", "action": ""}
    current = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        upper = line.upper()
        if upper.startswith("CONGESTION"):
            current = "congestion"
            line = line.split(":", 1)[-1].strip()
        elif upper.startswith("SEQUENCE"):
            current = "sequence"
            line = line.split(":", 1)[-1].strip()
        elif upper.startswith("DELAY"):
            current = "delay_risk"
            line = line.split(":", 1)[-1].strip()
        elif upper.startswith("ACTION"):
            current = "action"
            line = line.split(":", 1)[-1].strip()

        if current and line:
            sections[current] = (sections[current] + " " + line).strip()

    return sections


def analyse(orders, ollama, now=None):
    """
    Full AI-Mode analysis.

    Always returns the deterministic metrics. 'mode' says whether the
    narrative came from the LLM or from the fallback rules, so the screen
    and the marker can both see which path ran.
    """
    metrics = summarise_queue(orders, now=now)
    prompt = build_prompt(metrics)
    fallback = heuristic_analysis(metrics)

    result = {
        "metrics": metrics,
        "prompt": prompt,
        "mode": "heuristic",
        "model": ollama.model,
        "analysis": fallback,
        "raw_response": None,
        "note": None,
    }

    if not metrics["tickets"]:
        result["note"] = "No open orders - AI analysis skipped."
        return result

    try:
        raw = ollama.generate(prompt, system=SYSTEM_PROMPT)
    except (requests.RequestException, ValueError) as exc:
        result["note"] = ("Ollama unreachable (%s) - showing rule-based "
                          "analysis instead." % type(exc).__name__)
        return result

    if not raw:
        result["note"] = "Ollama returned an empty response - using rule-based analysis."
        return result

    parsed = parse_llm_reply(raw)

    if not parsed["congestion"] and not parsed["sequence"]:
        result["raw_response"] = raw
        result["note"] = ("Model reply did not follow the requested format - "
                          "showing rule-based analysis, raw reply kept below.")
        return result

    result["mode"] = "ollama"
    result["raw_response"] = raw
    result["analysis"] = {
        "congestion": parsed["congestion"] or fallback["congestion"],
        "sequence_text": parsed["sequence"],
        "sequence": fallback["sequence"],
        "delay_risk": parsed["delay_risk"] or fallback["delay_risk"],
        "action": parsed["action"] or fallback["action"],
    }

    return result
