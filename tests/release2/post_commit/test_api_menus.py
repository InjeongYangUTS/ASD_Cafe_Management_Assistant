import os

import requests


STUDENT_2_BACKEND_URL = os.getenv("STUDENT_2_BACKEND_URL", "http://localhost:5201")


def test_menus_exist():
    response = requests.get(f"{STUDENT_2_BACKEND_URL}/api/menus", timeout=5)
    assert response.status_code == 200
    menus = response.json()
    assert len(menus) > 0


def test_menu_by_id():
    response = requests.get(f"{STUDENT_2_BACKEND_URL}/api/menus/1", timeout=5)
    assert response.status_code == 200
    assert response.json()["menu_id"] == 1
