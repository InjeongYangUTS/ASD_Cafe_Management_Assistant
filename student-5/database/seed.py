import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "payments.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"

connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()

cursor.execute("PRAGMA foreign_keys = ON")

with open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
    cursor.executescript(schema_file.read())

cursor.execute("DELETE FROM refunds")
cursor.execute("DELETE FROM transactions")
cursor.execute("DELETE FROM payments")

cursor.execute(
    """
    DELETE FROM sqlite_sequence
    WHERE name IN ('payments', 'transactions', 'refunds')
    """
)

payments = [
    (1001, 1, 12.50, "card", "completed", "2026-09-01 08:10:00"),
    (1002, 2, 8.00, "cash", "completed", "2026-09-01 08:30:00"),
    (1003, 3, 17.50, "digital_wallet", "completed", "2026-09-01 09:00:00"),
    (1004, 4, 6.50, "card", "completed", "2026-09-01 09:20:00"),
    (1005, 5, 24.00, "cash", "completed", "2026-09-01 10:00:00"),
    (1006, 6, 11.00, "card", "completed", "2026-09-01 10:30:00"),
    (1007, 7, 15.50, "digital_wallet", "completed", "2026-09-01 11:00:00"),
    (1008, 8, 9.50, "cash", "completed", "2026-09-01 11:20:00"),
    (1009, 9, 21.00, "card", "completed", "2026-09-01 12:00:00"),
    (1010, 10, 13.50, "digital_wallet", "completed", "2026-09-01 12:30:00"),
]

cursor.executemany(
    """
    INSERT INTO payments
    (order_id, customer_id, amount, payment_method, payment_status, paid_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """,
    payments,
)

transactions = [
    (1, "TXN-1001", "payment", 12.50, "successful", "Card payment"),
    (2, "TXN-1002", "payment", 8.00, "successful", "Cash payment"),
    (3, "TXN-1003", "payment", 17.50, "successful", "Digital wallet"),
    (4, "TXN-1004", "payment", 6.50, "successful", "Card payment"),
    (5, "TXN-1005", "payment", 24.00, "successful", "Cash payment"),
    (6, "TXN-1006", "payment", 11.00, "successful", "Card payment"),
    (7, "TXN-1007", "payment", 15.50, "successful", "Digital wallet"),
    (8, "TXN-1008", "payment", 9.50, "successful", "Cash payment"),
    (9, "TXN-1009", "payment", 21.00, "successful", "Card payment"),
    (10, "TXN-1010", "payment", 13.50, "successful", "Digital wallet"),
]

cursor.executemany(
    """
    INSERT INTO transactions
    (payment_id, transaction_reference, transaction_type, amount, status, notes)
    VALUES (?, ?, ?, ?, ?, ?)
    """,
    transactions,
)

refunds = [
    (1, 1, 2.50, "Incorrect item", "completed", 1),
    (2, 2, 1.00, "Customer request", "completed", 1),
    (3, 3, 3.50, "Order delay", "pending", 2),
    (4, 4, 1.50, "Item unavailable", "completed", 2),
    (5, 5, 4.00, "Incorrect charge", "pending", 1),
    (6, 6, 2.00, "Quality issue", "completed", 3),
    (7, 7, 2.50, "Customer request", "pending", 3),
    (8, 8, 1.50, "Duplicate item", "completed", 2),
    (9, 9, 5.00, "Order cancelled", "pending", 1),
    (10, 10, 3.50, "Incorrect item", "completed", 3),
]

cursor.executemany(
    """
    INSERT INTO refunds
    (payment_id, transaction_id, refund_amount, refund_reason,
     refund_status, requested_by)
    VALUES (?, ?, ?, ?, ?, ?)
    """,
    refunds,
)

connection.commit()

for table in ["payments", "transactions", "refunds"]:
    count = cursor.execute(
        f"SELECT COUNT(*) FROM {table}"
    ).fetchone()[0]
    print(f"{table}: {count} records")

connection.close()

print("Payment database created successfully.")