from pathlib import Path
import importlib.util
import sqlite3

import pytest


STUDENT_DIR = Path(__file__).resolve().parents[1]
APP_PATH = STUDENT_DIR / "database" / "app.py"
SCHEMA_PATH = STUDENT_DIR / "database" / "schema.sql"

spec = importlib.util.spec_from_file_location("payment_database_app", APP_PATH)
payment_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(payment_app)


@pytest.fixture
def client(tmp_path):
    test_database = tmp_path / "test_payments.db"

    connection = sqlite3.connect(test_database)
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    connection.close()

    payment_app.DATABASE_PATH = test_database
    payment_app.app.config["TESTING"] = True

    with payment_app.app.test_client() as test_client:
        yield test_client


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json()["status"] == "healthy"


def test_create_and_read_payment(client):
    new_payment = {
        "order_id": 2001,
        "customer_id": 21,
        "amount": 14.50,
        "payment_method": "card",
    }

    create_response = client.post("/api/payments", json=new_payment)

    assert create_response.status_code == 201

    created_payment = create_response.get_json()

    assert created_payment["id"] == 1
    assert created_payment["order_id"] == 2001
    assert created_payment["payment_status"] == "pending"

    read_response = client.get("/api/payments/1")

    assert read_response.status_code == 200
    assert read_response.get_json()["amount"] == 14.50


def test_update_payment(client):
    create_response = client.post(
        "/api/payments",
        json={
            "order_id": 2002,
            "customer_id": 22,
            "amount": 20.00,
            "payment_method": "cash",
        },
    )

    payment_id = create_response.get_json()["id"]

    update_response = client.put(
        f"/api/payments/{payment_id}",
        json={
            "payment_status": "completed",
            "paid_at": "2026-09-03 15:00:00",
        },
    )

    assert update_response.status_code == 200
    assert update_response.get_json()["payment_status"] == "completed"


def test_delete_payment(client):
    create_response = client.post(
        "/api/payments",
        json={
            "order_id": 2003,
            "customer_id": 23,
            "amount": 9.00,
            "payment_method": "digital_wallet",
        },
    )

    payment_id = create_response.get_json()["id"]

    delete_response = client.delete(f"/api/payments/{payment_id}")

    assert delete_response.status_code == 200

    read_response = client.get(f"/api/payments/{payment_id}")

    assert read_response.status_code == 404


def test_missing_required_fields(client):
    response = client.post(
        "/api/payments",
        json={
            "amount": 10.00,
            "payment_method": "card",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Required fields are missing"