"""
Student 4 (Stella Kwon) - Order & Kitchen Management
The Release 2 cloud baseline: AI services switched off.

The brief requires AI-Mode, MCP, RAG and the Multi-Agent server to be
DISABLED BY DEFAULT in the cloud deployment, while the ordering and
kitchen functions keep working. A flag sitting in a YAML file does not
achieve that - the code has to read it. These tests are what stop the
flag from being decorative:

    * with a flag off, the route returns without calling the service
      AT ALL (the stand-ins here raise if they are touched)
    * the health report says "off", not "down", because a deliberate
      baseline and an outage are different things
    * CRUD and the deterministic queue metrics are unaffected
    * docker-compose.cloud.yml really sets the four flags the code reads

No network: every client is replaced before a route is called.
"""

import importlib
import os
import sys

import pytest

STUDENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(STUDENT_DIR)
BACKEND_DIR = os.path.join(STUDENT_DIR, "backend")

ALL_FLAGS = ("AI_MODE_ENABLED", "MCP_ENABLED",
             "RAG_ENABLED", "MULTI_AGENT_ENABLED")


class Tripwire:
    """Stands in for a client. Any CALL on it fails the test.

    Reading `base_url` is allowed: the off-state message names the
    address the service would have been reached at, and quoting an
    address is not the same as dialling it.
    """

    def __init__(self, name, base_url="http://switched-off.test"):
        self.name = name
        self.base_url = base_url
        self.model = "none"

    def __getattr__(self, attribute):
        def explode(*args, **kwargs):
            raise AssertionError(
                "%s.%s() was called even though the service is switched off"
                % (self.name, attribute))
        return explode


ORDERS = {"orders": [
    {"id": 1, "order_number": "A-1001", "status": "PREPARING",
     "channel": "TAKEAWAY", "created_at": "2026-10-22 10:00:00",
     "item_count": 1,
     "items": [{"menu_name": "Latte", "quantity": 2,
                "station": "BAR", "prep_seconds": 90}]},
]}


def load_backend(**flags):
    """Import backend/app.py fresh with the given flag values."""
    previous = {name: os.environ.get(name) for name in ALL_FLAGS}
    for name in ALL_FLAGS:
        os.environ.pop(name, None)
    for name, value in flags.items():
        os.environ[name] = value

    sys.path.insert(0, BACKEND_DIR)
    for name in ("app", "ai_services", "ai", "clients"):
        sys.modules.pop(name, None)

    module = importlib.import_module("app")
    module.app.config.update(TESTING=True)

    # Nothing in these tests may reach a network.
    module.db.list_orders = lambda **kwargs: ORDERS

    return module, previous


def unload(previous):
    sys.path.remove(BACKEND_DIR)
    for name in ("app", "ai_services", "ai", "clients"):
        sys.modules.pop(name, None)
    for name, value in previous.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


@pytest.fixture()
def baseline():
    """The cloud baseline: every AI service off, every client a tripwire."""
    module, previous = load_backend(
        AI_MODE_ENABLED="false", MCP_ENABLED="false",
        RAG_ENABLED="false", MULTI_AGENT_ENABLED="false")

    module.mcp = Tripwire("mcp")
    module.rag = Tripwire("rag")
    module.multi_agent = Tripwire("multi_agent")
    module.ollama.generate = Tripwire("ollama").generate

    yield module
    unload(previous)


@pytest.fixture()
def local():
    """The local default: no flags set at all."""
    module, previous = load_backend()
    yield module
    unload(previous)


# =====================================================================
# Defaults
# =====================================================================

def test_everything_is_on_when_no_flag_is_set(local):
    """Local behaviour must not change. The flags default to on."""
    assert local.AI_MODE_ENABLED is True
    assert local.MCP_ENABLED is True
    assert local.RAG_ENABLED is True
    assert local.MULTI_AGENT_ENABLED is True


