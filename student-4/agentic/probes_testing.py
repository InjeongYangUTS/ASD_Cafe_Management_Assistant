"""
Student 4 (Stella Kwon) - Shared Agentic Loop
Release 2: Testing Review mode.

Reviews the two bodies of testing evidence the team produces around a
commit, written against what is actually in the repository:

    .pre-commit-config.yaml         ruff-security, detect-secrets, pip-audit
    pyproject.toml                  [tool.ruff.lint] select
    .secrets.baseline               the detect-secrets baseline
    scripts/security/audit_dependencies.py
    tests/release2/post_commit/test_api_*.py     the endpoint tests
    reports/release2/student-N-test-results.md   raw pytest output
    reports/release2/student-N-test-audit.jsonl  {student, status, timestamp}

The distinction the whole mode is built around is between a scan that
ran and a scan that passed, and between a test that exists and a test
that ran after a push. A hook installed but never selecting security
rules looks green and protects nothing; five report files that each say
PASS prove nothing if no workflow invoked them. So the probes read the
configuration and the pytest output, not just the summary line.

Where a finding is real but accepted, the per-file-ignores in
pyproject.toml carry a written reason. That is a decision, not a
failure, and this mode treats it as one - but it checks the reason is
there.
"""

import os
import re

from evidence import (read_text, relative, repo_glob, repo_path)

AREAS = ["configuration", "security-scan", "endpoint-tests", "reporting"]

STUDENTS = ("student-1", "student-2", "student-3", "student-4", "student-5")

REQUIRED_HOOKS = ("ruff", "detect-secrets", "pip-audit")


