import os

import requests


STUDENT_5_BACKEND_URL = os.getenv("STUDENT_5_BACKEND_URL", "http://localhost:8500")


def test_payments_exist():
    response = requests.get(f"{STUDENT_5_BACKEND_URL}/api/payments", timeout=5)
    assert response.status_code == 200
    payments = response.json()
    assert len(payments) > 0


def test_payment_by_id():
    response = requests.get(f"{STUDENT_5_BACKEND_URL}/api/payments/1", timeout=5)
    assert response.status_code == 200
    assert response.json()["id"] == 1
