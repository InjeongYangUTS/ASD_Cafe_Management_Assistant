"""
Student 4 (Stella Kwon) - Shared Agentic Loop
Release 2: evidence helpers.

The Release 1 modes probed running services. The three Release 2 modes
review EVIDENCE the rest of the team produces, so this module exists to
answer one question honestly: is a piece of evidence absent because
nobody has produced it yet, or present but wrong? Those findings belong
to different people, so the probes report them differently.

Everything here is written against the shapes that are actually in the
repository, not against a format I invented. The locations:

    evidence/release2/multi-agent/*.json    a workflow run, wrapped as
                                            {server, status, workflow}
    evidence/release2/validation-*.json     the team's own integration
                                            validation, a list of
                                            {section, check, expected,
                                             actual, result}
    reports/release2/student-N-test-results.md    raw pytest output
    reports/release2/student-N-test-audit.jsonl   {student, status, timestamp}
    tests/release2/post_commit/test_api_*.py      the endpoint tests
"""

import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
STUDENT_DIR = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(STUDENT_DIR)

EVIDENCE_ROOT = os.path.join(REPO_ROOT, "evidence", "release2")
REPORTS_ROOT = os.path.join(REPO_ROOT, "reports", "release2")


def repo_path(*parts):
    return os.path.join(REPO_ROOT, *parts)


def repo_glob(pattern):
    return sorted(glob.glob(os.path.join(REPO_ROOT, pattern)))


def relative(path):
    if not path:
        return "(none)"
    try:
        return os.path.relpath(path, REPO_ROOT)
    except ValueError:
        return path


def read_text(*parts):
    path = repo_path(*parts)
    if not os.path.exists(path):
        return None
    # utf-8-sig, not utf-8: a file written on Windows often carries a
    # byte order mark, and refusing to read a file every other tool
    # reads would be pedantry rather than review.
    with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
        return handle.read()


# =====================================================================
# One piece of evidence
# =====================================================================

class Evidence:
    """A JSON evidence file, and what is wrong with it if anything.

    A probe asks for evidence, calls .problem() first, and fails with
    whatever that returns. That keeps the same four error branches out
    of forty-odd probes.
    """

    def __init__(self, path, label, expected):
        self.path = path
        self.label = label
        self.expected = expected
        self.data = None
        self.error = None
        self.notes = []

    def problem(self):
        """A reason this evidence cannot be reviewed, or None."""
        if self.path is None:
            return ("%s has not been produced yet - nothing matching %s"
                    % (self.label, self.expected))
        if self.error:
            return ("%s exists at %s but could not be read: %s"
                    % (self.label, relative(self.path), self.error))
        return None

    def dig(self, *path, default=None):
        """Walk a nested path, returning default rather than raising.

        Deliberately NOT called get(). An earlier version was, and
        callers who wrote the dict.get shape - ev.get("status", "") -
        silently got data["status"][""] instead of a default, which
        resolves to None and stringifies to "none". Three probes then
        compared against the wrong value while passing their own tests.
        The name is the fix: dig() does not invite a positional default.
        """
        node = self.data
        for key in path:
            if isinstance(node, dict) and key in node:
                node = node[key]
            elif isinstance(node, list) and isinstance(key, int) \
                    and -len(node) <= key < len(node):
                node = node[key]
            else:
                return default
        return node


def newest_first(paths):
    """Sort by modification time, most recent first, ties broken by name.

    The name tiebreak is not decoration. A fresh clone stamps every file
    with the checkout time, so on a CI runner the mtimes are identical
    and the order would otherwise be whatever the filesystem felt like -
    which would make the same commit review a different record on
    different runs.
    """
    return sorted(paths,
                  key=lambda p: (-os.path.getmtime(p), os.path.basename(p)))


def load_json(pattern, label, newest=True):
    """Find and parse one JSON evidence file by repository-relative glob.

    `newest` means newest by mtime, not last by filename. An earlier
    version sorted by name and called the result "newest", which quietly
    reviewed whichever record sorted last in the alphabet - so the run I
    had just captured was ignored in favour of one from a week before.
    """
    matches = repo_glob(pattern)
    if matches:
        ordered = newest_first(matches)
        path = ordered[0] if newest else ordered[-1]
    else:
        path = None
    ev = Evidence(path, label, pattern)

    if path is None:
        return ev

    # A byte order mark makes a file invalid JSON by the letter of the
    # spec, and most parsers ignore it anyway. Failing nine checks over
    # an encoding artefact would hide whatever the file actually says,
    # so it is read and the mark is reported as a note instead.
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
        if raw.startswith(b"\xef\xbb\xbf"):
            ev.notes.append("the file carries a UTF-8 byte order mark, "
                            "which strict JSON parsers reject")
        ev.data = json.loads(raw.decode("utf-8-sig"))
    except ValueError as exc:
        ev.error = "not valid JSON (%s)" % exc
    except OSError as exc:
        ev.error = str(exc)

    return ev


def inner_json(value, default=None):
    """Parse a field that holds JSON as a string.

    The multi-agent server stores each agent's output as a JSON string
    inside the workflow record, so plan, worker_output and review all
    arrive double-encoded. An agent that produced prose instead of JSON
    is a finding, not a crash, so this returns the default and lets the
    probe say so.
    """
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str) or not value.strip():
        return default
    try:
        return json.loads(value)
    except ValueError:
        return default


# =====================================================================
# Shared checks
# =====================================================================

STOP = {
    "the", "and", "that", "this", "with", "from", "they", "have", "were",
    "been", "will", "would", "could", "should", "their", "there", "which",
    "about", "into", "then", "than", "them", "these", "those", "each",
    "also", "more", "most", "some", "such", "only", "other", "when",
}


def words(text):
    """Content words, for comparing one stage's output with another's."""
    if isinstance(text, (dict, list)):
        text = json.dumps(text)
    return {w for w in re.findall(r"[a-z]{4,}", str(text).lower())
            if w not in STOP}


def overlap(source, derived):
    """How much of source's vocabulary carries into derived, 0.0 - 1.0."""
    a, b = words(source), words(derived)
    if not a:
        return None
    return len(a & b) / len(a)


def iso_ordered(timestamps):
    cleaned = [t for t in timestamps if isinstance(t, str) and t]
    return cleaned == sorted(cleaned)


SECRET_PATTERNS = [
    (re.compile(r"AKIA[0-9A-Z]{16}"), "an AWS access key id"),
    (re.compile(r"(?i)\bsecret[_-]?key\s*[:=]\s*['\"][^'\"]{12,}"), "a secret key literal"),
    (re.compile(r"(?i)\bpassword\s*[:=]\s*['\"][^'\"]{6,}"), "a password literal"),
    (re.compile(r"(?i)\bapi[_-]?key\s*[:=]\s*['\"][^'\"]{12,}"), "an API key literal"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "a private key"),
]

PLACEHOLDER = re.compile(
    r"(?i)(\$\{|\$\(|\{\{|<[a-z_-]+>|xxx+|changeme|your[_-]|placeholder|example\.com|secrets\.)")


def looks_like_a_secret(text):
    """Literal credentials in text, ignoring placeholders and references.

    Deliberately cruder than detect-secrets, which is Injeong's job.
    This only has to catch a credential pasted into a deployment script,
    so it skips anything reading as a variable reference, a GitHub
    secrets expression, or a placeholder.
    """
    hits = []
    for line in text.splitlines():
        if PLACEHOLDER.search(line):
            continue
        for pattern, description in SECRET_PATTERNS:
            if pattern.search(line):
                hits.append(description)
                break
    return sorted(set(hits))
