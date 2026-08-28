import sqlite3
import os


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


with open(SCHEMA_PATH, "r") as file:
    schema = file.read()

conn.executescript(schema)


conn.close()


print("Database created successfully.")