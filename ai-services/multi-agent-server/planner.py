
import requests

from config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT


def create_plan(task, evidence=None):
    """Create a plan for the Worker Agent."""

    evidence = evidence or {}

    
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

User task:
{task}

Available evidence:
{evidence}

Return your response using EXACTLY this format:

Available Information:
<Briefly list the information already provided>

Information to Check:
<Identify what needs checking against the user's task>

Worker Steps:
1. Identify the relevant information already in the evidence.
2. Check what information is genuinely missing.
3. Produce a concise answer using only the evidence.
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
