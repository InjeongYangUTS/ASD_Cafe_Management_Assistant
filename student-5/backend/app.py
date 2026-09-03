import os
from datetime import datetime, timezone
from uuid import uuid4

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS


app = Flask(__name__)
CORS(app)

DATABASE_API_URL = os.getenv(
    "DATABASE_API_URL",
    "http://127.0.0.1:5005/api",
)

ORDER_SERVICE_URL = os.getenv(
    "ORDER_SERVICE_URL",
    "",
)


def current_time():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def call_database(method, endpoint, data=None):
    return requests.request(
        method=method,
        url=f"{DATABASE_API_URL}/{endpoint}",
        json=data,
        timeout=5,
    )

def call_order_service(method, endpoint, data=None):
    return requests.request(
        method=method,
        url=f"{ORDER_SERVICE_URL}/{endpoint}",
        json=data,
        timeout=5,
    )


@app.get("/health")
def health():
    try:
        response = call_database("GET", "payments")

        if response.status_code == 200:
            return jsonify(
                {
                    "service": "Student 5 Payment Backend",
                    "database": "connected",
                    "status": "healthy",
                }
            )

        return jsonify({"status": "unhealthy"}), 503

    except requests.RequestException:
        return jsonify(
            {
                "database": "unavailable",
                "status": "unhealthy",
            }
        ), 503


@app.get("/api/payments")
def list_payments():
    try:
        response = call_database("GET", "payments")
        return jsonify(response.json()), response.status_code
    except requests.RequestException:
        return jsonify({"error": "Database service is unavailable"}), 503


@app.get("/api/payments/<int:payment_id>")
def get_payment(payment_id):
    try:
        response = call_database("GET", f"payments/{payment_id}")
        return jsonify(response.json()), response.status_code
    except requests.RequestException:
        return jsonify({"error": "Database service is unavailable"}), 503


@app.post("/api/payments/process")
def process_payment():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "JSON request body is required"}), 400

    required_fields = [
        "order_id",
        "customer_id",
        "amount",
        "payment_method",
    ]

    missing_fields = [
        field for field in required_fields if data.get(field) is None
    ]

    if missing_fields:
        return jsonify(
            {
                "error": "Required fields are missing",
                "fields": missing_fields,
            }
        ), 400

    if not isinstance(data["amount"], (int, float)) or data["amount"] <= 0:
        return jsonify({"error": "Amount must be greater than zero"}), 400

    allowed_methods = ["card", "cash", "digital_wallet"]

    if data["payment_method"] not in allowed_methods:
        return jsonify(
            {
                "error": "Unsupported payment method",
                "allowed_methods": allowed_methods,
            }
        ), 400

    order = None

    if ORDER_SERVICE_URL:
        try:
            order_response = call_order_service(
                "GET",
                f"orders/{data['order_id']}",
            )

            if order_response.status_code == 404:
                return jsonify({"error": "Order not found"}), 404

            if order_response.status_code != 200:
                return jsonify(
                    {"error": "Order service returned an error"}
                ), 502

            order = order_response.json()
            order_total = float(order["total_amount"])

            if round(float(data["amount"]), 2) != round(order_total, 2):
                return jsonify(
                    {
                        "error": "Payment amount does not match order total",
                        "order_total": order_total,
                    }
                ), 400

            if order["status"] in ["COMPLETED", "CANCELLED"]:
                return jsonify(
                    {
                        "error": (
                            f"Cannot pay for an order with "
                            f"{order['status']} status"
                        )
                    }
                ), 400

        except requests.RequestException:
            return jsonify({"error": "Order service is unavailable"}), 503
        except (KeyError, TypeError, ValueError):
            return jsonify(
                {"error": "Order service returned invalid data"}
            ), 502

    payment_data = {
        "order_id": data["order_id"],
        "customer_id": data["customer_id"],
        "amount": data["amount"],
        "payment_method": data["payment_method"],
        "payment_status": "pending",
    }

    try:
        payment_response = call_database(
            "POST",
            "payments",
            payment_data,
        )

        if payment_response.status_code != 201:
            return jsonify(payment_response.json()), payment_response.status_code

        payment = payment_response.json()

        transaction_data = {
            "payment_id": payment["id"],
            "transaction_reference": f"PAY-{uuid4().hex[:12].upper()}",
            "transaction_type": "payment",
            "amount": data["amount"],
            "status": "completed",
            "processed_at": current_time(),
            "notes": f"Payment for order {data['order_id']}",
        }

        transaction_response = call_database(
            "POST",
            "transactions",
            transaction_data,
        )

        if transaction_response.status_code != 201:
            call_database(
                "PUT",
                f"payments/{payment['id']}",
                {"payment_status": "failed"},
            )

            return jsonify(
                {"error": "Transaction could not be created"}
            ), 500

        completed_response = call_database(
            "PUT",
            f"payments/{payment['id']}",
            {
                "payment_status": "completed",
                "paid_at": current_time(),
            },
        )

        order_update = None
        order_update_warning = None

        if ORDER_SERVICE_URL:
            try:
                status_response = call_order_service(
                    "PUT",
                    f"order-status/{data['order_id']}",
                    {
                        "status": "COMPLETED",
                        "changed_by": "payment",
                        "note": (
                            f"Payment {payment['id']} "
                            f"completed successfully"
                        ),
                    },
                )

                if status_response.status_code == 200:
                    order_update = status_response.json()
                else:
                    status_error = status_response.json()
                    order_update_warning = status_error.get(
                        "error",
                        "Order status could not be updated",
                    )

            except (
                requests.RequestException,
                ValueError,
            ):
                order_update_warning = (
                    "Payment succeeded, but the order status "
                    "could not be updated"
                )          

        return jsonify(
            {
                "message": "Payment processed successfully",
                "payment": completed_response.json(),
                "transaction": transaction_response.json(),
                "order_update": order_update,
                "order_update_warning": order_update_warning,
            }
        ), 201

    except requests.RequestException:
        return jsonify({"error": "Database service is unavailable"}), 503

