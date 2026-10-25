
import importlib.util
import os
import sys
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
APP_PATH = BACKEND_DIR / "app.py"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AI_MODE_ENABLED", "false")
    monkeypatch.setenv("MCP_ENABLED", "false")
    monkeypatch.setenv("RAG_ENABLED", "false")
    monkeypatch.setenv("MULTI_AGENT_ENABLED", "false")

    spec = importlib.util.spec_from_file_location(
        "student3_cloud_test_app",
        APP_PATH
    )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    module.app.config["TESTING"] = True

    with module.app.test_client() as test_client:
        yield test_client


@pytest.mark.parametrize(
    "method,path,payload",
    [
        (
            "POST",
            "/api/ai/restock-recommendation",
            {"question": "What should I restock?"}
        ),
        (
            "GET",
            "/api/mcp/test",
            None
        ),
        (
            "POST",
            "/api/rag/query",
            {"question": "What is low in stock?"}
        ),
        (
            "POST",
            "/api/multi-agent/workflows",
            {"task": "Review low-stock items"}
        ),
        (
            "GET",
            "/api/multi-agent/workflows/test-id",
            None
        ),
        (
            "POST",
            "/api/multi-agent/workflows/test-id/human-review",
            {"decision": "approve"}
        ),
    ]
)
def test_cloud_ai_services_disabled(
    client, method, path, payload
):
    response = client.open(
        path,
        method=method,
        json=payload
    )

    assert response.status_code == 403

    data = response.get_json()

    assert data["success"] is False
    assert data["disabled"] is True


def test_service_flags_are_disabled(client):
    response = client.get("/api/mcp/test")

    assert response.status_code == 403
    assert "MCP" in response.get_json()["message"]
