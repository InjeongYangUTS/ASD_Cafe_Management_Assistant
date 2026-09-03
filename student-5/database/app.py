import os
from pathlib import Path
import sqlite3

from flask import Flask, jsonify, request

app = Flask(__name__)

DATABASE_PATH = Path(__file__).with_name("payments.db")

RESOURCE_CONFIG = {
    "payments": {
        "fields": [
            "order_id",
            "customer_id",
            "amount",
            "payment_method",
            "payment_status",
            "paid_at",
        ],
        "required": [
            "order_id",
            "customer_id",
            "amount",
            "payment_method",
        ],
    },
    "transactions": {
        "fields": [
            "payment_id",
            "transaction_reference",
            "transaction_type",
            "amount",
            "status",
            "processed_at",
            "notes",
        ],
        "required": [
            "payment_id",
            "transaction_reference",
            "amount",
            "status",
        ],
    },
    "refunds": {
        "fields": [
            "payment_id",
            "transaction_id",
            "refund_amount",
            "refund_reason",
            "refund_status",
            "requested_by",
            "requested_at",
            "processed_at",
        ],
        "required": [
            "payment_id",
            "refund_amount",
            "refund_reason",
            "requested_by",
        ],
    },
}


def get_database():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def get_config(resource):
    return RESOURCE_CONFIG.get(resource)


@app.get("/health")
def health():
    return jsonify(
        {
            "service": "Student 5 Payment Database API",
            "status": "healthy",
        }
    )


@app.get("/api/<resource>")
def list_records(resource):
    if not get_config(resource):
        return jsonify({"error": "Resource not found"}), 404

    connection = get_database()
    records = connection.execute(
        f"SELECT * FROM {resource} ORDER BY id"
    ).fetchall()
    connection.close()

    return jsonify([dict(record) for record in records])


@app.get("/api/<resource>/<int:record_id>")
def get_record(resource, record_id):
    if not get_config(resource):
        return jsonify({"error": "Resource not found"}), 404

    connection = get_database()
    record = connection.execute(
        f"SELECT * FROM {resource} WHERE id = ?",
        (record_id,),
    ).fetchone()
    connection.close()

    if record is None:
        return jsonify({"error": "Record not found"}), 404

    return jsonify(dict(record))


@app.post("/api/<resource>")
def create_record(resource):
    config = get_config(resource)

    if not config:
        return jsonify({"error": "Resource not found"}), 404

    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "JSON request body is required"}), 400

    missing_fields = [
        field for field in config["required"] if data.get(field) is None
    ]

    if missing_fields:
        return jsonify(
            {
                "error": "Required fields are missing",
                "fields": missing_fields,
            }
        ), 400

    supplied_fields = [
        field for field in config["fields"] if field in data
    ]
    values = [data[field] for field in supplied_fields]

    columns = ", ".join(supplied_fields)
    placeholders = ", ".join("?" for _ in supplied_fields)

    connection = get_database()

    try:
        cursor = connection.execute(
            f"INSERT INTO {resource} ({columns}) VALUES ({placeholders})",
            values,
        )
        connection.commit()

        record = connection.execute(
            f"SELECT * FROM {resource} WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    except sqlite3.IntegrityError as error:
        connection.close()
        return jsonify({"error": str(error)}), 400

    connection.close()
    return jsonify(dict(record)), 201


@app.put("/api/<resource>/<int:record_id>")
def update_record(resource, record_id):
    config = get_config(resource)

    if not config:
        return jsonify({"error": "Resource not found"}), 404

    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "JSON request body is required"}), 400

    supplied_fields = [
        field for field in config["fields"] if field in data
    ]

    if not supplied_fields:
        return jsonify({"error": "No valid fields were supplied"}), 400

    assignments = ", ".join(
        f"{field} = ?" for field in supplied_fields
    )
    values = [data[field] for field in supplied_fields]
    values.append(record_id)

    connection = get_database()

    try:
        cursor = connection.execute(
            f"UPDATE {resource} SET {assignments} WHERE id = ?",
            values,
        )
        connection.commit()

        if cursor.rowcount == 0:
            connection.close()
            return jsonify({"error": "Record not found"}), 404

        record = connection.execute(
            f"SELECT * FROM {resource} WHERE id = ?",
            (record_id,),
        ).fetchone()
    except sqlite3.IntegrityError as error:
        connection.close()
        return jsonify({"error": str(error)}), 400

    connection.close()
    return jsonify(dict(record))


@app.delete("/api/<resource>/<int:record_id>")
def delete_record(resource, record_id):
    if not get_config(resource):
        return jsonify({"error": "Resource not found"}), 404

    connection = get_database()

    try:
        cursor = connection.execute(
            f"DELETE FROM {resource} WHERE id = ?",
            (record_id,),
        )
        connection.commit()
    except sqlite3.IntegrityError as error:
        connection.close()
        return jsonify({"error": str(error)}), 400

    connection.close()

    if cursor.rowcount == 0:
        return jsonify({"error": "Record not found"}), 404

    return jsonify({"message": "Record deleted successfully"})


if __name__ == "__main__":
    app.run(
    host="0.0.0.0",
    port=int(os.getenv("PORT", "5005")),
    debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
)