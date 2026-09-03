from pathlib import Path
import importlib.util
from unittest.mock import Mock, patch


STUDENT_DIR = Path(__file__).resolve().parents[1]
APP_PATH = STUDENT_DIR / "backend" / "app.py"

spec = importlib.util.spec_from_file_location(
    "payment_backend_app",
    APP_PATH,
)
backend_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend_app)

backend_app.app.config["TESTING"] = True


def mock_response(status_code, data):
    response = Mock()
    response.status_code = status_code
    response.json.return_value = data
    return response


def test_health_endpoint():
    with backend_app.app.test_client() as client:
        with patch.object(
            backend_app,
            "call_database",
            return_value=mock_response(200, []),
        ):
            response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json()["status"] == "healthy"
    assert response.get_json()["database"] == "connected"


def test_list_payments():
    payments = [
        {
            "id": 1,
            "order_id": 1001,
            "customer_id": 1,
            "amount": 25.00,
            "payment_method": "card",
            "payment_status": "completed",
        }
    ]

    with backend_app.app.test_client() as client:
        with patch.object(
            backend_app,
            "call_database",
            return_value=mock_response(200, payments),
        ):
            response = client.get("/api/payments")

    assert response.status_code == 200
    assert response.get_json() == payments


def test_process_payment_successfully():
    pending_payment = {
        "id": 11,
        "order_id": 2001,
        "customer_id": 21,
        "amount": 18.50,
        "payment_method": "card",
        "payment_status": "pending",
        "paid_at": None,
    }

    completed_payment = {
        **pending_payment,
        "payment_status": "completed",
        "paid_at": "2026-09-03 14:00:00",
    }

    transaction = {
        "id": 11,
        "payment_id": 11,
        "transaction_reference": "PAY-TEST12345678",
        "transaction_type": "payment",
        "amount": 18.50,
        "status": "completed",
    }

    responses = [
        mock_response(201, pending_payment),
        mock_response(201, transaction),
        mock_response(200, completed_payment),
    ]

    with backend_app.app.test_client() as client:
        with patch.object(
            backend_app,
            "call_database",
            side_effect=responses,
        ):
            response = client.post(
                "/api/payments/process",
                json={
                    "order_id": 2001,
                    "customer_id": 21,
                    "amount": 18.50,
                    "payment_method": "card",
                },
            )

    result = response.get_json()

    assert response.status_code == 201
    assert result["message"] == "Payment processed successfully"
    assert result["payment"]["payment_status"] == "completed"
    assert result["transaction"]["transaction_type"] == "payment"


def test_rejects_invalid_payment_amount():
    with backend_app.app.test_client() as client:
        response = client.post(
            "/api/payments/process",
            json={
                "order_id": 2002,
                "customer_id": 22,
                "amount": 0,
                "payment_method": "card",
            },
        )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Amount must be greater than zero"


def test_rejects_unsupported_payment_method():
    with backend_app.app.test_client() as client:
        response = client.post(
            "/api/payments/process",
            json={
                "order_id": 2003,
                "customer_id": 23,
                "amount": 20.00,
                "payment_method": "cryptocurrency",
            },
        )

    result = response.get_json()

    assert response.status_code == 400
    assert result["error"] == "Unsupported payment method"


def test_process_partial_refund_successfully():
    payment = {
        "id": 12,
        "order_id": 2004,
        "customer_id": 24,
        "amount": 18.50,
        "payment_method": "card",
        "payment_status": "completed",
    }

    transaction = {
        "id": 12,
        "payment_id": 12,
        "transaction_reference": "REF-TEST12345678",
        "transaction_type": "refund",
        "amount": 5.00,
        "status": "completed",
    }

    refund = {
        "id": 11,
        "payment_id": 12,
        "transaction_id": 12,
        "refund_amount": 5.00,
        "refund_reason": "Customer changed order",
        "refund_status": "completed",
        "requested_by": 24,
    }

    responses = [
        mock_response(200, payment),
        mock_response(200, []),
        mock_response(201, transaction),
        mock_response(201, refund),
        mock_response(
            200,
            {
                **payment,
                "payment_status": "partially_refunded",
            },
        ),
    ]

    with backend_app.app.test_client() as client:
        with patch.object(
            backend_app,
            "call_database",
            side_effect=responses,
        ):
            response = client.post(
                "/api/refunds",
                json={
                    "payment_id": 12,
                    "refund_amount": 5.00,
                    "refund_reason": "Customer changed order",
                    "requested_by": 24,
                },
            )

    result = response.get_json()

    assert response.status_code == 201
    assert result["message"] == "Refund processed successfully"
    assert result["refund"]["refund_amount"] == 5.00
    assert result["remaining_amount"] == 13.50


def test_rejects_refund_above_remaining_amount():
    payment = {
        "id": 12,
        "amount": 18.50,
        "payment_status": "partially_refunded",
    }

    previous_refunds = [
        {
            "payment_id": 12,
            "refund_amount": 10.00,
            "refund_status": "completed",
        }
    ]

    responses = [
        mock_response(200, payment),
        mock_response(200, previous_refunds),
    ]

    with backend_app.app.test_client() as client:
        with patch.object(
            backend_app,
            "call_database",
            side_effect=responses,
        ):
            response = client.post(
                "/api/refunds",
                json={
                    "payment_id": 12,
                    "refund_amount": 10.00,
                    "refund_reason": "Requested refund",
                    "requested_by": 24,
                },
            )

    result = response.get_json()

    assert response.status_code == 400
    assert result["error"] == "Refund exceeds the remaining payment amount"
    assert result["remaining_amount"] == 8.50