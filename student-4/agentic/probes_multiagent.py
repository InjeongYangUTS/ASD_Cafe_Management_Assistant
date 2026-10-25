"""
Student 4 (Stella Kwon) - Shared Agentic Loop
Release 2: Multi-Agent Workflow Review mode.

Reviews what a run of the shared Multi-Agent Server leaves behind, and
produces recommendations rather than a bare pass or fail.

Written against the server that is actually in the repository
(ai-services/multi-agent-server, port 5800), so the shapes below are
its shapes:

    GET  /health
    POST /workflows
    GET  /workflows/<id>
    POST /workflows/<id>/human-review

    workflow = {
        workflow_id, task, status, created_at, evidence,
        plan, worker_output, review,        <- each a JSON *string*
        human_review: {decision, comments, timestamp} | null,
        history: [{event, timestamp, details}]
    }

    status    awaiting_human_review -> completed
    decision  approve | correct | reject | partial_accept

What the mode is really checking is a chain of custody. Four stages
produce a decision, and at each link the question is whether the stage
used what the previous one produced. A workflow where every stage writes
something plausible without reading the one before it looks identical
from the outside and is worth nothing. Most of the probes exist to tell
those two apart.
"""

import json

import requests

from evidence import (Evidence, inner_json, iso_ordered, load_json,
                      newest_first,
                      overlap, relative, repo_glob)
from repo import must_not_be_containerised

AREAS = ["availability", "workflow", "chain-of-custody", "human-review"]

VALID_DECISIONS = ("approve", "correct", "reject", "partial_accept")

EXPECTED_EVENTS = ("workflow_started", "planner_completed",
                   "worker_completed", "reviewer_completed")

EVIDENCE_GLOB = "evidence/release2/multi-agent/*.json"


# Each student wraps a workflow record differently. Student 4 writes
# {server, status, workflow}; Student 5 writes {evidence_type, ...,
# initial_workflow, final_workflow}. The mode reviews whatever the team
# produces, so it looks for the record instead of demanding one shape -
# a probe that only reads its own author's format reviews nothing but
# its own author.
WORKFLOW_KEYS = ("workflow", "final_workflow", "initial_workflow")


def unwrap(data):
    """The workflow record inside whatever envelope it arrived in."""
    if not isinstance(data, dict):
        return {}
    for key in WORKFLOW_KEYS:
        inner = data.get(key)
        if isinstance(inner, dict) and inner.get("workflow_id"):
            return inner
    if data.get("workflow_id") and "history" in data:
        return data
    return {}


def _completed_run():
    """The newest workflow record that reached a human decision.

    A run still awaiting review is real evidence of the first three
    stages but cannot answer the human-review probes, so those pick the
    newest completed run if there is one and say so if there is not.
    """
    for path in newest_first(repo_glob(EVIDENCE_GLOB)):
        ev = Evidence(path, "A multi-agent workflow record", EVIDENCE_GLOB)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                ev.data = json.load(handle)
        except (ValueError, OSError):
            continue
        if unwrap(ev.data).get("human_review"):
            return ev
    return None


