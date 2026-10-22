import os

import requests


STUDENT_3_BACKEND_URL = os.getenv("STUDENT_3_BACKEND_URL", "http://localhost:8300")


def test_inventory_exist():
    response = requests.get(f"{STUDENT_3_BACKEND_URL}/api/inventory", timeout=5)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) > 0


def test_inventory_item_by_id():
    response = requests.get(f"{STUDENT_3_BACKEND_URL}/api/inventory/1", timeout=5)
    assert response.status_code == 200
    assert response.json()["id"] == 1
