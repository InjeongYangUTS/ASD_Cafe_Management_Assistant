import os

import requests

# The Order & Kitchen feature is reached through its BACKEND, not its
# database service. The backend owns the rules - the status lifecycle, the
# queue metrics, the price snapshots - so reading around it would hand a
# model rows without the meaning attached to them.
STUDENT4_BACKEND_URL = os.getenv(
    "STUDENT4_BACKEND_URL",
    "http://localhost:8400"
).rstrip("/")

HTTP_TIMEOUT = float(os.getenv("MCP_HTTP_TIMEOUT", "10"))


class Student4AdapterError(Exception):
    """Raised when the Student 4 order service cannot fulfil a request."""

    def __init__(self, message, status_code=502, detail=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail


def _get(path, params=None):
    try:
        response = requests.get(
            STUDENT4_BACKEND_URL + path,
            params=params,
            timeout=HTTP_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise Student4AdapterError(
            "The Student 4 order service is unavailable.",
            detail=str(exc),
        ) from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise Student4AdapterError(
            "The Student 4 order service returned unreadable data.",
            detail=str(exc),
        ) from exc

    if response.status_code >= 400:
        raise Student4AdapterError(
            data.get("error", "Student 4 order request failed."),
            status_code=response.status_code,
            detail=data,
        )

    return data


def get_orders(status=None, limit=100):
    params = {"limit": limit}
    if status:
        params["status"] = status
    return _get("/api/orders", params=params)


def get_order(order_id):
    return _get("/api/orders/%d" % order_id)


def get_kitchen_queue():
    return _get("/api/kitchen/queue")


def get_order_status(order_id):
    return _get("/api/order-status/%d" % order_id)
