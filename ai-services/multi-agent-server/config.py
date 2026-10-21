import os

MULTI_AGENT_HOST = os.getenv("MULTI_AGENT_HOST", "0.0.0.0")
MULTI_AGENT_PORT = int(os.getenv("MULTI_AGENT_PORT", "5800"))

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434"
)

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))