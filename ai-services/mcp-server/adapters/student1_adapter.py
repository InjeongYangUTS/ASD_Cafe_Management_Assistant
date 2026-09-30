import os

import requests

STUDENT1_BACKEND_URL = os.getenv(
    "STUDENT1_BACKEND_URL",
    "http://localhost:8100"
).rstrip("/")

HTTP_TIMEOUT = float(os.getenv("MCP_HTTP_TIMEOUT", "10"))


class Student1AdapterError(Exception):
    """Raised when the Customer Feedback backend cannot answer."""


def _get(path, params=None):
    try:
        response = requests.get(STUDENT1_BACKEND_URL + path,
                                params=params, timeout=HTTP_TIMEOUT)
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise Student1AdapterError(
            "The Customer Feedback backend is unavailable.") from exc

    if response.status_code >= 400:
        raise Student1AdapterError(
            data.get("error", "Customer Feedback request failed."))

    return data


def get_summary():
    return _get("/api/summary")


def get_reviews(limit, sentiment=None, needs_reply=False):
    params = {"limit": limit, "sort": "newest"}
    if sentiment:
        params["sentiment"] = sentiment
    if needs_reply:
        params["needs_reply"] = 1
    return _get("/api/feedback", params)["feedback"]
