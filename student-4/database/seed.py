"""
Student 4 (Stella Kwon) - Order & Kitchen Management
Database microservice : schema creation + seed data.

Creates orders.db with 12 seeded orders, 30 order items and a full status
history so the Kitchen Display System has realistic data on first boot.

Menu names / prices stored here are SNAPSHOTS taken at order time.
The live source of truth is Student 2's Menu API - see backend/clients.py.

Run:  python seed.py            (safe to re-run: rebuilds the tables)
"""

import os
import sqlite3
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("ORDER_DB_PATH", os.path.join(BASE_DIR, "orders.db"))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")


# ---------------------------------------------------------------------
# Menu snapshot used for seeding (mirrors Student 2's menu_id 1-15).
# menu_id: (name, unit_price, station, prep_seconds)
# ---------------------------------------------------------------------
MENU_SNAPSHOT = {
    1:  ("Cappuccino",           4.50, "BAR",     90),
    2:  ("Latte",                4.50, "BAR",     90),
    3:  ("Flat White",           4.50, "BAR",     90),
    4:  ("Long Black",           4.20, "BAR",     60),
    5:  ("Iced Long Black",      5.00, "BAR",     75),
    6:  ("Iced Latte",           5.50, "BAR",    100),
    7:  ("Vanilla Latte",        5.20, "BAR",    105),
    8:  ("Caramel Latte",        5.20, "BAR",    105),
    9:  ("Hot Chocolate",        5.00, "BAR",     90),
    10: ("Chicken Sandwich",    12.50, "KITCHEN", 300),
    11: ("Ham & Cheese Toastie", 9.50, "KITCHEN", 240),
    12: ("Avocado Toast",       14.00, "KITCHEN", 270),
    13: ("Chocolate Cake",       7.50, "PASTRY",   45),
    14: ("Blueberry Muffin",     5.50, "PASTRY",   30),
    15: ("Croissant",            5.00, "PASTRY",   40),
}


# ---------------------------------------------------------------------
# Seed orders.
# (order_number, channel, table, customer_name, staff_name, status,
#  minutes_ago, note, [(menu_id, qty, item_note), ...])
# ---------------------------------------------------------------------
SEED_ORDERS = [
    ("A-1001", "DINE_IN",  "T1",  "Test Customer", "Test Staff", "COMPLETED", 210,
     None, [(1, 2, None), (15, 1, "warmed")]),

    ("A-1002", "TAKEAWAY", None,  "Daniel Park",   "Test Staff", "COMPLETED", 185,
     "no sugar", [(4, 1, None), (14, 2, None)]),

    ("A-1003", "DINE_IN",  "T4",  "Amelia Chen",   "Test Staff", "COMPLETED", 160,
     None, [(10, 1, "no mayo"), (2, 1, None), (13, 1, None)]),

    ("A-1004", "DINE_IN",  "T2",  "Test Customer", "Test Staff", "CANCELLED", 140,
     "customer left", [(6, 2, None)]),

    ("A-1005", "TAKEAWAY", None,  "Marcus Reid",   "Test Staff", "COMPLETED", 120,
     None, [(3, 1, "extra hot"), (11, 1, None)]),

    ("A-1006", "DINE_IN",  "T6",  "Priya Nair",    "Test Staff", "COMPLETED",  95,
     None, [(12, 1, None), (5, 1, None), (14, 1, None)]),

    ("A-1007", "DINE_IN",  "T3",  "Test Customer", "Test Staff", "READY",      22,
     None, [(7, 1, None), (13, 1, None)]),

    ("A-1008", "TAKEAWAY", None,  "Jordan Lee",    "Test Staff", "PREPARING",  16,
     "for 12:30 pickup", [(10, 2, None), (1, 2, None)]),

    ("A-1009", "DINE_IN",  "T5",  "Sofia Rossi",   "Test Staff", "PREPARING",  12,
     None, [(12, 1, "gluten free bread"), (8, 1, None), (15, 2, None)]),

    ("A-1010", "DINE_IN",  "T8",  "Henry Wu",      "Test Staff", "CONFIRMED",   7,
     None, [(2, 3, None), (11, 2, None), (14, 1, None)]),

    ("A-1011", "TAKEAWAY", None,  "Test Customer", "Test Staff", "CONFIRMED",   4,
     None, [(6, 1, None), (9, 1, None)]),

    ("A-1012", "DINE_IN",  "T7",  "Olivia Brown",  "Test Staff", "PENDING",     1,
     "birthday - candle on cake", [(13, 2, None), (3, 2, None), (10, 1, None)]),
]


