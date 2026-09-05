PRAGMA foreign_keys = ON;


CREATE TABLE IF NOT EXISTS customer_feedback (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    customer_id     INTEGER NOT NULL,
    customer_name   TEXT,

    order_id        INTEGER,
    order_number    TEXT,

    rating          INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    title           TEXT,
    comment         TEXT    NOT NULL,
    category        TEXT    NOT NULL DEFAULT 'GENERAL'
                    CHECK (category IN ('FOOD', 'DRINK', 'SERVICE',
                                        'CLEANLINESS', 'WAIT_TIME',
                                        'PRICE', 'GENERAL')),

    status          TEXT    NOT NULL DEFAULT 'SUBMITTED'
                    CHECK (status IN ('SUBMITTED', 'ACKNOWLEDGED',
                                      'IN_REVIEW', 'RESOLVED', 'ARCHIVED')),
    staff_response  TEXT,

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


CREATE TRIGGER IF NOT EXISTS trg_feedback_updated_at
AFTER UPDATE ON customer_feedback
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE customer_feedback SET updated_at = datetime('now') WHERE id = OLD.id;
END;
