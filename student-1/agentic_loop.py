import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(BASE_DIR / "backend"))

from services.llm_client import LLMClient, OLLAMA_MODEL, OLLAMA_REVIEW_MODEL  # noqa: E402
from services.prompt_loader import load_and_render                            # noqa: E402

load_dotenv(dotenv_path=BASE_DIR / ".env")

DB_URL = os.getenv("DB_SERVICE_URL", "http://127.0.0.1:7100").rstrip("/")
API_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8100").rstrip("/")
WEB_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:5110").rstrip("/")

LOG_DIR = BASE_DIR / "agentic" / "logs"

MIN_FEEDBACK_ROWS = 10
MIN_LOG_ROWS = 10

NFR_SAMPLES = 20
NFR_BUDGET_SECONDS = 0.500
NFR_ALLOWED_FAILURES = 1


PLAN = {
    "goal": (
        "Validate the Customer Feedback & Reviews microservices "
        "(student-1) using a local multi-agent workflow"
    ),
    "pass_condition": (
        "Both tables hold 10 or more records, every endpoint answers, and "
        "the read NFR holds"
    ),
    "nfr": "GET /api/feedback returns within 500 ms for 19 of 20 requests",
    "ai_condition": (
        "AI-Mode answers a staff question through Ollama and the approved "
        "open-source LLM"
    ),
    "db_plan": [
        "customer_feedback holds at least 10 records with valid ratings",
        "store_logs holds at least 10 audit records",
        "the audit trail contains a DELETED entry whose review no longer "
        "exists, proving store_logs has no delete cascade",
    ],
    "endpoints_plan": [
        "GET  /api/health        - service and dependency status",
        "GET  /api/feedback      - list reviews",
        "GET  /api/summary       - store-wide figures for other services",
        "POST /api/ai/ask        - AI-Mode answer to a staff question",
        "GET  /review            - customer screen",
        "GET  /reviews           - staff screen",
    ],
    "stop_condition": (
        "Database, endpoints, AI-Mode, agentic loop and evidence log are "
        "complete"
    ),
}


def validate_feedback_row(row):
    """One review, checked against the rules the schema promises."""
    if not isinstance(row.get("id"), int):
        return False, "id must be an integer"

    if not isinstance(row.get("customer_id"), int):
        return False, "customer_id must be an integer"

    rating = row.get("rating")
    if not isinstance(rating, int) or not 1 <= rating <= 5:
        return False, "rating must be a whole number from 1 to 5 (id %s)" % row.get("id")

    if not str(row.get("comment") or "").strip():
        return False, "comment is required (id %s)" % row.get("id")

    if row.get("sentiment") and row["sentiment"] not in (
            "POSITIVE", "NEUTRAL", "NEGATIVE"):
        return False, "unknown sentiment %r (id %s)" % (row["sentiment"], row["id"])

    if row.get("analysed_at") and not row.get("ai_model"):
        return False, "analysed review %s has no ai_model recorded" % row["id"]

    return True, "ok"


def observe_database():
    """Deterministic data-quality checks through the database API."""
    try:
        stats = requests.get(DB_URL + "/db/stats", timeout=5).json()
        feedback = requests.get(
            DB_URL + "/db/feedback", params={"limit": 500}, timeout=5
        ).json()["feedback"]
        logs = requests.get(
            DB_URL + "/db/logs", params={"limit": 500}, timeout=5
        ).json()["logs"]
    except (requests.RequestException, ValueError, KeyError) as exc:
        return False, "Database API unreachable (%s)" % exc

    counts = stats["row_counts"]

    if counts["customer_feedback"] < MIN_FEEDBACK_ROWS:
        return False, ("customer_feedback holds %d records, Release 0 "
                       "requires %d" % (counts["customer_feedback"],
                                        MIN_FEEDBACK_ROWS))

    if counts["store_logs"] < MIN_LOG_ROWS:
        return False, ("store_logs holds %d records, Release 0 requires %d"
                       % (counts["store_logs"], MIN_LOG_ROWS))

    for row in feedback:
        ok, message = validate_feedback_row(row)
        if not ok:
            return False, message

    live_ids = {row["id"] for row in feedback}
    orphan_deletes = [
        entry for entry in logs
        if entry["action"] == "DELETED" and entry["feedback_id"] not in live_ids
    ]

    if not orphan_deletes:
        return False, ("no DELETED audit entry survives without its review; "
                       "the store_logs no-cascade design is unverified")

    return True, (
        "Data validation passed: %d reviews, %d audit records, average "
        "rating %.2f, %d review(s) awaiting AI analysis, %d surviving "
        "DELETED audit entr%s"
        % (counts["customer_feedback"], counts["store_logs"],
           stats["average_rating"], stats["unanalysed_count"],
           len(orphan_deletes), "y" if len(orphan_deletes) == 1 else "ies")
    )


