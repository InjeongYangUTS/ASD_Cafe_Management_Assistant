PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    customer_id INTEGER,
    amount REAL NOT NULL CHECK (amount >= 0),
    payment_method TEXT NOT NULL,
    payment_status TEXT NOT NULL DEFAULT 'pending',
    paid_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_id INTEGER NOT NULL,
    transaction_reference TEXT UNIQUE NOT NULL,
    transaction_type TEXT NOT NULL DEFAULT 'payment',
    amount REAL NOT NULL CHECK (amount >= 0),
    status TEXT NOT NULL,
    processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (payment_id) REFERENCES payments(id)
);

CREATE TABLE IF NOT EXISTS refunds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_id INTEGER NOT NULL,
    transaction_id INTEGER,
    refund_amount REAL NOT NULL CHECK (refund_amount > 0),
    refund_reason TEXT NOT NULL,
    refund_status TEXT NOT NULL DEFAULT 'pending',
    requested_by INTEGER,
    requested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    processed_at DATETIME,
    FOREIGN KEY (payment_id) REFERENCES payments(id),
    FOREIGN KEY (transaction_id) REFERENCES transactions(id)
);