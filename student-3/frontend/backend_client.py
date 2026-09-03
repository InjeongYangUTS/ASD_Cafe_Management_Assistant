import os

import requests


BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8300").rstrip("/")
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "10"))
AI_HTTP_TIMEOUT = float(os.getenv("AI_HTTP_TIMEOUT", "120"))


class BackendError(Exception):
    def __init__(self, message, status_code=502, detail=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail


def call_backend(method, path, timeout=None, **kwargs):
    try:
        response = requests.request(method, BACKEND_URL + path, timeout=timeout or HTTP_TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        raise BackendError("The inventory backend service is unavailable.", detail=str(exc)) from exc
    try:
        data = response.json()
    except ValueError as exc:
        raise BackendError("The inventory backend returned unreadable data.", detail=str(exc)) from exc
    if response.status_code >= 400:
        raise BackendError(data.get("error", "Backend request failed."), response.status_code, data)
    return data
