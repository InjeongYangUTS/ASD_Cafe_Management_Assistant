"""
Student 4 (Stella Kwon) - Order & Kitchen Management
Capture the Multi-Agent workflow evidence for Release 2.

Runs one Planner -> Worker -> Reviewer -> Human Review cycle THROUGH MY
OWN FEATURE - student-4-backend, not the shared server directly - and
writes the two records the agentic loop's `multi-agent` mode reviews:

    evidence/release2/multi-agent/student-4-1-awaiting-review.json
    evidence/release2/multi-agent/student-4-2-human-review.json

Going through the backend is the point. It is what shows the feature is
integrated: the task is mine, the evidence the agents reason over is my
live kitchen queue, and the human decision is recorded against my own
endpoint. Calling :5800 directly would prove only that somebody else's
server works.

Before running this, three things must be up:

    ollama serve                       the model the three agents use
    ai-services/multi-agent-server     python app.py          (:5800)
    docker compose up student-4-*      database + backend     (:8400)

Then:

    python student-4/agentic/capture_multiagent.py
    python student-4/agentic/capture_multiagent.py --decision approve

The default decision is partial_accept with a written comment, because a
decision that is not a rubber stamp is the one worth showing: it proves
the human stage can disagree with the Reviewer and that the disagreement
is recorded with a reason.
"""

import argparse
import json
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))

EVIDENCE_DIR = os.path.join(REPO_ROOT, "evidence", "release2", "multi-agent")

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8400")

DEFAULT_TASK = (
    "Recommend the order the kitchen should work the open tickets in, "
    "and say which ticket is most at risk of missing the service target."
)

DEFAULT_COMMENT = (
    "The ranking matches the supplied priority scores, so that part is "
    "accepted. The at-risk ticket is named by position rather than by "
    "order number, which the kitchen cannot act on, so that part is not."
)


def write(stage, payload):
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    path = os.path.join(EVIDENCE_DIR, "student-4-%s.json" % stage)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    print("    wrote %s" % os.path.relpath(path, REPO_ROOT))
    return path


def envelope(result):
    """The shape the other four students' evidence files already use."""
    return {
        "server": result.get("server"),
        "status": result.get("status"),
        "captured_from": "student-4-backend /api/ai/multi-agent",
        "workflow": result.get("raw") or {
            key: result.get(key)
            for key in ("workflow_id", "task", "status", "created_at",
                        "evidence", "plan", "worker_output", "review",
                        "human_review", "history")
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Capture Student 4's Multi-Agent workflow evidence")
    parser.add_argument("--task", default=DEFAULT_TASK)
    parser.add_argument("--decision", default="partial_accept",
                        choices=["approve", "correct",
                                 "partial_accept", "reject"])
    parser.add_argument("--comments", default=DEFAULT_COMMENT)
    parser.add_argument("--backend", default=BACKEND_URL)
    args = parser.parse_args()

    backend = args.backend.rstrip("/")

    print("Multi-Agent evidence capture - through %s" % backend)
    print("  task: %s" % args.task)

    print("\n[1/2] starting the workflow (three agents on a local model -")
    print("      this takes minutes, not seconds)...")

    started = time.time()
    try:
        response = requests.post(
            backend + "/api/ai/multi-agent/workflows",
            json={"task": args.task}, timeout=900)
        first = response.json()
    except requests.RequestException as exc:
        print("      could not reach the backend: %s" % exc)
        return 1
    except ValueError:
        print("      the backend did not return JSON (HTTP %d)"
              % response.status_code)
        return 1

    if not first.get("available"):
        print("      %s" % first.get("reason"))
        return 1

    if not first.get("awaiting_review"):
        print("      the workflow did not reach the human stage - status %r"
              % first.get("status"))
        write("1-failed", envelope(first))
        return 1

    print("      reached %s after %.0f s"
          % (first["status"], time.time() - started))
    write("1-awaiting-review", envelope(first))

    workflow_id = first["workflow_id"]

    print("\n[2/2] submitting the human decision: %s" % args.decision)
    try:
        response = requests.post(
            "%s/api/ai/multi-agent/workflows/%s/human-review"
            % (backend, workflow_id),
            json={"decision": args.decision, "comments": args.comments},
            timeout=900)
        second = response.json()
    except requests.RequestException as exc:
        print("      could not reach the backend: %s" % exc)
        return 1
    except ValueError:
        print("      the backend did not return JSON (HTTP %d)"
              % response.status_code)
        return 1

    if not second.get("available") or not second.get("ok"):
        print("      %s" % second.get("reason"))
        return 1

    print("      status is now %s" % second.get("status"))
    write("2-human-review", envelope(second))

    print("\nDone. Review it with:")
    print("    python student-4/agentic/loop.py --mode multi-agent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
