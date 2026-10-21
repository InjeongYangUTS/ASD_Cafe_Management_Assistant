import json
import requests

from config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT


def create_plan(task, evidence=None):
    """Create a plan for the Worker Agent."""

    evidence = evidence or {}
    evidence_text = json.dumps(evidence, indent=2, ensure_ascii=False)

    
    prompt = f"""
You are the Planner Agent for the Cafe Management Assistant.

Your responsibility is to create a short, accurate plan for the
Worker Agent.

STRICT RULES:
1. Read the user's task carefully.
2. Examine all supplied evidence before creating the plan.
3. Clearly distinguish information that is provided from
   information that is missing.
4. Never describe provided information as missing.
5. Do not invent ingredients, quantities, prices or instructions.
6. Do not answer the user's task yourself.
7. Do not instruct the Worker to add information that is not
   supported by the evidence.
8. Keep the plan short and practical.
9. If the evidence already contains everything needed to answer
   the user's task, leave information_to_check as an empty list.
10. Do not suggest checking ingredients, equipment, quantities,
    or other details unless the user's task specifically requires them.
11. Worker steps must focus only on completing the user's task.
12. Do not assume that a recipe is incomplete just because
    additional information could exist.

User task:
{task}

Available evidence (JSON):
{evidence_text}

Return ONLY a valid JSON object with these three fields:

{{
    "available_information": ["Information supported by evidence"],
    "information_to_check": ["Information to verify or identify as missing"],
    "worker_steps": ["Step 1", "Step 2", "Step 3"]
}}

RULES FOR JSON OUTPUT:
1. Return JSON only, without Markdown code fences.
2. All three fields must contain lists of strings.
3. Do not invent facts or include unsupported information.
4. Keep each list concise.
"""

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json"
            },
            timeout=OLLAMA_TIMEOUT
        )

        response.raise_for_status()

    except requests.exceptions.Timeout as exc:
        raise RuntimeError(
            "Planner Agent timed out while waiting for Ollama."
        ) from exc

    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            "Planner Agent could not connect to Ollama."
        ) from exc

    except requests.exceptions.RequestException as exc:
        raise RuntimeError(
            "Planner Agent failed to communicate with Ollama."
        ) from exc

    result = response.json()

    plan = result.get("response", "").strip()

    if not plan:
        raise ValueError("Planner Agent returned an empty plan.")

    try:
        plan_data = json.loads(plan)
    except json.JSONDecodeError as exc:
        raise ValueError("Planner Agent returned invalid JSON.") from exc

    required_fields = (
        "available_information",
        "information_to_check",
        "worker_steps",
    )

    if not isinstance(plan_data, dict):
        raise ValueError("Planner Agent must return a JSON object.")

    for field in required_fields:
        value = plan_data.get(field)

        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            raise ValueError(
                f"Planner Agent returned an invalid '{field}' field."
            )

    return {
        "agent": "planner",
        "task": task,
        "plan": plan
    }
