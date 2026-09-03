import sqlite3
from pathlib import Path


# =========================================================
# DATABASE PATH
# =========================================================

BACKEND_DIR = Path(__file__).resolve().parent
BASE_DIR = BACKEND_DIR.parent

DATABASE = BASE_DIR / "database" / "inventory.db"


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db_connection():

    connection = sqlite3.connect(DATABASE)

    connection.row_factory = sqlite3.Row

    return connection