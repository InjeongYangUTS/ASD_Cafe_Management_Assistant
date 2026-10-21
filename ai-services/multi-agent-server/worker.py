import json
import requests

from config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT


def execute_task(task, plan, evidence=None):
    """Execute a task following the Planner Agent's plan."""

    evidence = evidence or {}
    evidence_text = json.dumps(evidence, indent=2, ensure_ascii=False)
    
    prompt = f"""
You are the Worker Agent for the Cafe Management Assistant.

Your task is to follow the Planner Agent's plan using ONLY the
evidence provided below.

STRICT RULES:
1. Use only information explicitly present in the evidence.
2. Do not add ingredients, quantities, ratios, prices or instructions
   that are not in the evidence.
3. Do not use general knowledge to fill missing information.
4. If information is missing, clearly state that it is not provided.
5. Do not claim to have performed actions you have not performed.
6. Do not repeat the entire plan in your response.
7. Keep the response clear, concise and relevant to the user's task.

User task:
{task}

Planner's plan:
{plan}

Available evidence (JSON):
{evidence}

Return your response using this format:

Result:
<Your answer based strictly on the evidence>

Missing Information:
<Information that is missing, or None>

Evidence Used:
<Briefly identify which supplied evidence supports your answer>
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

def revise_task(task, plan, previous_output, feedback, evidence=None):
    """Revise the Worker's output using human feedback."""

    evidence = evidence or {}
    evidence_text = json.dumps(evidence, indent=2, ensure_ascii=False)

    prompt = f"""
You are the Worker Agent for the Cafe Management Assistant.

A human reviewer has requested corrections to your previous output.

STRICT RULES:
1. Follow the human reviewer's feedback.
2. Use ONLY the supplied evidence.
3. Remove unsupported claims, quantities, ratios and ingredients.
4. Do not invent missing information.
5. Keep the revised answer concise and clear.
6. If the feedback requests information not in the evidence,
   explain that the information is unavailable.

User task:
{task}

Planner's plan:
{plan}

Previous Worker output:
{previous_output}

Human feedback:
{feedback}

Available evidence (JSON):
{evidence_text}

Return your revised response using this format:

Result:
<Corrected answer>

Missing Information:
<Missing information, or None>

Evidence Used:
<Supporting evidence>
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

    output = response.json().get("response", "").strip()

    if not output:
        raise ValueError("Worker Agent returned an empty revision.")

    return {
        "agent": "worker",
        "task": task,
        "output": output
    }

