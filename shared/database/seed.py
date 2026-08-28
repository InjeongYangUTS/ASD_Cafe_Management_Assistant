import sqlite3
import os

DB_PATH = os.path.join(
    os.path.dirname(__file__),
    "users.db"
)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    name TEXT NOT NULL
)
""")

cursor.execute("""
INSERT OR IGNORE INTO customers
(customer_id, password, name)
VALUES (?, ?, ?)
""", ("customer1", "1234", "Test Customer"))

conn.commit()
conn.close()

print("Database created successfully.")