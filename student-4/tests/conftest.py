"""Shared pytest fixtures for the Student 4 test suite."""

import importlib
import os
import sys
import tempfile

import pytest

STUDENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_DIR = os.path.join(STUDENT_DIR, "database")
BACKEND_DIR = os.path.join(STUDENT_DIR, "backend")


@pytest.fixture()
def db_app():
    """The database microservice wired to a throwaway SQLite file."""
    handle, path = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    os.remove(path)

    os.environ["ORDER_DB_PATH"] = path
    sys.path.insert(0, DATABASE_DIR)

    if "app" in sys.modules:
        del sys.modules["app"]

    module = importlib.import_module("app")
    module.DB_PATH = path
    module.ensure_schema()

    module.app.config.update(TESTING=True)

    yield module.app

    sys.path.remove(DATABASE_DIR)
    del sys.modules["app"]
    os.environ.pop("ORDER_DB_PATH", None)

    if os.path.exists(path):
        os.remove(path)


@pytest.fixture()
def db_client(db_app):
    return db_app.test_client()


@pytest.fixture()
def ai_module():
    """The AI-Mode helper module (pure functions, no network)."""
    sys.path.insert(0, BACKEND_DIR)

    if "ai" in sys.modules:
        del sys.modules["ai"]

    module = importlib.import_module("ai")

    yield module

    sys.path.remove(BACKEND_DIR)
    del sys.modules["ai"]


def sample_order_payload(**overrides):
    payload = {
        "channel": "DINE_IN",
        "table_number": "T9",
        "customer_name": "Test Customer",
        "staff_name": "Test Staff",
        "items": [
            {
                "menu_id": 2,
                "menu_name": "Latte",
                "unit_price": 4.50,
                "quantity": 2,
                "station": "BAR",
                "prep_seconds": 90,
            },
            {
                "menu_id": 15,
                "menu_name": "Croissant",
                "unit_price": 5.00,
                "quantity": 1,
                "station": "PASTRY",
                "prep_seconds": 40,
            },
        ],
    }
    payload.update(overrides)
    return payload


@pytest.fixture()
def frontend_app():
    """The frontend microservice, with no backend behind it."""
    FRONTEND_DIR = os.path.join(STUDENT_DIR, "frontend")
    os.environ.setdefault("SHARED_DIR", FRONTEND_DIR)

    sys.path.insert(0, FRONTEND_DIR)

    if "app" in sys.modules:
        del sys.modules["app"]

    module = importlib.import_module("app")
    module.app.config.update(TESTING=True)

    yield module.app

    sys.path.remove(FRONTEND_DIR)
    del sys.modules["app"]
