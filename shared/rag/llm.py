import requests

from config import (
    OLLAMA_URL,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT
)


def generate_response(prompt):
    """Generate a response using the local Ollama model."""

    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("A non-empty prompt is required.")

    url = f"{OLLAMA_URL.rstrip('/')}/api/generate"

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt.strip(),
        "stream": False
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=OLLAMA_TIMEOUT
        )

        response.raise_for_status()

        data = response.json()

        answer = data.get("response", "").strip()

        if not answer:
            raise RuntimeError(
                "Ollama returned an empty response."
            )

        return answer

    except requests.RequestException as error:
        raise RuntimeError(
            f"Failed to communicate with Ollama: {error}"
        ) from error