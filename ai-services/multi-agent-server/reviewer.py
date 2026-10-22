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
10. The Planner's plan is a checklist of intended work, NOT evidence
    of recipe facts.
11. Use the supplied evidence JSON as the source of truth when
    checking the Worker's factual claims.
12. Do not treat something listed under "Information To Check"
    as information that is actually present in the recipe.
13. If individual ingredient quantities and units are provided,
    do not incorrectly claim those quantities are missing.
14. Do not require a combined ingredient total unless the user's
    task explicitly requests one.
15. Do not add quantities with incompatible units, such as
    grams and millilitres.
16. Recommend "revise" only when there is a genuine error,
    unsupported claim, or relevant omission.
17. Evaluate the Worker's response primarily against the
    original user task and supplied database evidence.
18. Do not penalise the Worker for ignoring Planner steps
    that introduce requirements outside the original task.
19. Do not treat the Planner's information_to_check list
    as proof that a field is required or missing.
20. A statement that information is absent can be verified
    by checking whether that information exists in the evidence.
21. Only flag missing information as an issue when the
    original task requires that information.
22. Do not approve claims that ingredient quantities meet
    a standard unless the standard is supplied in the evidence.
23. When reviewing a corrected response, assess the latest
    Worker output independently rather than repeating an
    earlier assessment.
24. Recommend "revise" for genuine factual errors,
    unsupported claims or failure to address the user's task,
    not for optional recipe enhancements.

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
            "Reviewer Agent timed out while waiting for Ollama."
        ) from exc

    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            "Reviewer Agent could not connect to Ollama."
        ) from exc

    except requests.exceptions.RequestException as exc:
        raise RuntimeError(
            "Reviewer Agent failed to communicate with Ollama."
        ) from exc

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