def build_testing_probes(ok, fail, Probe):
    """Return the Testing Review pack. ok/fail/Probe come from loop.py."""

    def pytest_reports():
        return repo_glob("reports/release2/student-*-test-results.md")

    def audit_rows():
        rows = {}
        for path in repo_glob("reports/release2/student-*-test-audit.jsonl"):
            name = os.path.basename(path).split("-test-audit")[0]
            lines = [ln for ln in (read_text(relative(path)) or "").splitlines()
                     if ln.strip()]
            rows[name] = (path, lines)
        return rows

    # ---------------- configuration ----------------

    def hook_config_names_all_three():
        text = read_text(".pre-commit-config.yaml")
        if text is None:
            return fail("no .pre-commit-config.yaml at the repository root, "
                        "so no scan runs when anyone commits")
        lowered = text.lower().replace("_", "-")
        missing = [h for h in REQUIRED_HOOKS if h not in lowered]
        if missing:
            return fail("the pre-commit config does not reference %s. The "
                        "brief names Ruff security rules, detect-secrets and "
                        "pip-audit or equivalents." % ", ".join(missing))
        return ok("the pre-commit config defines hooks for all three "
                  "required scanners")

    def ruff_selects_security_rules():
        """Ruff only finds security issues if the S rules are selected.

        This is the failure this probe exists for: a repository can run
        Ruff on every commit, pass every time, and never have looked at
        a security rule, because the default rule set is style.
        """
        for candidate in ("pyproject.toml", "ruff.toml", ".ruff.toml",
                          ".pre-commit-config.yaml"):
            text = read_text(candidate)
            if not text:
                continue
            if re.search(r"(?m)^\s*select\s*=[^\n]*\bS\b", text) or \
               re.search(r"--select[^\n]{0,60}\bS\b", text) or \
               "flake8-bandit" in text:
                return ok("Ruff's security rules (S) are selected in %s"
                          % candidate)
        return fail("Ruff is configured but its security rules are not "
                    "selected. Without select = [\"S\"] it lints style and "
                    "finds no security issues at all.")

    def suppressions_carry_a_reason():
        """Every silenced rule has to say why in writing.

        An ignore with a comment is an accepted risk; one without is an
        unexamined one, and they look identical in a scan report.

        A comment introduces a GROUP of entries, not just the next line
        - one "# Reviewed: these services bind all interfaces so Docker
        can publish their ports" covers the dozen S104 entries under it.
        An earlier version of this check looked three lines back and
        reported ten well-documented suppressions as unexplained. The
        rule is: a comment opens a justified block, a blank line closes
        it.
        """
        text = read_text("pyproject.toml")
        if text is None:
            return fail("no pyproject.toml to read the Ruff configuration "
                        "from")

        in_block = False
        explained = False
        unexplained = []

        for line in text.splitlines():
            stripped = line.strip()

            if stripped.startswith("[tool.ruff.lint.per-file-ignores]"):
                in_block = True
                continue
            if in_block and stripped.startswith("["):
                break
            if not in_block:
                continue

            if not stripped:
                explained = False
                continue
            if stripped.startswith("#"):
                explained = True
                continue
            if "=" not in stripped:
                continue

            # S101 is `assert`, which pytest requires; silencing it in a
            # test file needs no explanation.
            if '"S101"' in stripped and "test" in stripped.lower():
                continue
            if not explained:
                unexplained.append(stripped[:60])

        if unexplained:
            return fail("%d Ruff suppression(s) carry no written "
                        "justification: %s"
                        % (len(unexplained), "; ".join(unexplained[:2])))
        return ok("every non-trivial Ruff suppression sits under a written "
                  "justification")

    def secrets_baseline_exists():
        text = read_text(".secrets.baseline")
        if text is None:
            return fail("no .secrets.baseline - detect-secrets has nothing "
                        "to compare against, so it cannot tell a new secret "
                        "from a known false positive")
        if '"results"' not in text:
            return fail(".secrets.baseline does not look like a "
                        "detect-secrets baseline")
        return ok("a detect-secrets baseline is committed")

    def dependency_audit_script_exists():
        path = repo_path("scripts", "security", "audit_dependencies.py")
        if not os.path.exists(path):
            return fail("the pre-commit config runs "
                        "scripts/security/audit_dependencies.py but that "
                        "file does not exist, so the dependency hook cannot "
                        "run")
        text = read_text("scripts/security/audit_dependencies.py") or ""
        if "pip" not in text.lower() and "audit" not in text.lower():
            return fail("the dependency audit script does not reference "
                        "pip-audit")
        return ok("the dependency audit script is present and invokes "
                  "pip-audit")

    # ---------------- security scan ----------------

    def every_hook_is_wired_to_something_runnable():
        text = read_text(".pre-commit-config.yaml") or ""
        broken = []
        for match in re.finditer(r"entry:\s*(.+)", text):
            entry = match.group(1).strip()
            first = entry.split()[0]
            if first in ("python", "python3"):
                script = entry.split()[1] if len(entry.split()) > 1 else ""
                if script and not os.path.exists(repo_path(script)):
                    broken.append(script)
        if broken:
            return fail("these hook entries point at files that do not "
                        "exist: %s" % ", ".join(broken))
        return ok("every hook entry resolves to something that exists")

    def hooks_do_not_skip_the_repository():
        """An exclude that swallows the project is a disabled scan."""
        text = read_text(".pre-commit-config.yaml") or ""
        for match in re.finditer(r"exclude:\s*'([^']+)'", text):
            pattern = match.group(1)
            for fragment in ("student-", "shared/", "ai-services",
                             r"^\.\*", r"\.py"):
                if fragment in pattern:
                    return fail("a hook excludes %r, which covers "
                                "application source - the scan would skip "
                                "the code it exists to check" % pattern)
        return ok("hook excludes cover fixtures and virtualenvs only")

    def ruff_runs_against_the_shared_config():
        text = read_text(".pre-commit-config.yaml") or ""
        match = re.search(r"entry:\s*ruff[^\n]*", text)
        if not match:
            return fail("no ruff entry in the pre-commit config")
        entry = match.group(0)
        if "--config" not in entry and "pyproject" not in entry:
            return fail("the Ruff hook does not name a config file, so it "
                        "may not pick up the security rules in "
                        "pyproject.toml: %s" % entry.strip()[:70])
        return ok("the Ruff hook runs against the shared config: %s"
                  % entry.split("entry:")[1].strip()[:60])

    # ---------------- endpoint tests ----------------

    def every_student_has_endpoint_tests():
        files = repo_glob("tests/release2/post_commit/test_api_*.py")
        if not files:
            return fail("no tests under tests/release2/post_commit/")
        if len(files) < len(STUDENTS):
            return fail("only %d endpoint test file(s) for %d students: %s"
                        % (len(files), len(STUDENTS),
                           ", ".join(relative(f) for f in files)))
        return ok("%d endpoint test files, one per service: %s"
                  % (len(files),
                     ", ".join(os.path.basename(f).replace("test_api_", "")
                               .replace(".py", "") for f in files)))

    def each_file_tests_two_functions():
        files = repo_glob("tests/release2/post_commit/test_api_*.py")
        if not files:
            return fail("no endpoint test files to read")
        short = []
        for path in files:
            text = read_text(relative(path)) or ""
            functions = set(re.findall(r"(?m)^def (test_\w+)", text))
            if len(functions) < 2:
                short.append("%s has %d" % (os.path.basename(path),
                                            len(functions)))
        if short:
            return fail("the brief requires two endpoint functions each: %s"
                        % "; ".join(short))
        return ok("every endpoint test file defines at least two test "
                  "functions")

    def the_tests_assert_something():
        """A test that calls an endpoint without asserting always passes."""
        files = repo_glob("tests/release2/post_commit/test_api_*.py")
        if not files:
            return fail("no endpoint test files to read")
        weak = []
        for path in files:
            text = read_text(relative(path)) or ""
            for block in re.split(r"(?m)^def ", text)[1:]:
                name = block.split("(")[0]
                if not name.startswith("test_"):
                    continue
                if "assert" not in block:
                    weak.append("%s::%s" % (os.path.basename(path), name))
        if weak:
            return fail("these tests make no assertion, so they pass "
                        "whatever the endpoint returns: %s"
                        % ", ".join(weak[:4]))
        return ok("every endpoint test makes at least one assertion")

    def workflows_invoke_the_endpoint_tests():
        """The report can claim anything; the workflow file is the proof."""
        silent = []
        for student in STUDENTS:
            matches = repo_glob(".github/workflows/%s.yml" % student)
            if not matches:
                silent.append("%s (no workflow)" % student)
                continue
            text = read_text(relative(matches[0])) or ""
            if "post_commit" not in text and "release2" not in text:
                silent.append(student)
        if silent:
            return fail("these workflows do not run the Release 2 endpoint "
                        "tests: %s" % ", ".join(silent))
        return ok("all five workflows invoke the Release 2 endpoint tests")

    def the_pytest_output_shows_passes():
        reports = pytest_reports()
        if not reports:
            return fail("no reports/release2/student-*-test-results.md - "
                        "nobody has captured a test run yet")
        problems = []
        for path in reports:
            text = read_text(relative(path)) or ""
            if re.search(r"\b\d+ failed", text) or "ERROR" in text:
                problems.append("%s reports failures" % os.path.basename(path))
            elif not re.search(r"\b(\d+) passed", text):
                problems.append("%s has no pass count"
                                % os.path.basename(path))
        if problems:
            return fail("; ".join(problems))
        counts = []
        for path in reports:
            m = re.search(r"\b(\d+) passed", read_text(relative(path)) or "")
            counts.append(int(m.group(1)) if m else 0)
        return ok("%d report(s), %d passing tests in total, no failures"
                  % (len(reports), sum(counts)))

    def the_output_came_from_ci():
        """post-commit means it ran on a runner, not on a laptop."""
        reports = pytest_reports()
        if not reports:
            return fail("no pytest output to read")
        local = []
        for path in reports:
            text = read_text(relative(path)) or ""
            if "hostedtoolcache" not in text and "/home/runner" not in text \
                    and "github" not in text.lower():
                local.append(os.path.basename(path))
        if local:
            return fail("these reports show no sign of running on a CI "
                        "runner, so there is nothing showing the tests ran "
                        "after a push rather than locally: %s"
                        % ", ".join(local))
        return ok("every pytest report shows a GitHub runner path")

    # ---------------- reporting ----------------

    def every_student_filed_an_audit_row():
        rows = audit_rows()
        if not rows:
            return fail("no reports/release2/student-*-test-audit.jsonl")
        missing = [s for s in STUDENTS if s not in rows]
        if missing:
            return fail("no test audit row for %s" % ", ".join(missing))
        empty = [name for name, (_p, lines) in rows.items() if not lines]
        if empty:
            return fail("these audit files are empty: %s" % ", ".join(empty))
        return ok("all five students filed a test audit row")

    def audit_rows_agree_with_the_pytest_output():
        """The summary and the raw output have to tell the same story.

        An audit row saying PASS next to a pytest log showing failures is
        the one combination nobody would notice by reading either alone.
        """
        import json as _json
        rows = audit_rows()
        if not rows:
            return fail("no audit rows to check")
        disagree = []
        for student, (path, lines) in rows.items():
            try:
                row = _json.loads(lines[-1])
            except (ValueError, IndexError):
                disagree.append("%s: unreadable audit row" % student)
                continue
            claimed = str(row.get("status", "")).upper()
            output = read_text("reports/release2/%s-test-results.md" % student)
            if output is None:
                disagree.append("%s: claims %s but filed no pytest output"
                                % (student, claimed))
                continue
            actually_failed = bool(re.search(r"\b\d+ failed", output))
            if claimed == "PASS" and actually_failed:
                disagree.append("%s: audit says PASS, pytest output shows "
                                "failures" % student)
            if claimed != "PASS" and not actually_failed:
                disagree.append("%s: audit says %s, pytest output shows no "
                                "failures" % (student, claimed))
        if disagree:
            return fail("; ".join(disagree))
        return ok("every audit row agrees with the pytest output beside it")

    def audit_rows_are_timestamped():
        import json as _json
        rows = audit_rows()
        if not rows:
            return fail("no audit rows to check")
        undated = []
        for student, (_path, lines) in rows.items():
            try:
                row = _json.loads(lines[-1])
            except (ValueError, IndexError):
                undated.append(student)
                continue
            if not row.get("timestamp"):
                undated.append(student)
        if undated:
            return fail("these audit rows carry no timestamp, so they cannot "
                        "be tied to a point in the history: %s"
                        % ", ".join(undated))
        return ok("every audit row is timestamped")

    return [
        Probe("t_hook_config", "configuration",
              "The pre-commit config names all three scanners",
              hook_config_names_all_three),
        Probe("t_ruff_security", "configuration",
              "Ruff's security rules are selected",
              ruff_selects_security_rules),
        Probe("t_suppressions", "configuration",
              "Every suppression carries a written reason",
              suppressions_carry_a_reason),
        Probe("t_baseline", "configuration",
              "A detect-secrets baseline is committed",
              secrets_baseline_exists),
        Probe("t_audit_script", "configuration",
              "The dependency audit script exists",
              dependency_audit_script_exists),

        Probe("t_hooks_runnable", "security-scan",
              "Every hook entry resolves", every_hook_is_wired_to_something_runnable),
        Probe("t_excludes", "security-scan",
              "Excludes do not skip application source",
              hooks_do_not_skip_the_repository),
        Probe("t_ruff_config", "security-scan",
              "Ruff runs against the shared config",
              ruff_runs_against_the_shared_config),

        Probe("t_files_exist", "endpoint-tests",
              "Every service has an endpoint test file",
              every_student_has_endpoint_tests),
        Probe("t_two_each", "endpoint-tests",
              "Two endpoint functions tested each",
              each_file_tests_two_functions),
        Probe("t_assertions", "endpoint-tests",
              "Every endpoint test asserts something",
              the_tests_assert_something),
        Probe("t_workflows_run", "endpoint-tests",
              "Workflows invoke the endpoint tests",
              workflows_invoke_the_endpoint_tests),
        Probe("t_pytest_passes", "endpoint-tests",
              "The pytest output shows passes, no failures",
              the_pytest_output_shows_passes),
        Probe("t_from_ci", "endpoint-tests",
              "The output came from a CI runner", the_output_came_from_ci),

        Probe("t_audit_rows", "reporting",
              "Every student filed an audit row",
              every_student_filed_an_audit_row),
        Probe("t_audit_agrees", "reporting",
              "Audit rows agree with the pytest output",
              audit_rows_agree_with_the_pytest_output),
        Probe("t_audit_dated", "reporting",
              "Audit rows are timestamped", audit_rows_are_timestamped),
    ]
