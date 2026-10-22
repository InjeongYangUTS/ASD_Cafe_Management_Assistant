import os

import requests


STUDENT_4_BACKEND_URL = os.getenv("STUDENT_4_BACKEND_URL", "http://localhost:8400")


def test_orders_exist():
    response = requests.get(f"{STUDENT_4_BACKEND_URL}/api/orders", timeout=5)
    assert response.status_code == 200
    orders = response.json()["orders"]
    assert len(orders) > 0


def test_order_by_id():
    response = requests.get(f"{STUDENT_4_BACKEND_URL}/api/orders/1", timeout=5)
    assert response.status_code == 200
    assert response.json()["id"] == 1
