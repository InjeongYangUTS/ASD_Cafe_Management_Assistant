import os
import uuid

import requests


MULTI_AGENT_URL = os.getenv("MULTI_AGENT_URL", "http://host.docker.internal:5800").rstrip("/")
MULTI_AGENT_TIMEOUT = int(os.getenv("MULTI_AGENT_TIMEOUT", "420"))


class MultiAgentError(Exception):
    def __init__(self, message, status_code=503):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _call_server(method, path, payload=None):
    try:
        response = requests.request(
            method,
            f"{MULTI_AGENT_URL}{path}",
            json=payload,
            timeout=MULTI_AGENT_TIMEOUT,
        )
    except requests.Timeout as exc:
        raise MultiAgentError("Multi-Agent workflow timed out.", 504) from exc
    except requests.RequestException as exc:
        raise MultiAgentError("Multi-Agent Server is unavailable.", 503) from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise MultiAgentError("Multi-Agent Server returned invalid JSON.", 502) from exc

    if not isinstance(data, dict):
        raise MultiAgentError("Unexpected Multi-Agent response.", 502)

    if response.status_code >= 400:
        message = data.get("error", "Multi-Agent request failed.")
        raise MultiAgentError(message, response.status_code)
    return data


def _checked_id(workflow_id):
    try:
        return str(uuid.UUID(workflow_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise MultiAgentError("Invalid workflow ID.", 400) from exc


def start_inventory_workflow(task, inventory_items):
    return _call_server("POST", "/workflows", {
        "task": task,
        "evidence": {
            "feature": "Student 3 - Inventory & Restocking",
            "low_stock_items": inventory_items,
        },
    })


def get_inventory_workflow(workflow_id):
    return _call_server("GET", f"/workflows/{_checked_id(workflow_id)}")


def submit_inventory_review(workflow_id, decision, comments=""):
    return _call_server("POST", f"/workflows/{_checked_id(workflow_id)}/human-review", {
        "decision": decision,
        "comments": comments,
    })
