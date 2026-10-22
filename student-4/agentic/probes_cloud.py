"""
Student 4 (Stella Kwon) - Shared Agentic Loop
Release 2: Cloud Deployment Review mode.

Reviews the evidence that the integrated application was deployed to the
team's chosen cloud platform, and supports the final human release
decision.

Written against what is actually in the repository:

    deploy/aws/deploy.sh, setup-ec2.sh, smoke-test.sh, README.md
    .github/workflows/cloud-deployment.yml   validate -> deploy (needs:)
    docker-compose.cloud.yml                 MCP_ENABLED / RAG_ENABLED /
                                             MULTI_AGENT_ENABLED = "false"

Two things make this mode different from the other two.

First, the brief sets a baseline the required deployment must hold to:
AI-Mode, MCP, RAG and the Multi-Agent server are DISABLED by default in
the cloud. That is a requirement a team can fail by succeeding too hard.
Enabling them is worth bonus marks, as a separate profile. So the
baseline probes read the deployment configuration rather than take a
report's word for it, and they check the flags by the names this
repository actually uses.

Second, this mode ends in a decision, not a score. Its job is to
assemble what a person needs in order to say ship or do not ship; the
verdict it emits is a recommendation, and the human sign-off is recorded
separately.
"""

import os
import re

from evidence import (load_json, looks_like_a_secret, read_text, relative,
                      repo_glob)

AREAS = ["artefacts", "deployment", "baseline", "release-decision"]

# The flag names this repository uses. Checked in both orders because a
# team half-way through a rename has some of each, and a probe that only
# knows one spelling reports a clean baseline that is not clean.
AI_FLAGS = (
    ("ai_mode", ("AI_MODE_ENABLED", "ENABLE_AI_MODE", "AI_ENABLED")),
    ("mcp", ("MCP_ENABLED", "ENABLE_MCP")),
    ("rag", ("RAG_ENABLED", "ENABLE_RAG")),
    ("multi_agent", ("MULTI_AGENT_ENABLED", "ENABLE_MULTI_AGENT")),
)

CONFIG_GLOBS = ("docker-compose.cloud.yml", "deploy/*/*.sh", "deploy/*/*.yml",
                ".github/workflows/cloud-deployment.yml", ".env.cloud*")

TRUE = ("true", "1", "yes", "on", "enabled")


def _config_files():
    paths = []
    for pattern in CONFIG_GLOBS:
        paths.extend(repo_glob(pattern))
    return [p for p in paths if os.path.isfile(p)]


