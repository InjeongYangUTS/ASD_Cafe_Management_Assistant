import json
import requests

from config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT


def review_task(task, plan, worker_output, evidence=None):
    """Review the Worker's output against the plan and evidence."""

    evidence = evidence or {}
    evidence_text = json.dumps(evidence, indent=2, ensure_ascii=False)
    
    
    prompt = f"""
You are the Reviewer Agent for the Cafe Management Assistant.

Your job is to evaluate the Worker's response fairly and accurately.

IMPORTANT:
Read the ENTIRE Worker output before making your decision.

REVIEW RULES:
1. Compare the Worker's response directly with the user's task.
2. Check whether the response uses only the supplied evidence.
3. Check whether the Worker identified genuinely missing information.
4. Do not claim something is missing from the Worker output if it
   is already explicitly mentioned.
5. Do not reject a correct answer simply because it is concise.
6. Do not require additional information that the user did not request.
7. Identify specific factual errors or unsupported claims.
8. If the Worker correctly completes the task, recommend Approve.
9. Do not invent issues just to provide criticism.

User task:
{task}

Available evidence (JSON):
{evidence_text}

Planner's plan:
{plan}

Worker's complete output:
{worker_output}

Before making your recommendation, verify:
- Did the Worker answer the user's question?
- Did the Worker identify the supplied information correctly?
- Did the Worker identify missing information correctly?
- Are there any unsupported claims?

Return ONLY a valid JSON object with these fields:

{{
    "assessment": "A brief assessment of the Worker's response",
    "issues": [],
    "recommendation": "approve",
    "reason": "A brief explanation of the recommendation"
}}

JSON OUTPUT RULES:
1. Return JSON only, without Markdown code fences.
2. "assessment" must be a string.
3. "issues" must be a list of strings.
4. "recommendation" must be exactly one of:
   "approve", "revise", or "reject".
5. "reason" must be a string.
6. If there are no issues, return an empty issues list.
7. Recommend "approve" when the Worker correctly answers the task
   using only the supplied evidence.
8. Recommend "revise" when the answer contains correctable errors.
9. Recommend "reject" when the answer is fundamentally unsupported
   by the evidence or fails to address the task.
10. Do not invent issues or require information the user did not request.
"""



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

    result = response.json()
    review = result.get("response", "").strip()

    if not review:
        raise ValueError("Reviewer Agent returned an empty review.")

    try:
        review_data = json.loads(review)
    except json.JSONDecodeError as exc:
        raise ValueError("Reviewer Agent returned invalid JSON.") from exc

    if not isinstance(review_data, dict):
        raise ValueError("Reviewer Agent must return a JSON object.")

    for field in ("assessment", "reason"):
        if not isinstance(review_data.get(field), str):
            raise ValueError(
                f"Reviewer Agent returned an invalid '{field}' field."
            )

    issues = review_data.get("issues")

    if not isinstance(issues, list) or not all(
        isinstance(item, str) for item in issues
    ):
        raise ValueError("Reviewer Agent returned an invalid 'issues' field.")

    valid_recommendations = ("approve", "revise", "reject")

    if review_data.get("recommendation") not in valid_recommendations:
        raise ValueError(
            "Reviewer Agent returned an invalid recommendation."
        )

    return {
        "agent": "reviewer",
        "task": task,
        "review": review
    }
