import os
import requests

RAG_SERVER_URL = os.getenv(
    "RAG_SERVER_URL",
    "http://host.docker.internal:5800"
)


def query_rag(question):
    """
    Send a query to the shared RAG server.

    Temporary mock mode is used until the shared RAG server
    is available.
    """

    rag_enabled = os.getenv("RAG_ENABLED", "false").lower() == "true"

    if not rag_enabled:
        return {
            "answer": (
                "Mock grounded response for Student 3. "
                "The shared RAG server is not connected yet."
            ),
            "sources": [
                "Student 3 Inventory & Restocking documentation"
            ],
            "confidence": "LOW",
            "insufficient_context": False
        }

    response = requests.post(
        f"{RAG_SERVER_URL}/query",
        json={
            "query": question,
            "student": "student-3"
        },
        timeout=30
    )

    response.raise_for_status()

    return response.json()