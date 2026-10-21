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
{evidence_text}

Return ONLY a valid JSON object with these fields:

{{
    "result": "A concise answer based strictly on the evidence",
    "missing_information": [],
    "evidence_used": []
}}

JSON OUTPUT RULES:
1. Return JSON only, without Markdown code fences.
2. "result" must be a string.
3. "missing_information" must be a list of strings.
4. "evidence_used" must be a list of strings.
5. If nothing is missing for the user's task, return an empty
   missing_information list.
6. Do not introduce ingredients, quantities, equipment or
   other information that is not required by the user's task.
7. Identify which supplied evidence supports the result.
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
            "Worker Agent timed out while waiting for Ollama."
        ) from exc

    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            "Worker Agent could not connect to Ollama."
        ) from exc

    except requests.exceptions.RequestException as exc:
        raise RuntimeError(
            "Worker Agent failed to communicate with Ollama."
        ) from exc

    result = response.json()
    output = result.get("response", "").strip()

    if not output:
        raise ValueError("Worker Agent returned an empty response.")

    try:
        output_data = json.loads(output)
    except json.JSONDecodeError as exc:
        raise ValueError("Worker Agent returned invalid JSON.") from exc

    if not isinstance(output_data, dict):
        raise ValueError("Worker Agent must return a JSON object.")

    if not isinstance(output_data.get("result"), str):
        raise ValueError("Worker Agent returned an invalid 'result' field.")

    for field in ("missing_information", "evidence_used"):
        value = output_data.get(field)

        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            raise ValueError(
                f"Worker Agent returned an invalid '{field}' field."
            )

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

Return ONLY a valid JSON object with these fields:

{{
    "result": "The corrected answer based strictly on the evidence",
    "missing_information": [],
    "evidence_used": []
}}

JSON OUTPUT RULES:
1. Return JSON only, without Markdown code fences.
2. "result" must be a string.
3. "missing_information" must be a list of strings.
4. "evidence_used" must be a list of strings.
5. If nothing is missing for the user's task, return an empty
   missing_information list.
6. Apply the human feedback only when it is supported by evidence.
7. Do not invent information to satisfy the human feedback.
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
            "Worker Agent revision timed out while waiting for Ollama."
        ) from exc

    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            "Worker Agent revision could not connect to Ollama."
        ) from exc

    except requests.exceptions.RequestException as exc:
        raise RuntimeError(
            "Worker Agent revision failed to communicate with Ollama."
        ) from exc

    output = response.json().get("response", "").strip()

    if not output:
        raise ValueError("Worker Agent returned an empty revision.")

    try:
        output_data = json.loads(output)
    except json.JSONDecodeError as exc:
        raise ValueError("Worker Agent returned invalid JSON.") from exc

    if not isinstance(output_data, dict):
        raise ValueError("Worker Agent must return a JSON object.")

    if not isinstance(output_data.get("result"), str):
        raise ValueError("Worker Agent returned an invalid 'result' field.")

    for field in ("missing_information", "evidence_used"):
        value = output_data.get(field)

        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            raise ValueError(
                f"Worker Agent returned an invalid '{field}' field."
            )

    return {
        "agent": "worker",
        "task": task,
        "output": output
    }

