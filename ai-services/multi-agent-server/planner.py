
import requests

from config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT


def create_plan(task, evidence=None):
    """Create a plan for the Worker Agent."""

    evidence = evidence or {}

    prompt = f"""
You are the Planner Agent for a Cafe Management Assistant.

Your responsibility is to:
1. Understand the user's task.
2. Identify the evidence required.
3. Create clear steps for the Worker Agent.
4. Do not invent information that is not provided.

User task:
{task}

Available evidence:
{evidence}

Return a clear, numbered plan.
"""

    response = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False
        },
        timeout=OLLAMA_TIMEOUT
    )

    response.raise_for_status()

    result = response.json()

    plan = result.get("response", "").strip()

    if not plan:
        raise ValueError("Planner Agent returned an empty plan.")

    return {
        "agent": "planner",
        "task": task,
        "plan": plan
    }
