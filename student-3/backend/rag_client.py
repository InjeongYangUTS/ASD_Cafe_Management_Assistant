import os
import requests

RAG_SERVER_URL = os.getenv(
    "RAG_URL",
    "http://host.docker.internal:5600"
).rstrip("/")


def query_rag(question):
    response = requests.post(
        f"{RAG_SERVER_URL}/query",
        json = {"question": question},
        timeout = 150
    )
    
    data = response.json()
    
    if not response.ok:
        raise RuntimeError(
            data.get("error", "Shared RAG request failed.")
        )
        
    return {
        "answer": data.get("answer") or "",
        "sources": data.get("sources", []),
        "confidence": data.get("confidence", "UNKNOWN"),
        "insufficient_context": (
            data.get("status") == "insufficient_context"
        )
    }