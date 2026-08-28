import sqlite3
import os

DB_PATH = os.path.join(
    os.path.dirname(__file__),
    "users.db"
)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

#Customers table
cursor.execute("""
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    name TEXT NOT NULL
)
""")

#Staff table
cursor.execute("""
CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL
)
""")

#Test customer
cursor.execute("""
INSERT OR IGNORE INTO customers
(username, email, password, name)
VALUES (?, ?, ?, ?)
""", (
    "testcustomer",
    "customer@test.com",
    "customer123",
    "Test Customer"
))

#Test staff/admin user
cursor.execute("""
INSERT OR IGNORE INTO staff
(username, email, password, name, role)
VALUES (?, ?, ?, ?, ?)
""", (
    "teststaff",
    "staff@test.com",
    "staff123",
    "Test Staff",
    "admin"
))

conn.commit()
conn.close()

print("Database created successfully.")