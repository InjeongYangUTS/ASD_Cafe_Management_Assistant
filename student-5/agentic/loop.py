import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
PROMPT_FILE = BASE_DIR / "prompts" / "payment_operations_review.md"
LOG_DIR = BASE_DIR / "agentic" / "logs"

BACKEND_URL = os.getenv(
    "STUDENT5_BACKEND_URL",
    "http://localhost:8500"
).rstrip("/")

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434/api/generate"
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_REVIEW_MODEL",
    "qwen2.5:0.5b"
)

def get_json(url):
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def ask_ollama(prompt):
    payload = json.dumps(
        {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=120) as response:
        result = json.loads(response.read().decode("utf-8"))

    return result.get("response", "").strip()

def plan():
    return {
        "goal": (
            "Review anonymised Payment and Billing statistics "
            "and identify one area for staff attention."
        ),
        "privacy_rule": (
            "Do not send customer IDs, order IDs, payment IDs "
            "or other transaction-level records to the LLM."
        ),
        "safety_rule": (
            "The AI may provide a recommendation but cannot "
            "approve payments, calculate refunds or modify records."
        )
    }

def act():
    payments = get_json(f"{BACKEND_URL}/api/payments")
    refunds = get_json(f"{BACKEND_URL}/api/refunds")

    completed_payments = [
        payment for payment in payments
        if payment.get("payment_status") in {
            "completed",
            "partially_refunded",
            "refunded"
        }
    ]

    partially_refunded = [
        payment for payment in payments
        if payment.get("payment_status") == "partially_refunded"
    ]

    fully_refunded = [
        payment for payment in payments
        if payment.get("payment_status") == "refunded"
    ]

    completed_refunds = [
        refund for refund in refunds
        if refund.get("refund_status") == "completed"
    ]

    total_paid = sum(
        float(payment.get("amount", 0))
        for payment in completed_payments
    )

    total_refunded = sum(
        float(refund.get("refund_amount", 0))
        for refund in completed_refunds
    )

    return {
        "completed_payments": len(completed_payments),
        "partially_refunded_payments": len(partially_refunded),
        "fully_refunded_payments": len(fully_refunded),
        "completed_refunds": len(completed_refunds),
        "total_paid": round(total_paid, 2),
        "total_refunded": round(total_refunded, 2)
    }

def observe(statistics):
    problems = []

    for name, value in statistics.items():
        if not isinstance(value, (int, float)):
            problems.append(f"{name} is not numeric")

        if isinstance(value, (int, float)) and value < 0:
            problems.append(f"{name} cannot be negative")

    if statistics["total_refunded"] > statistics["total_paid"]:
        problems.append("Total refunded exceeds total paid")

    return {
        "valid": len(problems) == 0,
        "problems": problems,
        "privacy_check": (
            "Only anonymous counts and aggregate totals were collected."
        )
    }


def build_prompt(statistics):
    template = PROMPT_FILE.read_text(encoding="utf-8")

    safe_statistics = (
        f"Completed payments: {statistics['completed_payments']}\n"
        f"Partially refunded payments: "
        f"{statistics['partially_refunded_payments']}\n"
        f"Fully refunded payments: "
        f"{statistics['fully_refunded_payments']}\n"
        f"Completed refunds: {statistics['completed_refunds']}\n"
        f"Total paid: ${statistics['total_paid']:.2f}\n"
        f"Total refunded: ${statistics['total_refunded']:.2f}"
    )

    return template.replace(
        "{payment_statistics}",
        safe_statistics
    )

def save_log(result):
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d-%H%M%S")

    json_path = LOG_DIR / f"loop-{timestamp}.json"
    markdown_path = LOG_DIR / f"loop-{timestamp}.md"

    json_path.write_text(
        json.dumps(result, indent=2),
        encoding="utf-8"
    )

    markdown = (
        "# Student 5 Agentic Loop\n\n"
        "## Plan\n\n"
        f"{result['plan']['goal']}\n\n"
        f"Privacy rule: {result['plan']['privacy_rule']}\n\n"
        f"Safety rule: {result['plan']['safety_rule']}\n\n"
        "## Act\n\n"
        f"{json.dumps(result['act'], indent=2)}\n\n"
        "## Observe\n\n"
        f"{json.dumps(result['observe'], indent=2)}\n\n"
        "## Adapt\n\n"
        f"{result['adapt']}\n\n"
        "## Model\n\n"
        f"{result['model']}\n"
    )

    markdown_path.write_text(
        markdown,
        encoding="utf-8"
    )

    return json_path, markdown_path

def main():
    print("=" * 55)
    print("STUDENT 5 - PAYMENT AND BILLING MANAGEMENT")
    print("PLAN -> ACT -> OBSERVE -> ADAPT")
    print("=" * 55)

    plan_result = plan()

    print("\nPLAN")
    print(plan_result["goal"])

    try:
        statistics = act()
    except Exception as error:
        print("\nACT FAILED")
        print(f"Could not read Student 5 data: {error}")
        return

    print("\nACT")
    print(json.dumps(statistics, indent=2))

    observation = observe(statistics)

    print("\nOBSERVE")
    print(json.dumps(observation, indent=2))

    if observation["valid"]:
        try:
            prompt = build_prompt(statistics)
            recommendation = ask_ollama(prompt)
        except Exception as error:
            recommendation = (
                "Ollama recommendation could not be generated: "
                f"{error}"
            )
    else:
        recommendation = (
            "The statistics failed validation, so no information "
            "was sent to Ollama."
        )

    print("\nADAPT")
    print(recommendation)

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "plan": plan_result,
        "act": statistics,
        "observe": observation,
        "adapt": recommendation,
        "model": OLLAMA_MODEL
    }

    json_log, markdown_log = save_log(result)

    print("\nLOGS SAVED")
    print(json_log)
    print(markdown_log)


if __name__ == "__main__":
    main()