import sqlite3
from pathlib import Path


# =========================================================
# DATABASE PATH
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "inventory.db"


# =========================================================
# CREATE DATABASE
# =========================================================

def initialise_database():

    connection = sqlite3.connect(DATABASE_PATH)
    cursor = connection.cursor()


    # =====================================================
    # 1. INVENTORY TABLE
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT NOT NULL,
            minimum_stock REAL NOT NULL,
            status TEXT NOT NULL
        )
    """)


    # =====================================================
    # 2. SUPPLIERS TABLE
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact_name TEXT,
            email TEXT,
            phone TEXT
        )
    """)


    # =====================================================
    # 3. RESTOCK ORDERS TABLE
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS restock_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inventory_id INTEGER NOT NULL,
            supplier_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (inventory_id)
                REFERENCES inventory(id),

            FOREIGN KEY (supplier_id)
                REFERENCES suppliers(id)
        )
    """)

    # =====================================================
    # INVENTORY DUMMY DATA
    # =====================================================

    cursor.execute("SELECT COUNT(*) FROM inventory")

    if cursor.fetchone()[0] == 0:

        inventory_data = [
            ("Coffee Beans", "Coffee", 5000, "g", 1500, "OK"),
            ("Full Cream Milk", "Milk", 3000, "ml", 4000, "LOW"),
            ("Ice", "Other", 8000, "g", 2000, "OK"),
            ("Vanilla Syrup", "Syrup", 500, "ml", 300, "OK"),
            ("Caramel Syrup", "Syrup", 150, "ml", 300, "LOW"),
            ("Chocolate Powder", "Coffee", 1000, "g", 500, "OK"),
            ("Bread", "Food", 20, "slices", 30, "LOW"),
            ("Chicken", "Food", 1500, "g", 500, "OK"),
            ("Lettuce", "Food", 300, "g", 400, "LOW"),
            ("Mayonnaise", "Food", 800, "g", 300, "OK"),
            ("Ham", "Food", 700, "g", 300, "OK"),
            ("Cheese", "Food", 250, "g", 300, "LOW"),
            ("Butter", "Food", 500, "g", 200, "OK"),
            ("Avocado", "Food", 0, "g", 500, "OUT OF STOCK"),
            ("Chocolate Cake Slice", "Food", 8, "slices", 5, "OK"),
            ("Blueberry Muffin", "Food", 3, "each", 5, "LOW"),
            ("Croissant", "Food", 0, "each", 5, "OUT OF STOCK")
        ]

        cursor.executemany("""
            INSERT INTO inventory (
                name,
                category,
                quantity,
                unit,
                minimum_stock,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, inventory_data)
        
    # =====================================================
    # SUPPLIER DUMMY DATA
    # =====================================================

    cursor.execute("SELECT COUNT(*) FROM suppliers")

    if cursor.fetchone()[0] == 0:

        supplier_data = [
            (
                "Sydney Coffee Supplies",
                "James Lee",
                "james@sydneycoffee.com",
                "0400000001"
            ),

            (
                "Fresh Food Distribution",
                "Sarah Kim",
                "sarah@freshfood.com",
                "0400000002"
            ),

            (
                "Cafe Essentials Australia",
                "Michael Chen",
                "michael@cafeessentials.com",
                "0400000003"
            )
        ]

        cursor.executemany("""
            INSERT INTO suppliers (
                name,
                contact_name,
                email,
                phone
            )
            VALUES (?, ?, ?, ?)
        """, supplier_data)

    # =====================================================
    # RESTOCK ORDER DUMMY DATA
    # =====================================================

    cursor.execute("SELECT COUNT(*) FROM restock_orders")

    if cursor.fetchone()[0] == 0:

        restock_data = [
            (2, 2, 5000, "Pending"),
            (5, 1, 1000, "Pending"),
            (7, 2, 40, "Ordered"),
            (12, 2, 1000, "Delivered"),
            (14, 2, 2000, "Pending"),
            (16, 3, 20, "Pending"),
            (17, 3, 30, "Ordered")
        ]

        cursor.executemany("""
            INSERT INTO restock_orders (
                inventory_id,
                supplier_id,
                quantity,
                status
            )
            VALUES (?, ?, ?, ?)
        """, restock_data)

    connection.commit()
    connection.close()

    print("Database created successfully.")


if __name__ == "__main__":
    initialise_database()