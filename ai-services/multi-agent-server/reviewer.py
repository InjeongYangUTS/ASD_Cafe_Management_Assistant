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

Return EXACTLY this format:

Assessment:
<Brief assessment>

Issues:
<Specific issues, or None>

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
