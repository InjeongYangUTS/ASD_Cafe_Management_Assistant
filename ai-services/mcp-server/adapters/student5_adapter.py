import os

import requests


STUDENT5_BACKEND_URL = os.getenv(
    "STUDENT5_BACKEND_URL",
    "http://localhost:8500",
).rstrip("/")

HTTP_TIMEOUT = float(os.getenv("MCP_HTTP_TIMEOUT", "10"))


class Student5AdapterError(Exception):
    """Raised when the Student 5 Payment backend cannot answer."""


def _get(path):
    try:
        response = requests.get(
            STUDENT5_BACKEND_URL + path,
            timeout=HTTP_TIMEOUT,
        )
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise Student5AdapterError(
            "The Student 5 Payment service is unavailable."
        ) from exc

    if response.status_code >= 400:
        message = data.get("error", "Student 5 Payment request failed.")
        raise Student5AdapterError(message)

    return data


def get_payments():
    return _get("/api/payments")


def get_payment(payment_id):
    return _get(f"/api/payments/{payment_id}")


def get_refunds():
    return _get("/api/refunds")
