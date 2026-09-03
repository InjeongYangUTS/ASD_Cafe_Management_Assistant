-- =====================================================================
-- Student 1 (Hangyeol Yi) - Customer Feedback & Reviews
-- Database microservice schema  (SQLite, owned by student-1-database)
--
-- OWNERSHIP RULE (ASD 2026 Release 0, Cross-Feature Database API
-- Integration):
--   feedback.db is opened by the student-1-database container and by
--   nothing else. Every other microservice - including my own
--   backend/API - reads and writes these tables only through the /db/*
--   HTTP endpoints in student-1/database/app.py.
--
--   customer_id  references shared auth  (shared/database/users.db)
--   order_id     references the Order service's orders table
--   Both are stored as plain reference values plus a snapshot of the
--   name / order number at submission time. We never join into another
--   service's database, so a review still renders correctly even when
--   the owning service is down.
-- =====================================================================

PRAGMA foreign_keys = ON;


-- ---------------------------------------------------------------------
-- customer_feedback : one row per review submitted by a customer
--
-- The AI columns (sentiment .. analysed_at) are filled in by the
-- backend after an AI-Mode run. They are nullable: a review is valid
-- before it has ever been analysed, and re-analysing simply overwrites
-- them.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS customer_feedback (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    -- who wrote it (reference + snapshot, owned by shared auth)
    customer_id     INTEGER NOT NULL,
    customer_name   TEXT,

    -- what it is about (reference + snapshot, owned by the Order service)
    order_id        INTEGER,
    order_number    TEXT,

    -- the review itself
    rating          INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    title           TEXT,
    comment         TEXT    NOT NULL,
    category        TEXT    NOT NULL DEFAULT 'GENERAL'
                    CHECK (category IN ('FOOD', 'DRINK', 'SERVICE',
                                        'CLEANLINESS', 'WAIT_TIME',
                                        'PRICE', 'GENERAL')),

    -- staff workflow state
    status          TEXT    NOT NULL DEFAULT 'SUBMITTED'
                    CHECK (status IN ('SUBMITTED', 'ACKNOWLEDGED',
                                      'IN_REVIEW', 'RESOLVED', 'ARCHIVED')),
    staff_response  TEXT,

    -- AI-Mode results (Ollama -> approved LLM), written back by the backend
    sentiment       TEXT    CHECK (sentiment IN ('POSITIVE', 'NEUTRAL', 'NEGATIVE')),
    sentiment_score REAL    CHECK (sentiment_score BETWEEN -1.0 AND 1.0),
    ai_summary      TEXT,
    ai_issues       TEXT,                       -- JSON array of issue tags
    ai_model        TEXT,                       -- e.g. 'qwen2.5' or 'heuristic'
    analysed_at     DATETIME,

    submitted_at    DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at      DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_feedback_customer  ON customer_feedback (customer_id);
CREATE INDEX IF NOT EXISTS idx_feedback_status    ON customer_feedback (status);
CREATE INDEX IF NOT EXISTS idx_feedback_sentiment ON customer_feedback (sentiment);
CREATE INDEX IF NOT EXISTS idx_feedback_submitted ON customer_feedback (submitted_at);


-- ---------------------------------------------------------------------
-- store_logs : append-only audit trail of everything that happens to a
-- review - created, updated, deleted, analysed, status changed.
--
-- DESIGN NOTE (deliberate, and explained in the technical report):
--   feedback_id is a plain INTEGER, NOT a foreign key with ON DELETE
--   CASCADE. The whole point of this table is to record deletions, so
--   the log entry must outlive the row it describes. A cascade would
--   erase exactly the evidence we are trying to keep.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS store_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    feedback_id INTEGER,                        -- reference only; survives deletion
    entity      TEXT    NOT NULL DEFAULT 'customer_feedback',
    action      TEXT    NOT NULL
                CHECK (action IN ('CREATED', 'UPDATED', 'DELETED',
                                  'ANALYSED', 'STATUS_CHANGED', 'RESPONDED')),
    actor       TEXT    NOT NULL DEFAULT 'system',   -- 'customer:7', 'staff:2', 'ai'
    actor_role  TEXT    NOT NULL DEFAULT 'SYSTEM'
                CHECK (actor_role IN ('CUSTOMER', 'STAFF', 'SYSTEM', 'AI')),
    detail      TEXT,
    created_at  DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_logs_feedback ON store_logs (feedback_id);
CREATE INDEX IF NOT EXISTS idx_logs_action   ON store_logs (action);
CREATE INDEX IF NOT EXISTS idx_logs_created  ON store_logs (created_at);


-- ---------------------------------------------------------------------
-- Keep customer_feedback.updated_at fresh on every UPDATE.
-- The guard stops the trigger recursing into itself.
-- ---------------------------------------------------------------------
CREATE TRIGGER IF NOT EXISTS trg_feedback_updated_at
AFTER UPDATE ON customer_feedback
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE customer_feedback SET updated_at = datetime('now') WHERE id = OLD.id;
END;
