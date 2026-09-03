import os

import requests


FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5300")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8300")
DATABASE_URL = os.getenv("DATABASE_URL", "http://localhost:7300")


def test_frontend_health():
    response = requests.get(FRONTEND_URL + "/health", timeout=5)
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_backend_health():
    response = requests.get(BACKEND_URL + "/api/health", timeout=5)
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_database_health():
    response = requests.get(DATABASE_URL + "/db/health", timeout=5)
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_inventory_contract():
    response = requests.get(BACKEND_URL + "/api/inventory", params={"page": 1, "per_page": 6}, timeout=5)
    assert response.status_code == 200
    data = response.json()
    assert {"items", "page", "total", "total_pages"}.issubset(data)
    assert len(data["items"]) <= 6


def test_dashboard_contract():
    response = requests.get(BACKEND_URL + "/api/dashboard", timeout=5)
    assert response.status_code == 200
    data = response.json()
    assert {"summary", "low_stock_items", "recent_restock_orders"}.issubset(data)


def test_frontend_inventory_page():
    response = requests.get(FRONTEND_URL + "/inventory/", timeout=10)
    assert response.status_code == 200
    assert "Inventory" in response.text
