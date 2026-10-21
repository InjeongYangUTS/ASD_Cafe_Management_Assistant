
import requests

from config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT


def review_task(task, plan, worker_output, evidence=None):
    """Review the Worker's output against the plan and evidence."""

    evidence = evidence or {}

    prompt = f"""
You are the Reviewer Agent for a Cafe Management Assistant.

Your responsibilities:
1. Check whether the Worker followed the Planner's plan.
2. Check whether the output addresses the user's task.
3. Identify unsupported claims or missing evidence.
4. Identify errors, risks and areas for improvement.
5. Provide a clear recommendation for human review.

Do not invent information.

User task:
{task}

Planner's plan:
{plan}

Worker's output:
{worker_output}

Available evidence:
{evidence}

Return your review using this format:

Assessment:
<Your assessment>

Issues:
<Any problems identified, or None>

Recommendation:
<Approve, Revise, or Reject>

Reason:
<Explain your recommendation>
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
    review = result.get("response", "").strip()

    if not review:
        raise ValueError("Reviewer Agent returned an empty review.")

    return {
        "agent": "reviewer",
        "task": task,
        "review": review
    }