@app.get("/api/refunds")
def list_refunds():
    try:
        response = call_database("GET", "refunds")
        return jsonify(response.json()), response.status_code
    except requests.RequestException:
        return jsonify({"error": "Database service is unavailable"}), 503


@app.post("/api/refunds")
def process_refund():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "JSON request body is required"}), 400

    required_fields = [
        "payment_id",
        "refund_amount",
        "refund_reason",
        "requested_by",
    ]

    missing_fields = [
        field for field in required_fields if data.get(field) is None
    ]

    if missing_fields:
        return jsonify(
            {
                "error": "Required fields are missing",
                "fields": missing_fields,
            }
        ), 400

    refund_amount = data["refund_amount"]

    if not isinstance(refund_amount, (int, float)) or refund_amount <= 0:
        return jsonify(
            {"error": "Refund amount must be greater than zero"}
        ), 400

    try:
        payment_response = call_database(
            "GET",
            f"payments/{data['payment_id']}",
        )

        if payment_response.status_code != 200:
            return jsonify({"error": "Payment not found"}), 404

        payment = payment_response.json()

        if payment["payment_status"] not in [
            "completed",
            "partially_refunded",
        ]:
            return jsonify(
                {"error": "Only completed payments can be refunded"}
            ), 400

        refunds_response = call_database("GET", "refunds")

        if refunds_response.status_code != 200:
            return jsonify(
                {"error": "Existing refunds could not be checked"}
            ), 500

        existing_refunds = refunds_response.json()

        already_refunded = sum(
            refund["refund_amount"]
            for refund in existing_refunds
            if refund["payment_id"] == payment["id"]
            and refund["refund_status"] == "completed"
        )

        remaining_amount = payment["amount"] - already_refunded

        if refund_amount > remaining_amount:
            return jsonify(
                {
                    "error": "Refund exceeds the remaining payment amount",
                    "remaining_amount": remaining_amount,
                }
            ), 400

        processed_time = current_time()

        transaction_data = {
            "payment_id": payment["id"],
            "transaction_reference": f"REF-{uuid4().hex[:12].upper()}",
            "transaction_type": "refund",
            "amount": refund_amount,
            "status": "completed",
            "processed_at": processed_time,
            "notes": data["refund_reason"],
        }

        transaction_response = call_database(
            "POST",
            "transactions",
            transaction_data,
        )

        if transaction_response.status_code != 201:
            return jsonify(
                {"error": "Refund transaction could not be created"}
            ), 500

        transaction = transaction_response.json()

        refund_data = {
            "payment_id": payment["id"],
            "transaction_id": transaction["id"],
            "refund_amount": refund_amount,
            "refund_reason": data["refund_reason"],
            "refund_status": "completed",
            "requested_by": data["requested_by"],
            "requested_at": processed_time,
            "processed_at": processed_time,
        }

        refund_response = call_database(
            "POST",
            "refunds",
            refund_data,
        )

        if refund_response.status_code != 201:
            return jsonify(
                {"error": "Refund record could not be created"}
            ), 500

        total_refunded = already_refunded + refund_amount

        new_payment_status = (
            "refunded"
            if total_refunded >= payment["amount"]
            else "partially_refunded"
        )

        call_database(
            "PUT",
            f"payments/{payment['id']}",
            {"payment_status": new_payment_status},
        )

        return jsonify(
            {
                "message": "Refund processed successfully",
                "refund": refund_response.json(),
                "transaction": transaction,
                "remaining_amount": payment["amount"] - total_refunded,
            }
        ), 201

    except requests.RequestException:
        return jsonify({"error": "Database service is unavailable"}), 503
    
if __name__ == "__main__":
    app.run(
    host="0.0.0.0",
    port=int(os.getenv("PORT", "5006")),
    debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
)