def build_cloud_probes(ok, fail, Probe):
    """Return the Cloud Deployment review pack. ok/fail/Probe from loop.py."""

    def report():
        return load_json("evidence/release2/cloud/deployment-report.json",
                         "The cloud deployment report")

    def decision():
        return load_json("evidence/release2/cloud/release-decision.json",
                         "The human release decision")

    # ---------------- artefacts ----------------

    def deployment_workflow_exists():
        text = read_text(".github/workflows/cloud-deployment.yml")
        if text is None:
            return fail("no .github/workflows/cloud-deployment.yml - the "
                        "brief names this file specifically")
        platforms = [p for p in ("aws", "azure") if p in text.lower()]
        if not platforms:
            return fail("cloud-deployment.yml names neither AWS nor Azure, "
                        "so it is not deploying anywhere identifiable")
        return ok("cloud-deployment.yml present, targeting %s"
                  % "/".join(platforms).upper())

    def deployment_is_gated():
        """A deploy that fires before validation is not a gate."""
        text = read_text(".github/workflows/cloud-deployment.yml")
        if text is None:
            return fail("cloud-deployment.yml not found")
        if re.search(r"(?m)^\s*needs\s*:", text):
            needs = re.search(r"(?m)^\s*needs\s*:\s*(.+)", text).group(1)
            return ok("the deploy job declares needs: %s, so it runs only "
                      "after that job succeeds" % needs.strip())
        if re.search(r"(?i)workflow_run", text):
            return ok("the workflow is triggered by workflow_run, so it "
                      "follows another workflow's result")
        return fail("cloud-deployment.yml has no needs: and no workflow_run "
                    "trigger, so deployment is not gated on validation")

    def deployment_scripts_are_reusable():
        """Reusable means parameterised, not a transcript of one session."""
        scripts = [p for p in repo_glob("deploy/*/*.sh") if os.path.isfile(p)]
        if not scripts:
            return fail("no deployment scripts under deploy/ - the brief "
                        "asks for reusable deployment scripts or "
                        "Infrastructure as Code")
        hardcoded = []
        for path in scripts:
            text = read_text(relative(path)) or ""
            if not re.search(r"\$\{?[A-Z_]{3,}|\$\d|getopts|--[a-z-]+\)", text):
                hardcoded.append(os.path.basename(path))
        if len(hardcoded) == len(scripts):
            return fail("%d deployment script(s) but none reads a parameter "
                        "or an environment variable, so they redeploy only "
                        "the environment they were written against: %s"
                        % (len(scripts), ", ".join(hardcoded)))
        return ok("%d deployment script(s), %d parameterised"
                  % (len(scripts), len(scripts) - len(hardcoded)))

    def scripts_fail_loudly():
        """A deploy script without set -e reports success after failing."""
        scripts = [p for p in repo_glob("deploy/*/*.sh") if os.path.isfile(p)]
        if not scripts:
            return fail("no deployment scripts to check")
        lax = []
        for path in scripts:
            text = read_text(relative(path)) or ""
            if not re.search(r"(?m)^\s*set\s+-[a-z]*e", text):
                lax.append(os.path.basename(path))
        if lax:
            return fail("these scripts do not set -e, so a failed step "
                        "part-way through still exits 0 and the workflow "
                        "reports a successful deployment: %s"
                        % ", ".join(lax))
        return ok("every deployment script exits on the first failure")

    def no_credentials_in_artefacts():
        paths = _config_files() + [p for p in repo_glob("deploy/*/*")
                                   if os.path.isfile(p)]
        if not paths:
            return fail("no deployment artefacts to check")
        offenders = []
        for path in set(paths):
            text = read_text(relative(path))
            if text is None:
                continue
            hits = looks_like_a_secret(text)
            if hits:
                offenders.append("%s (%s)" % (relative(path), hits[0]))
        if offenders:
            return fail("credentials look committed in %s"
                        % "; ".join(offenders[:3]))
        return ok("%d deployment artefact(s) checked, no committed "
                  "credentials" % len(set(paths)))

    def a_smoke_test_exists():
        """Something has to check the deployment after it lands."""
        scripts = repo_glob("deploy/*/smoke-test.sh")
        if not scripts:
            return fail("no smoke test under deploy/ - nothing verifies the "
                        "deployment once it is up")
        text = read_text(".github/workflows/cloud-deployment.yml") or ""
        if "smoke" not in text.lower():
            return fail("a smoke test exists but cloud-deployment.yml never "
                        "runs it, so a broken deployment still reports "
                        "success")
        return ok("a smoke test exists and the deployment workflow runs it")

    # ---------------- deployment ----------------

    def report_exists():
        ev = report()
        problem = ev.problem()
        if problem:
            return fail(problem)
        missing = [f for f in ("platform", "deployed_at", "frontend_url",
                               "status")
                   if f not in (ev.data or {})]
        if missing:
            return fail("%s is missing %s"
                        % (relative(ev.path), ", ".join(missing)))
        return ok("reviewing %s - %s, deployed %s"
                  % (relative(ev.path), ev.dig("platform"),
                     ev.dig("deployed_at")))

    def deployment_succeeded():
        ev = report()
        if ev.problem():
            return fail(ev.problem())
        status = str(ev.dig("status", default="")).lower()
        if status not in ("success", "succeeded", "ok", "deployed"):
            return fail("the deployment report records status %r" % status)
        run = ev.dig("workflow_run") or ev.dig("run_url")
        if not run:
            return fail("the report records no workflow run, so nothing "
                        "ties it to an actual GitHub Actions deployment")
        return ok("deployment succeeded, run recorded")

    def frontend_was_reached():
        ev = report()
        if ev.problem():
            return fail(ev.problem())
        url = ev.dig("frontend_url")
        if not url or not str(url).startswith("http"):
            return fail("frontend_url is missing or is not a URL")
        code = ev.dig("frontend_check", "status_code")
        if code is None:
            return fail("the report gives a frontend URL but records no "
                        "check against it, so nobody has shown it answers")
        if int(code) >= 400:
            return fail("the deployed frontend answered HTTP %s" % code)
        return ok("%s answered HTTP %s" % (url, code))

    def crud_was_verified_in_the_cloud():
        ev = report()
        if ev.problem():
            return fail(ev.problem())
        crud = ev.dig("crud_checks", default=[]) or []
        if not crud:
            return fail("the report records no CRUD checks. Criterion 7 is "
                        "about the deployed application's CRUD functions "
                        "working, so that has to be demonstrated.")
        failed = [c.get("operation") for c in crud
                  if isinstance(c, dict)
                  and str(c.get("result", "")).lower() not in
                  ("pass", "passed", "ok")]
        if failed:
            return fail("these CRUD checks did not pass in the cloud: %s"
                        % ", ".join(str(f) for f in failed))
        operations = {str(c.get("operation", "")).lower() for c in crud
                      if isinstance(c, dict)}
        for required in ("create", "read", "update", "delete"):
            if required not in operations:
                return fail("no %s check recorded - all four CRUD "
                            "operations need to be shown" % required)
        return ok("all four CRUD operations verified in the cloud")

    # ---------------- baseline ----------------

    def every_ai_service_has_a_flag():
        """A service with no flag is not disabled, it is unmanaged.

        This repository names three of the four
        (MCP_ENABLED, RAG_ENABLED, MULTI_AGENT_ENABLED). If AI-Mode has
        no flag anywhere, the baseline cannot be asserted for it, and
        that is a finding rather than a pass.
        """
        files = _config_files()
        if not files:
            return fail("no cloud deployment configuration found")
        blob = "\n".join(read_text(relative(p)) or "" for p in files)
        unmanaged = [service for service, names in AI_FLAGS
                     if not any(n in blob for n in names)]
        if unmanaged:
            return fail("no enable/disable flag anywhere in the cloud "
                        "configuration for: %s. The baseline cannot be "
                        "asserted for a service nothing switches."
                        % ", ".join(unmanaged))
        return ok("all four AI services have a flag in the cloud "
                  "configuration")

    def baseline_is_disabled_in_config():
        files = _config_files()
        if not files:
            return fail("no cloud deployment configuration found")
        turned_on = []
        for path in files:
            text = read_text(relative(path)) or ""
            for service, names in AI_FLAGS:
                for name in names:
                    for match in re.finditer(
                            r"%s\s*[:=]\s*[\"']?(\w+)" % re.escape(name),
                            text):
                        if match.group(1).lower() in TRUE:
                            turned_on.append("%s=%s in %s"
                                             % (name, match.group(1),
                                                relative(path)))
        if turned_on:
            return fail("the required cloud deployment must keep AI-Mode, "
                        "MCP, RAG and Multi-Agent disabled by default, but "
                        "the configuration enables: %s"
                        % "; ".join(turned_on[:3]))
        return ok("%d cloud config file(s) checked, no AI service enabled "
                  "by default" % len(files))

    def the_report_agrees_with_the_config():
        """Report and config have to tell the same story."""
        ev = report()
        if ev.problem():
            return fail(ev.problem())
        services = ev.dig("services", default={}) or {}
        claimed_on = [name for name in services
                      if str(services[name]).lower() in TRUE]
        if claimed_on:
            return fail("the deployment report says these are enabled in "
                        "the required deployment: %s. Enabling them is "
                        "bonus work and belongs to a separate profile."
                        % ", ".join(claimed_on))
        if not services:
            return fail("the report does not state whether the AI services "
                        "are enabled, so the baseline cannot be confirmed "
                        "from it")
        return ok("the report and the configuration agree: all AI services "
                  "disabled")

    def bonus_is_a_separate_profile():
        ev = report()
        if ev.problem():
            return fail(ev.problem())
        bonus = ev.dig("bonus")
        if bonus is None:
            return ok("no bonus profile claimed, so the baseline stands "
                      "alone")
        if not isinstance(bonus, dict) or not (bonus.get("profile")
                                               or bonus.get("deployment")):
            return fail("a bonus profile is claimed but does not name which "
                        "deployment it refers to. It has to be separate "
                        "from the required baseline.")
        return ok("bonus profile recorded separately: %s"
                  % str(bonus.get("profile") or bonus.get("deployment"))[:60])

    # ---------------- release decision ----------------

    def a_human_made_the_decision():
        ev = decision()
        problem = ev.problem()
        if problem:
            return fail(problem)
        verdict = str(ev.dig("decision", default="")).lower().replace("-", "_")
        if verdict not in ("go", "no_go", "hold"):
            return fail("release decision %r is not one of go, no_go, hold"
                        % ev.dig("decision"))
        who, when = ev.dig("decided_by"), ev.dig("decided_at")
        if not who or not when:
            return fail("the release decision does not record who made it "
                        "and when, so it is not auditable")
        return ok("%s by %s at %s" % (verdict.upper(), who, when))

    def the_decision_cites_the_review():
        """A sign-off that ignores the review is a rubber stamp."""
        ev = decision()
        if ev.problem():
            return fail(ev.problem())
        basis = ev.dig("based_on") or ev.dig("review_log") or ev.dig("evidence")
        if not basis:
            return fail("the release decision names no evidence. The brief "
                        "has this mode supporting the decision, which means "
                        "the decision should cite the review it read.")
        return ok("the decision cites: %s" % str(basis)[:80])

    def a_no_go_names_its_blockers():
        ev = decision()
        if ev.problem():
            return fail(ev.problem())
        verdict = str(ev.dig("decision", default="")).lower()
        if verdict == "go":
            return ok("released, so there are no blocking issues to record")
        blockers = ev.dig("blockers") or ev.dig("reason")
        if not blockers:
            return fail("the decision was %r but records no blocking issue, "
                        "so nobody knows what would change it" % verdict)
        return ok("%s, blocked by: %s" % (verdict, str(blockers)[:80]))

    return [
        Probe("c_workflow", "artefacts",
              "cloud-deployment.yml exists and names a platform",
              deployment_workflow_exists),
        Probe("c_gated", "artefacts",
              "Deployment is gated on validation", deployment_is_gated),
        Probe("c_reusable", "artefacts",
              "Deployment scripts are parameterised",
              deployment_scripts_are_reusable),
        Probe("c_set_e", "artefacts",
              "Scripts exit on the first failure", scripts_fail_loudly),
        Probe("c_no_secrets", "artefacts",
              "No credentials in deployment artefacts",
              no_credentials_in_artefacts),
        Probe("c_smoke", "artefacts",
              "A smoke test exists and runs", a_smoke_test_exists),

        Probe("c_report", "deployment",
              "The deployment report exists and parses", report_exists),
        Probe("c_succeeded", "deployment",
              "The deployment succeeded and links its run",
              deployment_succeeded),
        Probe("c_frontend", "deployment",
              "The deployed frontend was reached", frontend_was_reached),
        Probe("c_crud", "deployment",
              "All four CRUD operations verified in the cloud",
              crud_was_verified_in_the_cloud),

        Probe("c_flags_exist", "baseline",
              "Every AI service has a flag", every_ai_service_has_a_flag),
        Probe("c_disabled", "baseline",
              "No AI service is enabled by default",
              baseline_is_disabled_in_config),
        Probe("c_report_agrees", "baseline",
              "The report agrees with the configuration",
              the_report_agrees_with_the_config),
        Probe("c_bonus_separate", "baseline",
              "Bonus work is a separate profile", bonus_is_a_separate_profile),

        Probe("c_human", "release-decision",
              "A human made the release decision",
              a_human_made_the_decision),
        Probe("c_cites", "release-decision",
              "The decision cites the review", the_decision_cites_the_review),
        Probe("c_blockers", "release-decision",
              "A no-go names its blockers", a_no_go_names_its_blockers),
    ]