def observe_live_endpoints():
    results = []

    def check(label, method, url, **kwargs):
        try:
            response = requests.request(method, url, timeout=10, **kwargs)
            content_ok = bool(response.text and response.text.strip())
            line = ("%s -> HTTP %d, content_ok=%s"
                    % (label, response.status_code, content_ok))
        except Exception as exc:                       # noqa: BLE001
            line = "%s -> error: %s" % (label, exc)

        print("  Checked %s" % line)
        results.append(line)
        return line

    check("GET /api/health", "GET", API_URL + "/api/health")
    check("GET /api/feedback", "GET", API_URL + "/api/feedback?limit=5")
    check("GET /api/summary", "GET", API_URL + "/api/summary")
    check("GET /api/logs", "GET", API_URL + "/api/logs?limit=5")
    check("GET /review (customer screen)", "GET", WEB_URL + "/review")
    check("GET /reviews (staff screen)", "GET", WEB_URL + "/reviews")

    return results


def observe_nfr():
    """Course NFR check: 19 of 20 backend reads within 500 ms."""
    durations = []

    for _ in range(NFR_SAMPLES):
        start = time.perf_counter()
        try:
            requests.get(API_URL + "/api/feedback?limit=20", timeout=5)
        except requests.RequestException:
            durations.append(float("inf"))
            continue
        durations.append(time.perf_counter() - start)

    over_budget = [d for d in durations if d > NFR_BUDGET_SECONDS]
    finite = [d for d in durations if d != float("inf")]
    slowest = max(finite) if finite else float("inf")
    ok = len(over_budget) <= NFR_ALLOWED_FAILURES

    message = ("NFR %s: %d/%d requests within %d ms (slowest %.0f ms)"
               % ("passed" if ok else "FAILED",
                  NFR_SAMPLES - len(over_budget), NFR_SAMPLES,
                  int(NFR_BUDGET_SECONDS * 1000),
                  slowest * 1000 if slowest != float("inf") else -1))

    print("  %s" % message)
    return ok, message


def observe_ai_mode(llm):
    """Prove the AI request path end to end: loop -> backend -> Ollama -> LLM -> back."""
    question = "Which menu items do customers complain about?"

    try:
        response = requests.post(
            API_URL + "/api/ai/ask", json={"question": question}, timeout=240
        )
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        message = "AI-Mode check failed: %s" % exc
        print("  %s" % message)
        return False, message

    mode = payload.get("mode")
    model = payload.get("model")
    answer = (payload.get("answer") or "").strip()

    message = ("AI-Mode answered via %s (%s): %s"
               % (mode, model, answer[:160] or "(empty)"))
    print("  %s" % message)

    return mode == "ollama" and bool(answer), message


def get_implementation_agent_advice(llm, evidence):
    prompt = load_and_render(
        "agentic/implementation_task_prompt.txt",
        validation_evidence=evidence,
    )
    system = load_and_render("agentic/implementation_system_prompt.txt")

    return llm.call_model(system, prompt, model_name=OLLAMA_MODEL, max_tokens=220)


def get_review_agent_advice(llm, recommendation, evidence):
    prompt = load_and_render(
        "agentic/review_task_prompt.txt",
        implementation_recommendation=recommendation,
        validation_evidence=evidence,
    )
    system = load_and_render("agentic/review_system_prompt.txt")

    return llm.call_model(system, prompt, model_name=OLLAMA_REVIEW_MODEL,
                          max_tokens=200)


def human_review(interactive=True):
    if not interactive:
        print("HUMAN REVIEW: skipped (--no-input), decision deferred")
        return "Deferred"

    print()
    print("HUMAN REVIEW")
    print("1 - Accept")
    print("2 - Partially Accept")
    print("3 - Reject")

    try:
        decision = input("Decision: ").strip()
    except EOFError:
        return "Deferred"

    return {"1": "Accept", "2": "Partially Accept"}.get(decision, "Reject")


def adapt(decision, observations):
    """The ADAPT step. Failed checks outrank any agent recommendation."""
    failures = [label for label, ok, _ in observations if not ok]

    if failures:
        action = ("Fix the failed check(s) first: %s. Rerun the loop before "
                  "applying any agent recommendation." % ", ".join(failures))
    elif decision == "Accept":
        action = "Apply the recommendation and rerun validation."
    elif decision == "Partially Accept":
        action = "Apply the selected recommendations and rerun validation."
    elif decision == "Deferred":
        action = ("No human decision was recorded in this run. Review the "
                  "agent output and rerun interactively.")
    else:
        action = "Keep the current implementation and document the rationale."

    print()
    print("ADAPT: %s" % action)
    return action


