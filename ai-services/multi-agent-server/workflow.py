
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from planner import create_plan
from worker import execute_task, revise_task
from reviewer import review_task


BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

WORKFLOWS = {}
LOCK = threading.RLock()

VALID_DECISIONS = {
    "approve",
    "correct",
    "reject",
    "partial_accept"
}


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def save_workflow(workflow):
    """Save workflow history and audit evidence."""

    path = LOG_DIR / f"{workflow['workflow_id']}.json"

    with LOCK:
        path.write_text(
            json.dumps(workflow, indent=2),
            encoding="utf-8"
        )


def record_event(workflow, event, details=None):
    """Add a timestamped audit event."""

    workflow["history"].append({
        "timestamp": timestamp(),
        "event": event,
        "details": details or {}
    })

    save_workflow(workflow)


def start_workflow(task, evidence=None):
    """Run Planner, Worker and Reviewer agents."""

    if not isinstance(task, str) or not task.strip():
        raise ValueError("A valid task is required.")

    if evidence is None:
        evidence = {}

    if not isinstance(evidence, dict):
        raise ValueError("Evidence must be a JSON object.")

    workflow_id = str(uuid.uuid4())

    workflow = {
        "workflow_id": workflow_id,
        "task": task.strip(),
        "evidence": evidence,
        "status": "running",
        "created_at": timestamp(),
        "plan": None,
        "worker_output": None,
        "review": None,
        "human_review": None,
        "history": []
    }

    with LOCK:
        WORKFLOWS[workflow_id] = workflow

    record_event(workflow, "workflow_started")

    try:
        planner_result = create_plan(task, evidence)

        workflow["plan"] = planner_result["plan"]

        record_event(
            workflow,
            "planner_completed",
            {"plan": workflow["plan"]}
        )

        worker_result = execute_task(
            task,
            workflow["plan"],
            evidence
        )

        workflow["worker_output"] = worker_result["output"]

        record_event(
            workflow,
            "worker_completed",
            {"output": workflow["worker_output"]}
        )

        reviewer_result = review_task(
            task,
            workflow["plan"],
            workflow["worker_output"],
            evidence
        )

        workflow["review"] = reviewer_result["review"]
        workflow["status"] = "awaiting_human_review"

        record_event(
            workflow,
            "reviewer_completed",
            {"review": workflow["review"]}
        )

    except Exception as error:
        workflow["status"] = "failed"

        record_event(
            workflow,
            "workflow_failed",
            {"error": str(error)}
        )

        raise

    return workflow


def get_workflow(workflow_id):
    """Retrieve workflow details."""

    with LOCK:
        workflow = WORKFLOWS.get(workflow_id)

        if workflow is not None:
            return workflow

        path = LOG_DIR / f"{workflow_id}.json"

        if not path.exists():
            return None

        workflow = json.loads(
            path.read_text(encoding="utf-8")
        )

        WORKFLOWS[workflow_id] = workflow
        return workflow



def submit_human_review(workflow_id, decision, comments=""):
    """Record a human decision and handle requested corrections."""

    if decision not in VALID_DECISIONS:
        raise ValueError(
            "Decision must be approve, correct, "
            "reject or partial_accept."
        )

    if not isinstance(comments, str):
        raise ValueError("Comments must be text.")

    with LOCK:
        workflow = get_workflow(workflow_id)

        if workflow is None:
            raise LookupError("Workflow not found.")

        if workflow["status"] != "awaiting_human_review":
            raise ValueError("Workflow is not awaiting human review.")

        if decision == "correct" and not comments.strip():
            raise ValueError("Correction comments are required.")

        human_review = {
            "decision": decision,
            "comments": comments,
            "timestamp": timestamp()
        }

        workflow["human_review"] = human_review

        record_event(
            workflow,
            "human_review_submitted",
            human_review
        )

        if decision == "correct":
            previous_output = workflow["worker_output"]

            workflow["status"] = "revising"
            record_event(workflow, "revision_started")

            try:
                revised_result = revise_task(
                    workflow["task"],
                    workflow["plan"],
                    previous_output,
                    comments,
                    workflow["evidence"]
                )

                workflow["worker_output"] = revised_result["output"]

                record_event(
                    workflow,
                    "worker_revised",
                    {"output": workflow["worker_output"]}
                )

                reviewer_result = review_task(
                    workflow["task"],
                    workflow["plan"],
                    workflow["worker_output"],
                    workflow["evidence"]
                )

                workflow["review"] = reviewer_result["review"]
                workflow["status"] = "awaiting_human_review"

                record_event(
                    workflow,
                    "reviewer_revised",
                    {"review": workflow["review"]}
                )

            except Exception as error:
                workflow["status"] = "revision_failed"

                record_event(
                    workflow,
                    "revision_failed",
                    {"error": str(error)}
                )

                raise

        else:
            workflow["status"] = "completed"

            record_event(
                workflow,
                "human_review_completed",
                human_review
            )

        return workflow
