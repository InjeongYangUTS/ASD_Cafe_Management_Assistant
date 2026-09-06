import json
import os
from datetime import datetime
from pathlib import Path

import requests


# =========================================================
# CONFIG
# =========================================================

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8300").rstrip("/")
OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434/api/generate"
)
MODEL_NAME = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5:0.5b"
)

LOG_DIRECTORY = Path(
    os.getenv(
        "LOG_DIRECTORY",
        Path(__file__).resolve().parent.parent / "logs"
    )
)


# =========================================================
# OLLAMA
# =========================================================

def ask_ollama(prompt):
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
            },
            timeout=90,
        )

        response.raise_for_status()

        data = response.json()
        return data["response"].strip()

    except (requests.RequestException, KeyError, ValueError) as exc:
        raise RuntimeError(
            f"AI service unavailable: {exc}"
        ) from exc


# =========================================================
# INVENTORY NORMALISATION
# =========================================================

def normalise_inventory(items):
    """
    Convert backend inventory data into authoritative
    deterministic inventory facts.
    """

    normalised = []

    for item in items:
        quantity = float(item["quantity"])
        minimum_stock = float(item["minimum_stock"])
        shortage = max(minimum_stock - quantity, 0)

        if quantity == 0:
            status = "OUT OF STOCK"
        elif quantity <= minimum_stock:
            status = "LOW"
        else:
            status = "IN STOCK"

        normalised.append({
            "id": item["id"],
            "name": item["name"],
            "quantity": quantity,
            "minimum_stock": minimum_stock,
            "shortage": shortage,
            "unit": item["unit"],
            "status": status,
        })

    return normalised


# =========================================================
# PLAN
# =========================================================

def plan():
    """
    PLAN uses the LLM only to describe the decision process.
    """

    prompt = """
You are an AI inventory management agent for a cafe.

Create a short plan for deciding which inventory items
should be restocked first.

Use these fixed rules:

1. OUT OF STOCK items must be considered before LOW items.
2. Within the same status group, larger shortages receive
   higher priority.
3. Inventory quantities, stock statuses, and shortages are
   calculated by the system and must not be changed.
4. The final decision must use only the supplied inventory data.

Do not list actual inventory items.
Do not calculate any values.
Return a concise 3-4 step plan.
"""

    return ask_ollama(prompt)


# =========================================================
# ACT
# =========================================================

def act(items):
    """
    ACT is deterministic.
    Python creates the authoritative priority list.
    """

    priority_items = [
        item
        for item in items
        if item["status"] in ("OUT OF STOCK", "LOW")
    ]

    def priority_key(item):
        if item["status"] == "OUT OF STOCK":
            status_priority = 0
        else:
            status_priority = 1

        return (
            status_priority,
            -item["shortage"]
        )

    priority_items.sort(key=priority_key)

    return priority_items


# =========================================================
# FORMAT ACT RESULT
# =========================================================

def format_act_result(priority_items):
    lines = []

    for index, item in enumerate(priority_items, start=1):
        lines.append(
            f"{index}. {item['name']} "
            f"- Status: {item['status']} "
            f"- Current: {item['quantity']:g} {item['unit']} "
            f"- Minimum: {item['minimum_stock']:g} {item['unit']} "
            f"- Shortage: {item['shortage']:g} {item['unit']}"
        )

    return "\n".join(lines)


# =========================================================
# OBSERVE
# =========================================================

def observe(priority_items):
    """
    OBSERVE verifies the deterministic ACT result.
    """

    problems = []

    out_of_stock_count = 0
    low_stock_count = 0

    seen_low = False

    for item in priority_items:
        quantity = item["quantity"]
        minimum_stock = item["minimum_stock"]
        status = item["status"]

        expected_shortage = max(
            minimum_stock - quantity,
            0
        )

        # Check status
        if quantity == 0:
            expected_status = "OUT OF STOCK"
        elif quantity <= minimum_stock:
            expected_status = "LOW"
        else:
            expected_status = "IN STOCK"

        if status != expected_status:
            problems.append(
                f"{item['name']} has incorrect status."
            )

        # Check shortage
        if item["shortage"] != expected_shortage:
            problems.append(
                f"{item['name']} has incorrect shortage."
            )

        # Count groups
        if status == "OUT OF STOCK":
            out_of_stock_count += 1

            if seen_low:
                problems.append(
                    "An OUT OF STOCK item appears after a LOW item."
                )

        elif status == "LOW":
            low_stock_count += 1
            seen_low = True

    if problems:
        summary = (
            f"{len(problems)} problem(s) detected.\n"
            + "\n".join(
                f"- {problem}"
                for problem in problems
            )
        )
    else:
        summary = (
            "All inventory facts and priorities were verified.\n"
            f"OUT OF STOCK items: {out_of_stock_count}\n"
            f"LOW items: {low_stock_count}\n"
            "No status, shortage, or priority inconsistencies detected."
        )

    return summary, problems


