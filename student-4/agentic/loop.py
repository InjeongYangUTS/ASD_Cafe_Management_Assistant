"""
Student 4 (Stella Kwon) - Order & Kitchen Management
Agentic AI review loop :  PLAN -> ACT -> OBSERVE -> ADAPT

Reviews my slice of the Release 0 system across the four areas named in the
assignment brief - the database, the implementation, the microservices
architecture and the DevOps pipeline - and keeps iterating until the checks
pass or the iteration budget runs out.

    PLAN     decide which probes to run this iteration, and why
    ACT      run those probes against the live services and the repository
    OBSERVE  record what each probe found, with evidence
    ADAPT    ask the LLM (Ollama) to read the observations and choose the
             focus for the next iteration; fall back to a deterministic
             rule when Ollama is not available

Every iteration is appended to agentic/logs/ as both a readable Markdown
report and a machine-readable JSONL record.

Usage
    python agentic/loop.py                       # against localhost
    python agentic/loop.py --max-iterations 3
    python agentic/loop.py --backend-url http://localhost:8400
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(BASE_DIR)
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

AREAS = ["database", "implementation", "architecture", "devops"]

SYSTEM_PROMPT = (
    "You are a software engineering reviewer for a university microservices "
    "project. You are given the results of automated checks on one student's "
    "services. Reply with two short sections: FINDING (what the results mean, "
    "at most two sentences) and NEXT (which of database, implementation, "
    "architecture, devops the next iteration should focus on, and why, in one "
    "sentence). Be direct and do not invent checks that were not run."
)


# =====================================================================
# Small helpers
# =====================================================================

class Probe:
    """One check, tagged with the review area it belongs to."""

    def __init__(self, key, area, description, run):
        self.key = key
        self.area = area
        self.description = description
        self.run = run


def ok(evidence):
    return True, evidence


def fail(evidence):
    return False, evidence


def read(*path_parts):
    path = os.path.join(BASE_DIR, *path_parts)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def get_json(url, timeout=8):
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


# =====================================================================
# PROBES
# =====================================================================

def build_probes(db_url, backend_url, frontend_url):

    # ---------------- database ----------------

    def schema_has_all_three_tables():
        schema = read("database", "schema.sql") or ""
        missing = [t for t in ("orders", "order_items", "order_statuses")
                   if "CREATE TABLE IF NOT EXISTS %s" % t not in schema]
        if missing:
            return fail("schema.sql is missing: %s" % ", ".join(missing))
        return ok("orders, order_items and order_statuses are all declared")

    def database_is_seeded():
        stats = get_json(db_url + "/db/stats")
        counts = stats["row_counts"]
        if counts["orders"] < 10:
            return fail("only %d orders seeded, the brief asks for 10+"
                        % counts["orders"])
        return ok("orders=%d items=%d statuses=%d"
                  % (counts["orders"], counts["order_items"],
                     counts["order_statuses"]))

    def cascade_delete_removes_children():
        created = requests.post(db_url + "/db/orders", timeout=8, json={
            "channel": "DINE_IN", "customer_name": "agentic-loop probe",
            "items": [{"menu_id": 2, "menu_name": "Latte",
                       "unit_price": 4.5, "quantity": 1}],
        }).json()
        order_id = created["id"]

        requests.delete(db_url + "/db/orders/%d" % order_id, timeout=8)

        leftovers = get_json(db_url + "/db/order-statuses?limit=200")
        orphans = [row for row in leftovers["status_history"]
                   if row["order_id"] == order_id]

        if orphans:
            return fail("%d status rows survived the parent delete - "
                        "foreign keys are not cascading" % len(orphans))
        return ok("deleting order %d removed its items and status history"
                  % order_id)

    def totals_match_the_line_items():
        data = get_json(db_url + "/db/orders?include=items&limit=50")
        wrong = []

        for order in data["orders"]:
            # Agreed rule (see database/app.py recalc_order): an order's
            # total is the value of every line it still holds, cancelled
            # lines included, so a cancelled ticket stays reportable.
            expected = round(sum(i["line_total"] for i in order["items"]), 2)
            if abs(expected - order["total_amount"]) > 0.011:
                wrong.append("%s (stored %.2f, items add to %.2f)"
                             % (order["order_number"], order["total_amount"],
                                expected))

        if wrong:
            return fail("order totals disagree with their items: %s"
                        % "; ".join(wrong[:5]))
        return ok("all %d order totals match the sum of their line items"
                  % data["count"])

    # ---------------- implementation ----------------

    def crud_round_trip():
        created = requests.post(backend_url + "/api/orders", timeout=15, json={
            "channel": "TAKEAWAY", "customer_name": "agentic-loop probe",
            "items": [{"menu_id": 2, "quantity": 2}],
        })
        if created.status_code != 201:
            return fail("create returned %d: %s"
                        % (created.status_code, created.text[:160]))

        order = created.json()["order"]
        order_id = order["id"]

        try:
            read_back = get_json(backend_url + "/api/orders/%d" % order_id)
            if read_back["item_count"] != 2:
                return fail("read back item_count=%s, expected 2"
                            % read_back["item_count"])

            item_id = read_back["items"][0]["id"]
            requests.put(backend_url + "/api/order-items/%d" % item_id,
                         json={"quantity": 3}, timeout=10)

            updated = get_json(backend_url + "/api/orders/%d" % order_id)
            if updated["item_count"] != 3:
                return fail("after update item_count=%s, expected 3"
                            % updated["item_count"])
        finally:
            requests.delete(db_url + "/db/orders/%d" % order_id, timeout=8)

        gone = requests.get(backend_url + "/api/orders/%d" % order_id, timeout=8)
        if gone.status_code != 404:
            return fail("deleted order still readable (status %d)"
                        % gone.status_code)

        return ok("create -> read -> update -> delete all behaved on order %d"
                  % order_id)

    def invalid_input_is_rejected():
        cases = [
            ({"items": []}, 400, "empty basket"),
            ({"items": [{"menu_id": 999999, "quantity": 1}]}, 400, "unknown menu id"),
            ({"items": [{"menu_id": 2, "quantity": 0}]}, 400, "zero quantity"),
        ]
        problems = []

        for payload, expected, label in cases:
            response = requests.post(backend_url + "/api/orders",
                                     json=payload, timeout=10)
            if response.status_code != expected:
                problems.append("%s returned %d, expected %d"
                                % (label, response.status_code, expected))

        if problems:
            return fail("; ".join(problems))
        return ok("empty basket, unknown menu id and zero quantity are all rejected")

    def illegal_status_jump_is_refused():
        data = get_json(backend_url + "/api/orders?status=PENDING&limit=1")
        if not data["orders"]:
            return ok("no PENDING order available to test - skipped")

        order_id = data["orders"][0]["id"]
        response = requests.put(backend_url + "/api/order-status/%d" % order_id,
                                json={"status": "COMPLETED"}, timeout=10)

        if response.status_code != 409:
            return fail("PENDING -> COMPLETED returned %d, expected 409"
                        % response.status_code)
        return ok("PENDING -> COMPLETED refused with 409, as designed")

    # ---------------- architecture ----------------

    def backend_never_opens_sqlite():
        offenders = []
        for filename in ("app.py", "clients.py", "ai.py"):
            source = read("backend", filename) or ""
            if re.search(r"^\s*import\s+sqlite3", source, re.M):
                offenders.append(filename)
            if ".db" in source and "sqlite3.connect" in source:
                offenders.append(filename + " (sqlite3.connect)")

        if offenders:
            return fail("backend touches SQLite directly in: %s"
                        % ", ".join(sorted(set(offenders))))
        return ok("backend reaches data only through the /db HTTP API")

    def frontend_holds_no_data_layer():
        source = read("frontend", "app.py") or ""
        if re.search(r"^\s*import\s+sqlite3", source, re.M):
            return fail("frontend imports sqlite3 - it must be stateless")
        if "BACKEND_URL" not in source:
            return fail("frontend does not route through BACKEND_URL")
        return ok("frontend is stateless and calls the backend over HTTP")

    def cross_feature_calls_use_peer_apis():
        source = read("backend", "clients.py") or ""
        problems = []

        if "MENU_SERVICE_URL" not in source:
            problems.append("no Menu API client for Student 2")
        if "INVENTORY_SERVICE_URL" not in source:
            problems.append("no Inventory API client for Student 3")
        if re.search(r"student-[1235]/.*\.db", source):
            problems.append("references another student's database file")

        if problems:
            return fail("; ".join(problems))
        return ok("Student 2 and Student 3 are reached over HTTP APIs only")

    def peer_service_outage_is_survivable():
        health = get_json(backend_url + "/api/health")
        menu_up = health["dependencies"]["menu_service_student_2"]["reachable"]

        catalog = get_json(backend_url + "/api/menu")
        if catalog["count"] < 15:
            return fail("menu returned only %d items - the fallback cache is "
                        "not covering the outage" % catalog["count"])

        return ok("menu served %d items with Student 2 %s (source: %s)"
                  % (catalog["count"], "up" if menu_up else "down",
                     catalog["source"]))

    # ---------------- devops ----------------

    def every_service_has_a_dockerfile():
        missing = [service for service in ("frontend", "backend", "database")
                   if read(service, "Dockerfile") is None]
        if missing:
            return fail("no Dockerfile for: %s" % ", ".join(missing))
        return ok("frontend, backend and database each have a Dockerfile")

    def containers_declare_healthchecks():
        missing = [service for service in ("frontend", "backend", "database")
                   if "HEALTHCHECK" not in (read(service, "Dockerfile") or "")]
        if missing:
            return fail("no HEALTHCHECK in: %s" % ", ".join(missing))
        return ok("all three Dockerfiles declare a HEALTHCHECK")

    def workflow_builds_and_validates():
        path = os.path.join(REPO_ROOT, ".github", "workflows", "student-4.yml")
        if not os.path.exists(path):
            return fail(".github/workflows/student-4.yml is missing")

        with open(path, "r", encoding="utf-8") as handle:
            workflow = handle.read()

        problems = []
        if "docker" not in workflow:
            problems.append("no docker build step")
        if "pytest" not in workflow:
            problems.append("no test step")

        if problems:
            return fail("; ".join(problems))
        return ok("student-4.yml builds the images and runs the test suite")

    def compose_wires_my_three_services():
        path = os.path.join(REPO_ROOT, "docker-compose.yml")
        if not os.path.exists(path):
            return fail("docker-compose.yml is missing from the repository root")

        with open(path, "r", encoding="utf-8") as handle:
            compose = handle.read()

        missing = [name for name in ("student-4-frontend", "student-4-backend",
                                     "student-4-database", "ollama")
                   if name not in compose]
        if missing:
            return fail("compose does not define: %s" % ", ".join(missing))
        return ok("compose defines my three services plus the shared Ollama runtime")

    def all_three_containers_answer():
        endpoints = [
            ("database", db_url + "/db/health"),
            ("backend", backend_url + "/api/health"),
            ("frontend", frontend_url + "/health"),
        ]
        down = []

        for name, url in endpoints:
            try:
                response = requests.get(url, timeout=6)
                if response.status_code >= 400:
                    down.append("%s (%d)" % (name, response.status_code))
            except requests.RequestException:
                down.append("%s (unreachable)" % name)

        if down:
            return fail("not answering: %s" % ", ".join(down))
        return ok("database, backend and frontend all answered their health endpoint")

    return [
        Probe("schema_tables", "database", "All three tables are declared",
              schema_has_all_three_tables),
        Probe("seed_volume", "database", "At least 10 seeded orders",
              database_is_seeded),
        Probe("cascade_delete", "database", "Deleting an order cascades",
              cascade_delete_removes_children),
        Probe("total_integrity", "database", "Order totals match their items",
              totals_match_the_line_items),

        Probe("crud_round_trip", "implementation", "Create/read/update/delete works",
              crud_round_trip),
        Probe("input_validation", "implementation", "Bad input is rejected",
              invalid_input_is_rejected),
        Probe("status_rules", "implementation", "Illegal status jumps refused",
              illegal_status_jump_is_refused),

        Probe("no_direct_sqlite", "architecture", "Backend does not open SQLite",
              backend_never_opens_sqlite),
        Probe("stateless_frontend", "architecture", "Frontend holds no data layer",
              frontend_holds_no_data_layer),
        Probe("peer_api_only", "architecture", "Peer data via their APIs only",
              cross_feature_calls_use_peer_apis),
        Probe("outage_tolerance", "architecture", "Survives a peer outage",
              peer_service_outage_is_survivable),

        Probe("dockerfiles", "devops", "Every service is containerised",
              every_service_has_a_dockerfile),
        Probe("healthchecks", "devops", "Containers declare healthchecks",
              containers_declare_healthchecks),
        Probe("workflow", "devops", "student-4.yml builds and validates",
              workflow_builds_and_validates),
        Probe("compose", "devops", "Shared compose wires my services",
              compose_wires_my_three_services),
        Probe("services_live", "devops", "All three containers answer",
              all_three_containers_answer),
    ]


# =====================================================================
# The loop
# =====================================================================

def plan(iteration, probes, focus, previous):
    """PLAN - choose this iteration's probes and say why."""
    if iteration == 1:
        selected = probes
        rationale = ("First pass: run every probe across all four review "
                     "areas to establish a baseline.")
    elif focus == "all":
        selected = probes
        rationale = "Re-running every probe to confirm nothing else regressed."
    else:
        failed_keys = {r["key"] for r in previous if not r["passed"]}
        selected = [p for p in probes
                    if p.area == focus or p.key in failed_keys]
        rationale = ("Focusing on '%s' because the previous iteration found "
                     "problems there, and re-testing every probe that failed."
                     % focus)

    return selected, rationale


