
import requests

from config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT


def execute_task(task, plan, evidence=None):
    """Execute a task following the Planner Agent's plan."""

    evidence = evidence or {}

    prompt = f"""
You are the Worker Agent for a Cafe Management Assistant.

Your responsibilities:
1. Follow the Planner Agent's plan.
2. Use only the provided evidence.
3. Complete the user's requested task.
4. Clearly identify missing information.
5. Do not invent facts or claim actions you have not performed.

User task:
{task}

Planner's plan:
{plan}

Available evidence:
{evidence}

Produce a clear result based on the plan and evidence.
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
    output = result.get("response", "").strip()

    if not output:
        raise ValueError("Worker Agent returned an empty response.")

    return {
        "agent": "worker",
        "task": task,
        "output": output
    }