def build_multiagent_probes(server_url, backend_url, ok, fail, Probe):
    """Return the Multi-Agent review pack. ok/fail/Probe come from loop.py."""

    base = server_url.rstrip("/")
    backend = backend_url.rstrip("/")

    def record():
        """The newest file that actually contains a workflow record.

        Newest, not first: a file that holds no recognisable workflow is
        skipped rather than chosen, so one teammate committing a
        differently-shaped artefact cannot make this mode report twelve
        failures against evidence that is in fact complete.
        """
        ev = load_json(EVIDENCE_GLOB, "A multi-agent workflow record")
        if ev.path is None or ev.error or unwrap(ev.data):
            return ev
        for path in newest_first(repo_glob(EVIDENCE_GLOB)):
            candidate = load_json(relative(path), "A multi-agent workflow record")
            if unwrap(candidate.data):
                return candidate
        return ev

    def workflow_of(ev):
        """Unwrap whichever envelope this record arrived in."""
        return unwrap(ev.data)

    # ---------------- availability ----------------

    def server_answers():
        try:
            response = requests.get(base + "/health", timeout=6)
        except requests.RequestException as exc:
            return fail("the Multi-Agent server is not answering on %s. It "
                        "runs on the host and is not containerised, so start "
                        "it before this mode can review a live run. (%s)"
                        % (base, exc))
        if not response.ok:
            return fail("%s/health returned HTTP %d"
                        % (base, response.status_code))
        return ok("%s answered /health" % base)

    def not_a_compose_service():
        return must_not_be_containerised(
            "the Multi-Agent server", "multi-agent", "multiagent",
            ok=ok, fail=fail)

    def workflow_route_is_live():
        """A health endpoint is not the same as a working workflow route."""
        try:
            response = requests.get(base + "/workflows/does-not-exist",
                                    timeout=8)
        except requests.RequestException as exc:
            return fail("the workflow route did not answer: %s" % exc)
        if response.status_code >= 500:
            return fail("GET /workflows/<id> returned HTTP %d on an unknown "
                        "id - an unknown workflow should be a 404, not a "
                        "fault" % response.status_code)
        return ok("the workflow route answers (HTTP %d on an unknown id)"
                  % response.status_code)

    def reachable_from_my_feature():
        """The brief requires the workflow be reachable through the UI.

        The frontend calls my backend and my backend calls the
        Multi-Agent server, so the backend's health report is where that
        link has to show up.
        """
        try:
            health = requests.get(backend + "/api/health", timeout=8).json()
        except (requests.RequestException, ValueError) as exc:
            return fail("could not read %s/api/health: %s" % (backend, exc))

        deps = health.get("dependencies", health)
        for key in ("multi_agent", "multiagent", "multi_agent_server"):
            if key in deps:
                state = deps[key]
                if isinstance(state, dict) and not state.get("reachable"):
                    return fail("the backend reports the Multi-Agent server "
                                "unreachable at %s" % state.get("url", "?"))
                return ok("student-4-backend reports the Multi-Agent server "
                          "reachable, so the UI has a route to it")
        return fail("student-4-backend does not report the Multi-Agent "
                    "server among its health dependencies, so there is "
                    "nothing showing the frontend can reach it")

    # ---------------- workflow ----------------

    def a_record_exists():
        ev = record()
        problem = ev.problem()
        if problem:
            return fail(problem)
        workflow = workflow_of(ev)
        missing = [f for f in ("workflow_id", "task", "status", "history")
                   if f not in workflow]
        if missing:
            return fail("%s is missing %s"
                        % (relative(ev.path), ", ".join(missing)))
        return ok("reviewing %s - %r, status %s"
                  % (relative(ev.path), str(workflow.get("task"))[:55],
                     workflow.get("status")))

    def all_three_agents_ran():
        ev = record()
        if ev.problem():
            return fail(ev.problem())
        workflow = workflow_of(ev)
        empty = [name for name in ("plan", "worker_output", "review")
                 if not str(workflow.get(name) or "").strip()]
        if empty:
            return fail("these agent stages produced nothing: %s"
                        % ", ".join(empty))
        return ok("the Planner, Worker and Reviewer all produced output")

    def agent_output_is_structured():
        """Each agent stores its output as a JSON string, not prose.

        A free-text answer cannot be reviewed field by field, and the
        Reviewer's recommendation has to be machine-readable for the
        human step to act on it.
        """
        ev = record()
        if ev.problem():
            return fail(ev.problem())
        workflow = workflow_of(ev)
        prose = [name for name in ("plan", "worker_output", "review")
                 if inner_json(workflow.get(name)) is None]
        if prose:
            return fail("these stages returned text that is not JSON, so "
                        "their fields cannot be read: %s" % ", ".join(prose))
        return ok("all three agent outputs parse as JSON")

    def history_covers_every_stage():
        ev = record()
        if ev.problem():
            return fail(ev.problem())
        workflow = workflow_of(ev)
        history = workflow.get("history") or []
        events = {h.get("event") for h in history if isinstance(h, dict)}
        missing = [e for e in EXPECTED_EVENTS if e not in events]
        if missing:
            return fail("the coordination log records no %s"
                        % ", ".join(missing))
        return ok("%d history entries covering all four stages"
                  % len(history))

    def history_is_in_order():
        ev = record()
        if ev.problem():
            return fail(ev.problem())
        workflow = workflow_of(ev)
        history = workflow.get("history") or []
        stamps = [h.get("timestamp") for h in history if isinstance(h, dict)]
        if len(stamps) < 2:
            return fail("the history carries fewer than two timestamps, so "
                        "the order of events cannot be checked")
        if not iso_ordered(stamps):
            return fail("history timestamps are out of order, so the "
                        "sequence of events cannot be trusted")
        return ok("%d history timestamps, non-decreasing" % len(stamps))

    # ---------------- chain of custody ----------------

    def planner_produced_steps():
        ev = record()
        if ev.problem():
            return fail(ev.problem())
        plan = inner_json(workflow_of(ev).get("plan"), default={})
        steps = plan.get("worker_steps") if isinstance(plan, dict) else None
        if not steps:
            return fail("the Planner recorded no worker_steps, so the Worker "
                        "had nothing to follow and the Reviewer has no "
                        "standard to judge against")
        return ok("the Planner set out %d step(s) for the Worker"
                  % len(steps))

    def planner_separated_known_from_unknown():
        """A plan that never admits a gap is not a plan.

        The server's own plan shape has available_information and
        information_to_check. Both being present is what makes the
        Worker's missing_information meaningful later.
        """
        ev = record()
        if ev.problem():
            return fail(ev.problem())
        plan = inner_json(workflow_of(ev).get("plan"), default={})
        if not isinstance(plan, dict):
            return fail("the plan did not parse as an object")
        missing = [f for f in ("available_information", "information_to_check")
                   if f not in plan]
        if missing:
            return fail("the plan does not record %s" % ", ".join(missing))
        available = plan.get("available_information") or []
        return ok("the plan names %d piece(s) of available information and "
                  "lists what still needs checking" % len(available))

    def worker_used_the_plan():
        ev = record()
        if ev.problem():
            return fail(ev.problem())
        workflow = workflow_of(ev)
        plan = inner_json(workflow.get("plan"), default={})
        work = inner_json(workflow.get("worker_output"), default={})
        if not plan or not work:
            return fail("the plan or the Worker output is missing, so the "
                        "link between them cannot be checked")

        share = overlap(plan, work)
        if share is None:
            return fail("the plan carried no content words to compare")
        if share < 0.15:
            return fail("only %.0f%% of the plan's vocabulary appears in the "
                        "Worker's output - the Worker does not look like it "
                        "read the plan" % (share * 100))
        return ok("%.0f%% of the plan's vocabulary carries into the Worker's "
                  "output" % (share * 100))

    def worker_cited_the_evidence():
        ev = record()
        if ev.problem():
            return fail(ev.problem())
        work = inner_json(workflow_of(ev).get("worker_output"), default={})
        if not isinstance(work, dict):
            return fail("the Worker output did not parse as an object")
        used = work.get("evidence_used")
        if used is None:
            return fail("the Worker did not record evidence_used, so there "
                        "is nothing showing which supplied evidence it "
                        "actually drew on")
        if not used:
            return fail("the Worker recorded an empty evidence_used list "
                        "while the Planner supplied evidence to work from")
        return ok("the Worker cited %d piece(s) of the supplied evidence"
                  % len(used))

    def reviewer_judged_the_actual_work():
        ev = record()
        if ev.problem():
            return fail(ev.problem())
        workflow = workflow_of(ev)
        work = inner_json(workflow.get("worker_output"), default={})
        review = inner_json(workflow.get("review"), default={})
        if not work or not review:
            return fail("the Worker output or the review is missing")

        share = overlap(work, review)
        if share is None:
            return fail("the Worker output carried no content words")
        if share < 0.10:
            return fail("only %.0f%% of the Worker's vocabulary appears in "
                        "the review - the Reviewer looks like it wrote "
                        "generic commentary rather than reading the work"
                        % (share * 100))
        return ok("the review overlaps the Worker's output by %.0f%%"
                  % (share * 100))

    def reviewer_gave_a_recommendation_with_a_reason():
        ev = record()
        if ev.problem():
            return fail(ev.problem())
        review = inner_json(workflow_of(ev).get("review"), default={})
        if not isinstance(review, dict):
            return fail("the review did not parse as an object")
        missing = [f for f in ("assessment", "recommendation", "reason")
                   if not review.get(f)]
        if missing:
            return fail("the review records no %s. A recommendation a human "
                        "cannot check is not reviewable."
                        % ", ".join(missing))
        if "issues" not in review:
            return fail("the review does not record an issues list, even an "
                        "empty one, so it is unclear whether risks were "
                        "looked for")
        return ok("recommendation %r with a stated reason and %d issue(s)"
                  % (review.get("recommendation"),
                     len(review.get("issues") or [])))

    # ---------------- human review ----------------

    def a_human_decided():
        ev = _completed_run()
        if ev is None:
            return fail("no workflow record carries a human_review. A run "
                        "that stops at awaiting_human_review is not the "
                        "complete Planner, Worker, Reviewer, Human sequence "
                        "the brief requires.")
        decision = (ev.dig("workflow", "human_review", "decision")
                    or "").lower()
        if decision not in VALID_DECISIONS:
            return fail("human decision %r is not one of %s"
                        % (decision, ", ".join(VALID_DECISIONS)))
        return ok("human decision %r in %s"
                  % (decision, relative(ev.path)))

    def the_decision_is_timestamped():
        ev = _completed_run()
        if ev is None:
            return fail("no completed run to check")
        review = ev.dig("workflow", "human_review", default={}) or {}
        when = review.get("timestamp")
        if not when:
            return fail("the human decision records no timestamp, so it is "
                        "not auditable")
        created = ev.dig("workflow", "created_at")
        if created and not iso_ordered([created, when]):
            return fail("the human decision is timestamped before the "
                        "workflow was created (%s vs %s)" % (when, created))
        return ok("decided at %s, after the workflow was created" % when)

    def a_non_approval_carries_comments():
        ev = _completed_run()
        if ev is None:
            return fail("no completed run to check")
        review = ev.dig("workflow", "human_review", default={}) or {}
        decision = str(review.get("decision", "")).lower()
        comments = review.get("comments")
        if decision == "approve":
            return ok("approved, so no correction needed to be recorded")
        if not comments:
            return fail("the decision was %r but records no comments, so "
                        "the correction cannot be acted on" % decision)
        return ok("%s, with comments: %s" % (decision, str(comments)[:80]))

    def the_run_reached_completed():
        ev = _completed_run()
        if ev is None:
            return fail("no completed run to check")
        status = ev.dig("workflow", "status")
        if status != "completed":
            return fail("a human decision was recorded but the workflow "
                        "status is %r, not 'completed'" % status)
        history = ev.dig("workflow", "history", default=[]) or []
        events = {h.get("event") for h in history if isinstance(h, dict)}
        if "human_review_completed" not in events:
            return fail("the status is completed but the history records no "
                        "human_review_completed event")
        return ok("the run reached 'completed' and the history records it")

    return [
        Probe("ma_health", "availability",
              "Multi-Agent server answers /health", server_answers),
        Probe("ma_not_containerised", "availability",
              "Multi-Agent server is not a Compose service",
              not_a_compose_service),
        Probe("ma_workflow_route", "availability",
              "The workflow route is live", workflow_route_is_live),
        Probe("ma_reachable_from_feature", "availability",
              "Reachable from my feature through the backend",
              reachable_from_my_feature),

        Probe("ma_record", "workflow",
              "A workflow record exists and parses", a_record_exists),
        Probe("ma_three_agents", "workflow",
              "All three agents produced output", all_three_agents_ran),
        Probe("ma_structured", "workflow",
              "Agent output is structured, not prose",
              agent_output_is_structured),
        Probe("ma_history", "workflow",
              "The coordination log covers every stage",
              history_covers_every_stage),
        Probe("ma_history_order", "workflow",
              "The coordination log is in order", history_is_in_order),

        Probe("ma_plan_steps", "chain-of-custody",
              "The Planner set out steps", planner_produced_steps),
        Probe("ma_plan_gaps", "chain-of-custody",
              "The plan separates known from unknown",
              planner_separated_known_from_unknown),
        Probe("ma_worker_read_plan", "chain-of-custody",
              "The Worker used the plan", worker_used_the_plan),
        Probe("ma_worker_cited", "chain-of-custody",
              "The Worker cited the supplied evidence",
              worker_cited_the_evidence),
        Probe("ma_reviewer_read_work", "chain-of-custody",
              "The Reviewer judged the actual work",
              reviewer_judged_the_actual_work),
        Probe("ma_reviewer_reason", "chain-of-custody",
              "The review gives a recommendation and a reason",
              reviewer_gave_a_recommendation_with_a_reason),

        Probe("ma_human_decision", "human-review",
              "A human made a valid decision", a_human_decided),
        Probe("ma_human_timestamp", "human-review",
              "The decision is timestamped after the run",
              the_decision_is_timestamped),
        Probe("ma_human_comments", "human-review",
              "A non-approval carries comments",
              a_non_approval_carries_comments),
        Probe("ma_completed", "human-review",
              "The run reached completed", the_run_reached_completed),
    ]