def act(selected):
    """ACT - execute the probes."""
    results = []

    for probe in selected:
        try:
            passed, evidence = probe.run()
        except requests.RequestException as exc:
            passed, evidence = False, "service call failed: %s" % exc
        except Exception as exc:                    # noqa: BLE001 - probe guard
            passed, evidence = False, "probe raised %s: %s" % (
                type(exc).__name__, exc)

        results.append({
            "key": probe.key,
            "area": probe.area,
            "description": probe.description,
            "passed": passed,
            "evidence": evidence,
        })

    return results


def observe(results):
    """OBSERVE - summarise what the probes found."""
    failed = [r for r in results if not r["passed"]]

    by_area = {}
    for area in AREAS:
        area_results = [r for r in results if r["area"] == area]
        if area_results:
            by_area[area] = {
                "passed": sum(1 for r in area_results if r["passed"]),
                "total": len(area_results),
            }

    return {
        "total": len(results),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "failures": failed,
        "by_area": by_area,
    }


def adapt(observation, ollama_url, model):
    """ADAPT - decide the next focus, with the LLM if it is available."""
    if observation["failed"] == 0:
        return {
            "next_focus": None,
            "reasoning": "Every probe passed - the loop has converged and stops here.",
            "source": "rule",
        }

    worst = min(
        observation["by_area"].items(),
        key=lambda kv: kv[1]["passed"] / kv[1]["total"],
    )[0]

    rule_reasoning = (
        "%d of %d probes failed. The weakest area is '%s' (%d/%d passing), "
        "so the next iteration concentrates there."
        % (observation["failed"], observation["total"], worst,
           observation["by_area"][worst]["passed"],
           observation["by_area"][worst]["total"])
    )

    prompt_lines = [
        "AUTOMATED REVIEW RESULTS",
        "",
        "Passed: %d of %d" % (observation["passed"], observation["total"]),
        "",
        "By area:",
    ]
    for area, counts in observation["by_area"].items():
        prompt_lines.append("  %-15s %d/%d passing"
                            % (area, counts["passed"], counts["total"]))

    prompt_lines += ["", "Failures:"]
    for failure in observation["failures"]:
        prompt_lines.append("  [%s] %s -> %s"
                            % (failure["area"], failure["description"],
                               failure["evidence"]))

    prompt = "\n".join(prompt_lines)

    try:
        response = requests.post(
            ollama_url.rstrip("/") + "/api/generate",
            json={"model": model, "prompt": prompt, "system": SYSTEM_PROMPT,
                  "stream": False, "options": {"temperature": 0.1}},
            timeout=60,
        )
        response.raise_for_status()
        reply = response.json().get("response", "").strip()
    except (requests.RequestException, ValueError):
        reply = ""

    if not reply:
        return {"next_focus": worst, "reasoning": rule_reasoning,
                "source": "rule (Ollama unavailable)", "prompt": prompt}

    chosen = worst
    for area in AREAS:
        if re.search(r"NEXT.*%s" % area, reply, re.S | re.I):
            chosen = area
            break

    return {"next_focus": chosen, "reasoning": reply, "source": "ollama:%s" % model,
            "prompt": prompt}


