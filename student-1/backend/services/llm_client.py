import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_REVIEW_MODEL = os.getenv("OLLAMA_REVIEW_MODEL", "qwen2.5:0.5b")

AI_TIMEOUT = float(os.getenv("AI_TIMEOUT", 180))


class LLMClient:
    """Calls the local Ollama runtime with an approved open-source LLM."""

    def __init__(self, base_url=None, model=None, timeout=None):
        self.base_url = (base_url or OLLAMA_BASE_URL).rstrip("/")
        self.model = model or OLLAMA_MODEL
        self.timeout = timeout or AI_TIMEOUT

    def _client(self):
        return OpenAI(
            base_url=self.base_url,
            api_key="ollama",
            timeout=self.timeout,
        )

    def call_model(self, system_prompt, user_prompt, model_name=None,
                   max_tokens=220, temperature=0.1):
        """Return (text, error). Exactly one of the two is set."""
        model = model_name or self.model

        try:
            response = self._client().chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )

            content = response.choices[0].message.content

            if content and content.strip():
                return content.strip(), None

            return None, "%s returned an empty response" % model

        except Exception as exc:                      # noqa: BLE001
            return None, "%s unavailable or timed out (%s)" % (model, exc)

    def health(self):
        """Report reachability and which models the runtime actually has."""
        try:
            models = [item.id for item in self._client().models.list().data]
            return {
                "reachable": True,
                "url": self.base_url,
                "model": self.model,
                "installed_models": models,
                "model_installed": any(
                    name == self.model or name.startswith(self.model + ":")
                    for name in models
                ),
            }
        except Exception:                             # noqa: BLE001
            return {"reachable": False, "url": self.base_url,
                    "model": self.model, "installed_models": []}
