import json
import os
import time
import uuid
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

AUDIT_PATH = os.environ.get("AI_AUDIT_PATH",
                            os.path.join(BASE_DIR, "logs", "ai-audit.jsonl"))


def _summary(mode, outcome):
    if mode == "rag":
        return {"confidence": outcome.get("confidence"),
                "sources": [source.get("document") for source in outcome.get("sources", [])]}
    return {"row_count": outcome.get("row_count"), "error": outcome.get("error")}


def record(mode, name, request_input, outcome, started):
    """Append one MCP or RAG invocation to the JSONL audit log."""
    entry = {
        "request_id": uuid.uuid4().hex,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": mode,
        "name": name,
        "input": request_input,
        "status": outcome.get("status"),
        "duration_ms": round((time.monotonic() - started) * 1000),
        "result": _summary(mode, outcome),
    }

    try:
        os.makedirs(os.path.dirname(AUDIT_PATH), exist_ok=True)
        with open(AUDIT_PATH, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    except OSError:
        pass

    return entry


def recent(limit=20):
    try:
        with open(AUDIT_PATH, encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError:
        return []

    return [json.loads(line) for line in lines[-limit:]][::-1]