# =====================================================================
# Logging
# =====================================================================

def write_logs(run_id, records):
    os.makedirs(LOG_DIR, exist_ok=True)

    jsonl_path = os.path.join(LOG_DIR, "loop-%s.jsonl" % run_id)
    with open(jsonl_path, "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")

    md_path = os.path.join(LOG_DIR, "loop-%s.md" % run_id)
    with open(md_path, "w", encoding="utf-8") as handle:
        handle.write("# Agentic loop run %s\n\n" % run_id)
        handle.write("Student 4 (Stella Kwon) - Order & Kitchen Management\n\n")

        for record in records:
            handle.write("## Iteration %d\n\n" % record["iteration"])
            handle.write("**PLAN** - %s\n\n" % record["plan"]["rationale"])
            handle.write("Probes selected: %d\n\n"
                         % len(record["plan"]["probes"]))

            handle.write("**ACT / OBSERVE**\n\n")
            handle.write("| Area | Check | Result | Evidence |\n")
            handle.write("| --- | --- | --- | --- |\n")
            for result in record["results"]:
                handle.write("| %s | %s | %s | %s |\n" % (
                    result["area"], result["description"],
                    "PASS" if result["passed"] else "FAIL",
                    result["evidence"].replace("|", "/"),
                ))

            handle.write("\n**OBSERVE** - %d/%d passed\n\n"
                         % (record["observation"]["passed"],
                            record["observation"]["total"]))

            handle.write("**ADAPT** (%s) - %s\n\n"
                         % (record["adaptation"]["source"],
                            record["adaptation"]["reasoning"]))
            handle.write("---\n\n")

    return md_path, jsonl_path


