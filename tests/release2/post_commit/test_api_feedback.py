import os

import requests


STUDENT_1_BACKEND_URL = os.getenv("STUDENT_1_BACKEND_URL", "http://localhost:8100")


def test_feedback_exist():
    response = requests.get(f"{STUDENT_1_BACKEND_URL}/api/feedback", timeout=5)
    assert response.status_code == 200
    feedback = response.json()["feedback"]
    assert len(feedback) > 0


def test_feedback_by_id():
    response = requests.get(f"{STUDENT_1_BACKEND_URL}/api/feedback/1", timeout=5)
    assert response.status_code == 200
    assert response.json()["id"] == 1
