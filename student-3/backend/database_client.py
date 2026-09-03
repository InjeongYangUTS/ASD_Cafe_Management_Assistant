import os

import requests


DATABASE_URL = os.getenv("DB_SERVICE_URL", "http://localhost:7300").rstrip("/")
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "10"))


class DatabaseError(Exception):
    def __init__(self, message, status_code=502, detail=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail


def call_database(method, path, **kwargs):
    try:
        response = requests.request(method, DATABASE_URL + path, timeout=HTTP_TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        raise DatabaseError("The inventory database service is unavailable.", detail=str(exc)) from exc
    try:
        data = response.json()
    except ValueError as exc:
        raise DatabaseError("The inventory database service returned unreadable data.", detail=str(exc)) from exc
    if response.status_code >= 400:
        raise DatabaseError(data.get("error", "Database request failed."), response.status_code, data)
    return data
