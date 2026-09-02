-- =====================================================================
-- Student 4 (Stella Kwon) - Order & Kitchen Management
-- Database microservice schema  (SQLite, owned by student-4-database)
--
-- OWNERSHIP RULE (ASD 2026 Release 0):
--   This SQLite file is owned exclusively by the student-4-database
--   container. No other backend/API microservice may open this file or
--   read these tables directly. All access goes through the
--   /db/* HTTP API exposed by student-4/database/app.py.
--
--   Likewise, menu_id references data OWNED BY STUDENT 2 and stock is
--   OWNED BY STUDENT 3. We store menu_id only as a reference value plus
--   a snapshot of the name/price at the time of ordering. We never join
--   into their databases.
-- =====================================================================

PRAGMA foreign_keys = ON;


-- ---------------------------------------------------------------------
-- orders : one row per customer order (POS ticket)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    order_number    TEXT    NOT NULL UNIQUE,          -- human ticket no. e.g. A-1007
    channel         TEXT    NOT NULL DEFAULT 'DINE_IN' CHECK (channel IN ('DINE_IN', 'TAKEAWAY')),
    table_number    TEXT,                             -- NULL for takeaway
    customer_id     INTEGER,                          -- reference to shared auth customers.id
    customer_name   TEXT,                             -- snapshot from shared auth session
    staff_id        INTEGER,                          -- reference to shared auth staff.id
    staff_name      TEXT,
    status          TEXT    NOT NULL DEFAULT 'PENDING'
                    CHECK (status IN ('PENDING', 'CONFIRMED', 'PREPARING', 'READY', 'COMPLETED', 'CANCELLED')),
    item_count      INTEGER NOT NULL DEFAULT 0,
    total_amount    REAL    NOT NULL DEFAULT 0,
    prep_seconds    INTEGER NOT NULL DEFAULT 0,       -- estimated total preparation workload
    note            TEXT,
    stock_deducted  INTEGER NOT NULL DEFAULT 0,       -- 1 once Inventory API confirmed the deduction
    placed_at       DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at      DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_orders_status    ON orders (status);
CREATE INDEX IF NOT EXISTS idx_orders_placed_at ON orders (placed_at);


-- ---------------------------------------------------------------------
-- order_items : line items of an order
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS order_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id     INTEGER NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
    menu_id      INTEGER NOT NULL,                    -- reference only (owned by Student 2)
    menu_name    TEXT    NOT NULL,                    -- price/name snapshot at order time
    unit_price   REAL    NOT NULL,
    quantity     INTEGER NOT NULL CHECK (quantity > 0),
    line_total   REAL    NOT NULL,
    station      TEXT    NOT NULL DEFAULT 'BAR' CHECK (station IN ('BAR', 'KITCHEN', 'PASTRY')),
    prep_seconds INTEGER NOT NULL DEFAULT 60,
    item_status  TEXT    NOT NULL DEFAULT 'PENDING'
                 CHECK (item_status IN ('PENDING', 'PREPARING', 'READY', 'CANCELLED')),
    note         TEXT
);

CREATE INDEX IF NOT EXISTS idx_items_order   ON order_items (order_id);
CREATE INDEX IF NOT EXISTS idx_items_station ON order_items (station);


-- ---------------------------------------------------------------------
-- order_statuses : append-only status history for every order
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS order_statuses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
    status      TEXT    NOT NULL
                CHECK (status IN ('PENDING', 'CONFIRMED', 'PREPARING', 'READY', 'COMPLETED', 'CANCELLED')),
    changed_by  TEXT    NOT NULL DEFAULT 'system',
    note        TEXT,
    changed_at  DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_status_order ON order_statuses (order_id);


-- ---------------------------------------------------------------------
-- Keep orders.updated_at fresh on every UPDATE
-- ---------------------------------------------------------------------
CREATE TRIGGER IF NOT EXISTS trg_orders_updated_at
AFTER UPDATE ON orders
FOR EACH ROW
BEGIN
    UPDATE orders SET updated_at = datetime('now') WHERE id = OLD.id;
END;
