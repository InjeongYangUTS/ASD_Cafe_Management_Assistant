import sqlite3
import os
from werkzeug.security import generate_password_hash


BASE_DIR = os.path.dirname(__file__)

DB_PATH = os.path.join(
    BASE_DIR,
    "users.db"
)

SCHEMA_PATH = os.path.join(
    BASE_DIR,
    "schema.sql"
)


conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()


# Create tables using schema.sql
with open(SCHEMA_PATH, "r") as schema_file:
    cursor.executescript(schema_file.read())


# -------------------------
# Test Customer
# -------------------------

customer_password_hash = generate_password_hash("customer123")

cursor.execute(
    """
    INSERT OR IGNORE INTO customers
    (name, username, email, password_hash)
    VALUES (?, ?, ?, ?)
    """,
    (
        "Test Customer",
        "testcustomer",
        "customer@test.com",
        customer_password_hash
    )
)


# -------------------------
# Test Staff / Admin
# -------------------------

staff_password_hash = generate_password_hash("staff123")

cursor.execute(
    """
    INSERT OR IGNORE INTO staff
    (username, email, password_hash, name, role)
    VALUES (?, ?, ?, ?, ?)
    """,
    (
        "teststaff",
        "staff@test.com",
        staff_password_hash,
        "Test Staff",
        "staff"
    )
)


conn.commit()
conn.close()

print("Database created successfully.")