# Status lifecycle used to build the history rows
LIFECYCLE = ["PENDING", "CONFIRMED", "PREPARING", "READY", "COMPLETED"]


def build_history(final_status, placed_at):
    """Return [(status, changed_by, note, changed_at), ...] up to final_status."""
    rows = []

    if final_status == "CANCELLED":
        rows.append(("PENDING", "pos", "order placed", placed_at))
        rows.append(("CANCELLED", "Test Staff", "cancelled at counter",
                     placed_at + timedelta(minutes=3)))
        return rows

    stop = LIFECYCLE.index(final_status)
    offsets = [0, 1, 3, 9, 14]

    for step in range(stop + 1):
        status = LIFECYCLE[step]
        rows.append((
            status,
            "pos" if step == 0 else "kitchen",
            "order placed" if step == 0 else None,
            placed_at + timedelta(minutes=offsets[step]),
        ))

    return rows


def main():
    fresh = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    with open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
        cursor.executescript(schema_file.read())

    # Idempotent re-seed: clear existing rows so the demo data is stable.
    cursor.execute("DELETE FROM order_statuses")
    cursor.execute("DELETE FROM order_items")
    cursor.execute("DELETE FROM orders")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name IN "
                   "('orders', 'order_items', 'order_statuses')")

    now = datetime.now()

    for (number, channel, table, customer, staff, status,
         minutes_ago, note, items) in SEED_ORDERS:

        placed_at = now - timedelta(minutes=minutes_ago)

        item_count = sum(qty for _, qty, _ in items)
        total = 0.0
        prep_total = 0

        for menu_id, qty, _ in items:
            _, price, _, prep = MENU_SNAPSHOT[menu_id]
            total += price * qty
            prep_total += prep * qty

        history = build_history(status, placed_at)
        updated_at = history[-1][3]

        cursor.execute(
            """
            INSERT INTO orders
                (order_number, channel, table_number, customer_name,
                 staff_name, status, item_count, total_amount, prep_seconds,
                 note, stock_deducted, placed_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                number, channel, table, customer, staff, status,
                item_count, round(total, 2), prep_total, note,
                placed_at.strftime("%Y-%m-%d %H:%M:%S"),
                updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        order_id = cursor.lastrowid

        for menu_id, qty, item_note in items:
            name, price, station, prep = MENU_SNAPSHOT[menu_id]

            if status in ("COMPLETED", "READY"):
                item_status = "READY"
            elif status == "CANCELLED":
                item_status = "CANCELLED"
            elif status == "PREPARING":
                item_status = "PREPARING"
            else:
                item_status = "PENDING"

            cursor.execute(
                """
                INSERT INTO order_items
                    (order_id, menu_id, menu_name, unit_price, quantity,
                     line_total, station, prep_seconds, item_status, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id, menu_id, name, price, qty,
                    round(price * qty, 2), station, prep, item_status, item_note,
                ),
            )

        for hist_status, changed_by, hist_note, changed_at in history:
            cursor.execute(
                """
                INSERT INTO order_statuses
                    (order_id, status, changed_by, note, changed_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    order_id, hist_status, changed_by, hist_note,
                    changed_at.strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )

    conn.commit()

    counts = {}
    for table_name in ("orders", "order_items", "order_statuses"):
        counts[table_name] = cursor.execute(
            f"SELECT COUNT(*) FROM {table_name}"
        ).fetchone()[0]

    conn.close()

    print(f"[seed] database : {DB_PATH} ({'created' if fresh else 'refreshed'})")
    print(f"[seed] orders         : {counts['orders']}")
    print(f"[seed] order_items    : {counts['order_items']}")
    print(f"[seed] order_statuses : {counts['order_statuses']}")
    print("[seed] done.")


if __name__ == "__main__":
    main()