def write_logs(record):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = record["started_at"].replace("-", "").replace(":", "").replace(" ", "-")[:15]

    jsonl_path = LOG_DIR / ("loop-%s.jsonl" % stamp)
    with open(jsonl_path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(record, indent=2) + "\n")

    lines = [
        "# Agentic Loop Run - Student 1 (Customer Feedback & Reviews)",
        "",
        "- Started: %s UTC" % record["started_at"],
        "- Implementation model: %s" % record["implementation_model"],
        "- Review model: %s" % record["review_model"],
        "- Result: %s" % ("PASS" if record["all_checks_passed"] else "FAIL"),
        "",
        "## PLAN",
        "",
        "```json",
        json.dumps(record["plan"], indent=2),
        "```",
        "",
        "## OBSERVE",
        "",
        "| Check | Result | Detail |",
        "|---|---|---|",
    ]

    for label, ok, detail in record["observations"]:
        lines.append("| %s | %s | %s |"
                     % (label, "PASS" if ok else "FAIL",
                        detail.replace("|", "\\|")))

    lines += [
        "",
        "## IMPLEMENTATION AGENT (%s)" % record["implementation_model"],
        "",
        "```text",
        record["implementation_advice"],
        "```",
        "",
        "## REVIEW AGENT (%s)" % record["review_model"],
        "",
        "```text",
        record["review_advice"],
        "```",
        "",
        "## HUMAN DECISION",
        "",
        "%s" % record["decision"],
        "",
        "## ADAPT",
        "",
        "%s" % record["adapt_action"],
        "",
    ]

    md_path = LOG_DIR / ("loop-%s.md" % stamp)
    md_path.write_text("\n".join(lines), encoding="utf-8")

    return jsonl_path, md_path


def main():
    parser = argparse.ArgumentParser(
        description="Student 1 agentic loop: PLAN -> ACT -> OBSERVE -> ADAPT"
    )
    parser.add_argument("--no-input", action="store_true",
                        help="skip the human review prompt (CI)")
    parser.add_argument("--no-ai", action="store_true",
                        help="run the deterministic checks only")
    args = parser.parse_args()

    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    print("=" * 68)
    print("ASD RELEASE 0 - STUDENT 3 AGENTIC LOOP")
    print("Customer Feedback & Reviews - Hangyeol Yi")
    print("=" * 68)

    print()
    print("PLAN")
    for key, value in PLAN.items():
        if isinstance(value, list):
            print("  %s:" % key)
            for item in value:
                print("    - %s" % item)
        else:
            print("  %s: %s" % (key, value))

    print()
    print("ACT")
    print("  Run deterministic checks against the running microservices")

    llm = LLMClient()
    observations = []

    print()
    print("OBSERVE: Database")
    ok_db, msg_db = observe_database()
    print("  %s" % msg_db)
    observations.append(("Database", ok_db, msg_db))

    print()
    print("OBSERVE: Live Endpoints")
    endpoint_results = observe_live_endpoints()
    endpoints_ok = all("HTTP 200" in line for line in endpoint_results)
    observations.append(("Endpoints", endpoints_ok, "; ".join(endpoint_results)))

    print()
    print("OBSERVE: Non-Functional Requirement")
    ok_nfr, msg_nfr = observe_nfr()
    observations.append(("NFR", ok_nfr, msg_nfr))

    print()
    print("OBSERVE: AI-Mode")
    if args.no_ai:
        msg_ai = "AI-Mode check skipped (--no-ai)"
        ok_ai = True
        print("  %s" % msg_ai)
    else:
        ok_ai, msg_ai = observe_ai_mode(llm)
    observations.append(("AI-Mode", ok_ai, msg_ai))

    evidence = " | ".join("%s: %s" % (label, detail)
                          for label, _ok, detail in observations)

    implementation_advice = "Implementation agent not run."
    review_advice = "Review agent not run."

    if not args.no_ai:
        print()
        print("IMPLEMENTATION AGENT")
        print("  Model: %s" % OLLAMA_MODEL)
        advice, error = get_implementation_agent_advice(llm, evidence)
        implementation_advice = advice or ("unavailable: %s" % error)
        print()
        print(implementation_advice)

        print()
        print("REVIEW AGENT")
        print("  Model: %s" % OLLAMA_REVIEW_MODEL)
        advice, error = get_review_agent_advice(
            llm, implementation_advice, evidence
        )
        review_advice = advice or ("unavailable: %s" % error)
        print()
        print(review_advice)

    print()
    print("HUMAN DECISION")
    decision = human_review(interactive=not args.no_input)
    print("  Decision: %s" % decision)

    adapt_action = adapt(decision, observations)

    all_passed = all(ok for _label, ok, _detail in observations)

    jsonl_path, md_path = write_logs({
        "started_at": started_at,
        "plan": PLAN,
        "observations": observations,
        "all_checks_passed": all_passed,
        "implementation_model": OLLAMA_MODEL,
        "review_model": OLLAMA_REVIEW_MODEL,
        "implementation_advice": implementation_advice,
        "review_advice": review_advice,
        "decision": decision,
        "adapt_action": adapt_action,
    })

    print()
    print("Evidence written to:")
    print("  %s" % md_path)
    print("  %s" % jsonl_path)

    print()
    print("LOOP COMPLETE - %s" % ("PASS" if all_passed else "FAIL"))

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
