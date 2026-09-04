"""Low-level SQLite access: connection factory and schema management.

This module owns *where* the database lives and *what shape* it has. It
knows nothing about HTTP or business rules -- that lives in repository.py.
A future standalone script (e.g. a Gmail-polling worker) can import this
module directly to get a connection to the same database.
"""

import datetime
import os
import sqlite3
import threading

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "applications.db")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")

SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    company             TEXT    NOT NULL,
    position            TEXT    NOT NULL,
    location            TEXT,
    application_date    TEXT    NOT NULL,
    current_stage       TEXT    NOT NULL DEFAULT 'Applied',
    outcome             TEXT    NOT NULL DEFAULT 'Pending',
    source              TEXT,
    job_url             TEXT,
    job_description     TEXT,
    notes               TEXT,
    max_stage_reached   TEXT    NOT NULL DEFAULT 'Applied',
    created_at          TEXT    NOT NULL,
    updated_at          TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS application_events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id      INTEGER NOT NULL,
    event_type          TEXT    NOT NULL,
    event_date          TEXT    NOT NULL,
    description         TEXT,
    source              TEXT    NOT NULL DEFAULT 'manual',
    gmail_message_id    TEXT,          -- the Gmail message an event came from
    scheduled_for       TEXT,          -- Tracker: assessment due / interview slot
    item_status         TEXT,          -- Tracker: this item's own outcome
    created_at          TEXT    NOT NULL,
    FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE
);

-- Guards against duplicate inserts caused by double-clicking "Add" or a
-- retried request from a future automation script. Rows are cheap and are
-- never read except for existence checks, so no cleanup job is needed.
CREATE TABLE IF NOT EXISTS request_log (
    client_request_id   TEXT PRIMARY KEY,
    application_id      INTEGER,
    created_at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_applications_company ON applications(company);
CREATE INDEX IF NOT EXISTS idx_applications_stage ON applications(current_stage);
CREATE INDEX IF NOT EXISTS idx_applications_outcome ON applications(outcome);
CREATE INDEX IF NOT EXISTS idx_applications_date ON applications(application_date);
CREATE INDEX IF NOT EXISTS idx_applications_source ON applications(source);
CREATE INDEX IF NOT EXISTS idx_events_application_id ON application_events(application_id);
"""

_local = threading.local()


def ensure_data_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)


def _backup_database(reason):
    """Copy the live DB to backups/ before a migration touches it. Caller
    decides when it's warranted (i.e. there are real columns to add)."""
    ensure_data_dirs()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"{reason}_{timestamp}.db")
    src = sqlite3.connect(DB_PATH)
    dest = sqlite3.connect(backup_path)
    try:
        src.backup(dest)
    finally:
        dest.close()
        src.close()


def _column_names(conn, table):
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


# Columns added after a table's original CREATE. On a fresh database these are
# already in SCHEMA, so _migrate_schema is a genuine no-op; it only does work
# for a database created by an older JobTrace.
_MIGRATIONS = {
    "application_events": [
        ("gmail_message_id", "TEXT"),
        ("scheduled_for", "TEXT"),
        ("item_status", "TEXT"),
    ],
}


def _migrate_schema(conn):
    """Idempotent, additive-only migrations for databases created before a
    given column existed. Never drops or rewrites existing data."""
    pending = [
        (table, col, decl)
        for table, cols in _MIGRATIONS.items()
        for col, decl in cols
        if col not in _column_names(conn, table)
    ]
    if pending and os.path.exists(DB_PATH):
        _backup_database("pre_migration")
    for table, col, decl in pending:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_gmail_message_id "
        "ON application_events(gmail_message_id)"
    )
    conn.commit()


def get_connection():
    """Return a connection for the current thread, creating the DB/schema
    on first use. The server is threaded, so each worker thread gets its
    own connection (sqlite3 connections are not thread-safe to share).
    """
    conn = getattr(_local, "conn", None)
    if conn is not None:
        return conn

    ensure_data_dirs()
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.executescript(SCHEMA)
    conn.commit()
    _migrate_schema(conn)
    _local.conn = conn
    return conn


def new_connection():
    """Open a fresh, independent connection. Intended for standalone
    scripts (e.g. the Gmail sync helper, or a future automation worker)
    that are not part of the request-per-thread web server lifecycle.
    """
    ensure_data_dirs()
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.executescript(SCHEMA)
    conn.commit()
    _migrate_schema(conn)
    return conn