# =====================================================================
# Entry point
# =====================================================================

def main():
    parser = argparse.ArgumentParser(description="Student 4 agentic review loop")
    parser.add_argument("--db-url",
                        default=os.environ.get("S4_DB_URL", "http://localhost:7400"))
    parser.add_argument("--backend-url",
                        default=os.environ.get("S4_BACKEND_URL", "http://localhost:8400"))
    parser.add_argument("--frontend-url",
                        default=os.environ.get("S4_FRONTEND_URL", "http://localhost:5400"))
    parser.add_argument("--ollama-url",
                        default=os.environ.get("OLLAMA_URL", "http://localhost:11434"))
    parser.add_argument("--model",
                        default=os.environ.get("OLLAMA_MODEL", "llama3.2"))
    parser.add_argument("--max-iterations", type=int, default=3)
    args = parser.parse_args()

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    probes = build_probes(args.db_url, args.backend_url, args.frontend_url)

    print("=" * 72)
    print(" AGENTIC REVIEW LOOP - Student 4 - Order & Kitchen Management")
    print(" run %s | model %s | up to %d iterations"
          % (run_id, args.model, args.max_iterations))
    print("=" * 72)

    records = []
    focus = "all"
    previous_results = []

    for iteration in range(1, args.max_iterations + 1):

        selected, rationale = plan(iteration, probes, focus, previous_results)

        print("\n--- ITERATION %d ---" % iteration)
        print("[PLAN]    %s" % rationale)
        print("[PLAN]    %d probe(s): %s"
              % (len(selected), ", ".join(p.key for p in selected)))

        print("[ACT]     running probes...")
        results = act(selected)

        for result in results:
            print("          %s  %-14s %s"
                  % ("PASS" if result["passed"] else "FAIL",
                     result["area"], result["description"]))
            if not result["passed"]:
                print("                                -> %s" % result["evidence"])

        observation = observe(results)
        print("[OBSERVE] %d/%d passed" % (observation["passed"], observation["total"]))
        for area, counts in observation["by_area"].items():
            print("          %-15s %d/%d" % (area, counts["passed"], counts["total"]))

        adaptation = adapt(observation, args.ollama_url, args.model)
        print("[ADAPT]   (%s) %s" % (adaptation["source"],
                                     adaptation["reasoning"].replace("\n", " ")))

        records.append({
            "iteration": iteration,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "plan": {"rationale": rationale,
                     "probes": [p.key for p in selected]},
            "results": results,
            "observation": {k: v for k, v in observation.items()
                            if k != "failures"},
            "adaptation": adaptation,
        })

        previous_results = results

        if adaptation["next_focus"] is None:
            print("\n[LOOP]    converged after %d iteration(s)." % iteration)
            break

        focus = adaptation["next_focus"]
        print("[LOOP]    next iteration focuses on '%s'" % focus)

    md_path, jsonl_path = write_logs(run_id, records)

    final = records[-1]["observation"]
    print("\n" + "=" * 72)
    print(" FINAL: %d/%d probes passing" % (final["passed"], final["total"]))
    print(" log:   %s" % os.path.relpath(md_path, REPO_ROOT))
    print("        %s" % os.path.relpath(jsonl_path, REPO_ROOT))
    print("=" * 72)

    return 0 if final["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