# =========================================================
# ADAPT
# =========================================================

def adapt(priority_items, observation):
    """
    ADAPT uses only verified facts.
    The LLM explains the final recommendation but cannot
    change the authoritative data.
    """

    facts = format_act_result(priority_items)

    prompt = f"""
You are an AI inventory management assistant for a cafe.

The following inventory priority list was calculated and
verified by the system.

AUTHORITATIVE PRIORITY LIST:
{facts}

OBSERVATION:
{observation}

Write a concise final restocking recommendation.

Rules:

1. Keep the exact item order shown above.
2. Keep every supplied status unchanged.
3. Keep every supplied shortage unchanged.
4. Do not invent quantities or stock values.
5. Do not reorder items.
6. OUT OF STOCK items should be described as the most urgent.
7. LOW items should be described as the next priority group.

Return a short numbered recommendation.
"""

    return ask_ollama(prompt)


# =========================================================
# SAVE LOG
# =========================================================

def save_log(result):
    LOG_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    path = (
        LOG_DIRECTORY
        / f"inventory_agent_{timestamp}.json"
    )

    path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=4
        ),
        encoding="utf-8"
    )

    return path


# =========================================================
# MAIN AGENTIC WORKFLOW
# =========================================================

def run_agentic_workflow(items):
    inventory = normalise_inventory(items)

    print()
    print("=" * 60)
    print("INVENTORY AGENTIC AI WORKFLOW")
    print("PLAN -> ACT -> OBSERVE -> ADAPT")
    print("=" * 60)

    # -----------------------------------------------------
    # PLAN
    # -----------------------------------------------------

    print()
    print("PLAN")
    print("-" * 60)

    plan_result = plan()
    print(plan_result)

    # -----------------------------------------------------
    # ACT
    # -----------------------------------------------------

    print()
    print("ACT")
    print("-" * 60)

    act_result = act(inventory)
    act_text = format_act_result(act_result)

    print(act_text)

    # -----------------------------------------------------
    # OBSERVE
    # -----------------------------------------------------

    print()
    print("OBSERVE")
    print("-" * 60)

    observe_result, problems = observe(
        act_result
    )

    print(observe_result)

    # -----------------------------------------------------
    # ADAPT
    # -----------------------------------------------------

    print()
    print("ADAPT")
    print("-" * 60)

    if problems:
        adapt_result = (
            "The workflow detected inventory validation "
            "problems. Final AI recommendation was not generated."
        )
    else:
        adapt_result = adapt(
            act_result,
            observe_result
        )

    print(adapt_result)

    # -----------------------------------------------------
    # FINAL RESULT
    # -----------------------------------------------------

    result = {
        "timestamp": datetime.now().isoformat(),
        "model": MODEL_NAME,
        "plan": plan_result,
        "act": act_result,
        "observe": observe_result,
        "problems": problems,
        "adapt": adapt_result,
    }

    log_path = save_log(result)

    print()
    print("=" * 60)
    print("FINAL RESULT")
    print("=" * 60)
    print(adapt_result)

    print()
    print(
        f"Workflow log saved to: {log_path}"
    )

    return result


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    print(
        f"Loading inventory data from "
        f"{BACKEND_URL}/api/dashboard"
    )

    try:
        response = requests.get(
            BACKEND_URL + "/api/dashboard",
            timeout=10
        )

        response.raise_for_status()

    except requests.RequestException as exc:
        raise RuntimeError(
            f"Student 3 backend unavailable: {exc}"
        ) from exc

    data = response.json()

    items = data.get(
        "low_stock_items",
        []
    )

    if not items:
        print(
            "No low-stock or out-of-stock "
            "inventory items were found."
        )
        raise SystemExit(0)

    print(
        f"Loaded {len(items)} "
        f"low-stock or out-of-stock item(s)."
    )

    run_agentic_workflow(items)