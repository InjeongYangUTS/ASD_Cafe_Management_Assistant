import os
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.getenv("INVENTORY_DB_PATH", BASE_DIR / "inventory.db"))


INVENTORY_DATA = [
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
    ("Croissant", "Food", 0, "each", 5, "OUT OF STOCK"),
]


SUPPLIER_DATA = [
    ("Sydney Coffee Supplies", "James Lee", "james@sydneycoffee.com", "0400 000 001", "Coffee beans, chocolate powder", "Active"),
    ("Fresh Food Distribution", "Sarah Kim", "sarah@freshfood.com", "0400 000 002", "Chicken, lettuce, avocado", "Active"),
    ("Cafe Essentials Australia", "Michael Chen", "michael@cafeessentials.com", "0400 000 003", "Syrups, mayonnaise", "Active"),
    ("Sydney Dairy Wholesale", "Emma Wilson", "emma@sydneydairy.com", "0400 000 004", "Milk, butter, cheese", "Active"),
    ("Golden Bakery Supplies", "Daniel Park", "daniel@goldenbakery.com", "0400 000 005", "Bread, croissants", "Active"),
    ("Sweet Treats Wholesale", "Olivia Brown", "olivia@sweettreats.com", "0400 000 006", "Cake slices, muffins", "Active"),
    ("Australian Ice Company", "Noah Taylor", "noah@australianice.com", "0400 000 007", "Ice", "Active"),
    ("Metro Food Services", "Sophia Nguyen", "sophia@metrofood.com", "0400 000 008", "Ham, chicken, cheese", "Active"),
    ("Premium Syrup Co.", "William Zhang", "william@premiumsyrup.com", "0400 000 009", "Vanilla and caramel syrup", "Inactive"),
    ("Daily Fresh Produce", "Ava Thompson", "ava@dailyfresh.com", "0400 000 010", "Lettuce, avocado", "Active"),
]


RESTOCK_DATA = [
    (2, 2, 5000, "Pending"),
    (5, 1, 1000, "Pending"),
    (7, 2, 40, "Ordered"),
    (12, 2, 1000, "Delivered"),
    (14, 2, 2000, "Pending"),
    (16, 3, 20, "Pending"),
    (17, 3, 30, "Ordered"),
]


def initialise_database(database_path=DATABASE_PATH):
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    cursor = connection.cursor()
    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact_name TEXT,
            email TEXT,
            phone TEXT,
            supplies TEXT,
            status TEXT NOT NULL DEFAULT 'Active'
        );
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT NOT NULL,
            minimum_stock REAL NOT NULL,
            status TEXT NOT NULL,
            supplier_id INTEGER,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        );
        CREATE TABLE IF NOT EXISTS restock_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inventory_id INTEGER NOT NULL,
            supplier_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            order_date TEXT NOT NULL DEFAULT CURRENT_DATE,
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (inventory_id) REFERENCES inventory(id),
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        );
        """
    )
    inventory_columns = {row[1] for row in cursor.execute("PRAGMA table_info(inventory)").fetchall()}
    if "supplier_id" not in inventory_columns:
        cursor.execute("ALTER TABLE inventory ADD COLUMN supplier_id INTEGER")
    restock_columns = {row[1] for row in cursor.execute("PRAGMA table_info(restock_orders)").fetchall()}
    if "order_date" not in restock_columns:
        cursor.execute("ALTER TABLE restock_orders ADD COLUMN order_date TEXT")
        cursor.execute("UPDATE restock_orders SET order_date = DATE(created_at) WHERE order_date IS NULL")
    if cursor.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0] == 0:
        cursor.executemany("INSERT INTO suppliers (name, contact_name, email, phone, supplies, status) VALUES (?, ?, ?, ?, ?, ?)", SUPPLIER_DATA)
    if cursor.execute("SELECT COUNT(*) FROM inventory").fetchone()[0] == 0:
        cursor.executemany("INSERT INTO inventory (name, category, quantity, unit, minimum_stock, status) VALUES (?, ?, ?, ?, ?, ?)", INVENTORY_DATA)
    if cursor.execute("SELECT COUNT(*) FROM restock_orders").fetchone()[0] == 0:
        cursor.executemany("INSERT INTO restock_orders (inventory_id, supplier_id, quantity, status) VALUES (?, ?, ?, ?)", RESTOCK_DATA)
    connection.commit()
    connection.close()


if __name__ == "__main__":
    initialise_database()
