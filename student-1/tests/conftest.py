"""Shared pytest fixtures. Uses a throwaway SQLite file, so no containers are needed."""

import importlib
import os
import sys
from pathlib import Path

import pytest

STUDENT_DIR = Path(__file__).resolve().parent.parent

# Import by plain module name, as the services do inside their containers.
for path in (STUDENT_DIR / "database", STUDENT_DIR / "backend"):
    sys.path.insert(0, str(path))


@pytest.fixture()
def db_app(tmp_path, monkeypatch):
    """
    The database microservice, backed by a fresh SQLite file.

    The module is reloaded per test because it reads FEEDBACK_DB_PATH at
    import time; without the reload every test would share the first
    test's database and pass or fail depending on ordering.
    """
    monkeypatch.setenv("FEEDBACK_DB_PATH", str(tmp_path / "feedback.db"))

    sys.path.insert(0, str(STUDENT_DIR / "database"))
    import app as database_app

    importlib.reload(database_app)
    database_app.ensure_schema()

    return database_app


@pytest.fixture()
def db_client(db_app):
    db_app.app.config["TESTING"] = True
    return db_app.app.test_client()


@pytest.fixture()
def seeded_client(db_client):
    """A database client holding three reviews with known values."""
    reviews = [
        {"customer_id": 1, "customer_name": "Test Customer", "rating": 5,
         "title": "Best flat white", "comment": "The flat white was perfect.",
         "category": "DRINK"},
        {"customer_id": 2, "customer_name": "Daniel Park", "rating": 2,
         "title": "Slow", "comment": "Waited 25 minutes for a latte.",
         "category": "WAIT_TIME"},
        {"customer_id": 1, "customer_name": "Test Customer", "rating": 3,
         "title": "Mixed", "comment": "Good coffee, dirty table.",
         "category": "CLEANLINESS"},
    ]

    for review in reviews:
        response = db_client.post("/db/feedback", json=review)
        assert response.status_code == 201, response.get_json()

    return db_client


@pytest.fixture()
def menu_vocabulary():
    """The menu vocabulary, loaded from the real menu_terms.json."""
    sys.path.insert(0, str(STUDENT_DIR / "backend"))
    from services.database_api import MenuClient

    # A dead port, so the client uses its documented fallback.
    client = MenuClient(base_url="http://127.0.0.1:9")
    return client._fallback