@pytest.mark.parametrize("value,expected", [
    ("false", False), ("False", False), ("0", False), ("no", False),
    ("off", False), ("", False),
    ("true", True), ("True", True), ("1", True), ("yes", True),
    ("on", True), ("enabled", True),
])
def test_the_flag_reads_the_usual_spellings(value, expected):
    module, previous = load_backend(MCP_ENABLED=value)
    try:
        assert module.MCP_ENABLED is expected, value
    finally:
        unload(previous)


# =====================================================================
# Each service, switched off
# =====================================================================

def test_ai_mode_off_does_not_call_the_model(baseline):
    """The analysis still arrives - computed, not generated."""
    response = baseline.app.test_client().post("/api/ai/kitchen-analysis")
    body = response.get_json()

    assert response.status_code == 200
    assert body["mode"] == "heuristic"
    assert body["ai_mode_enabled"] is False
    assert "switched off" in body["note"]
    # The part that does not need a model is all still there.
    assert body["metrics"]["open_order_count"] == 1
    assert body["analysis"]["congestion"]


def test_mcp_off_returns_without_calling_the_server(baseline):
    client = baseline.app.test_client()

    catalogue = client.get("/api/ai/mcp").get_json()
    assert catalogue["disabled"] is True
    assert catalogue["flag"] == "MCP_ENABLED"
    assert catalogue["tools"] == []

    called = client.post("/api/ai/mcp", json={"tool": "get_orders"}).get_json()
    assert called["disabled"] is True


def test_rag_off_returns_without_calling_the_server(baseline):
    body = baseline.app.test_client().post(
        "/api/ai/rag", json={"question": "anything"}).get_json()

    assert body["disabled"] is True
    # The panel branches on status, so the off state has to carry one.
    assert body["status"] == "unavailable"
    assert body["answer"] is None


def test_multi_agent_off_returns_without_calling_the_server(baseline):
    client = baseline.app.test_client()

    started = client.post("/api/ai/multi-agent/workflows",
                          json={"task": "anything"}).get_json()
    assert started["disabled"] is True

    fetched = client.get("/api/ai/multi-agent/workflows/wf-1").get_json()
    assert fetched["disabled"] is True

    decided = client.post("/api/ai/multi-agent/workflows/wf-1/human-review",
                          json={"decision": "approve"}).get_json()
    assert decided["disabled"] is True


def test_a_switched_off_service_is_reported_off_not_down(baseline):
    """The health report must not cry outage over a deliberate baseline.

    The clients are tripwires here, so this also proves the health check
    does not call four servers it was told not to use - which on a cloud
    box would be four network timeouts on every probe.
    """
    report = baseline.app.test_client().get("/api/health").get_json()

    for name in ("mcp", "rag", "multi_agent"):
        dependency = report["dependencies"][name]
        assert dependency["enabled"] is False, name
        assert "disabled by configuration" in dependency["note"], name

    assert report["dependencies"]["ollama"]["enabled"] is False

    switches = report["ai_services"]
    assert {n: s["enabled"] for n, s in switches.items()} == {
        "ai_mode": False, "mcp": False, "rag": False, "multi_agent": False}


def test_the_ordering_functions_are_unaffected(baseline):
    """The whole point of the baseline: the application still works."""
    response = baseline.app.test_client().get("/api/orders")
    assert response.status_code == 200
    assert response.get_json()["orders"][0]["order_number"] == "A-1001"


# =====================================================================
# The flags in the file are the flags in the code
# =====================================================================

def test_the_cloud_baseline_sets_every_flag_the_code_reads():
    """Ties docker-compose.cloud.yml to app.py.

    A flag renamed in one place and not the other would leave a service
    quietly enabled in the cloud while the file still looked right.
    """
    path = os.path.join(REPO_ROOT, "docker-compose.cloud.yml")
    with open(path, encoding="utf-8") as handle:
        text = handle.read()

    block = text.split("student-4-backend:", 1)
    assert len(block) == 2, "docker-compose.cloud.yml has no student-4-backend"
    block = block[1].split("\n  student-", 1)[0]

    for flag in ALL_FLAGS:
        assert '%s: "false"' % flag in block, \
            "%s is not turned off for student-4-backend in the cloud" % flag
