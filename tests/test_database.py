"""Schema creation and the additive migration path."""

import os
import sqlite3
import unittest

from backend import database
from tests.helpers import TempDBTestCase


class SchemaTests(TempDBTestCase):
    def test_core_tables_exist(self):
        conn = database.get_connection()
        names = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertLessEqual({"applications", "application_events", "request_log"}, names)

    def test_tracker_columns_present_on_fresh_db(self):
        conn = database.get_connection()
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(application_events)")}
        self.assertIn("scheduled_for", cols)
        self.assertIn("item_status", cols)
        self.assertIn("gmail_message_id", cols)

    def test_foreign_keys_cascade(self):
        conn = database.get_connection()
        conn.execute(
            "INSERT INTO applications (company, position, application_date, "
            "created_at, updated_at) VALUES ('A', 'B', '2026-01-01', '', '')")
        app_id = conn.execute("SELECT id FROM applications").fetchone()["id"]
        conn.execute(
            "INSERT INTO application_events (application_id, event_type, "
            "event_date, created_at) VALUES (?, 'X', '2026-01-01', '')", (app_id,))
        conn.commit()
        conn.execute("DELETE FROM applications WHERE id = ?", (app_id,))
        conn.commit()
        self.assertEqual(
            0, conn.execute("SELECT COUNT(*) c FROM application_events").fetchone()["c"])


class MigrationTests(TempDBTestCase):
    """Apply the migration to a pre-Tracker database and prove it's idempotent."""

    create_db = False  # we seed an old-shape database ourselves

    def setUp(self):
        super().setUp()
        database.ensure_data_dirs()

    def _legacy_db(self):
        """The application_events table as it was before gmail_message_id /
        scheduled_for / item_status existed."""
        conn = sqlite3.connect(database.DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT NOT NULL, position TEXT NOT NULL,
                location TEXT, application_date TEXT NOT NULL,
                current_stage TEXT NOT NULL DEFAULT 'Applied',
                outcome TEXT NOT NULL DEFAULT 'Pending',
                source TEXT, job_url TEXT, job_description TEXT, notes TEXT,
                max_stage_reached TEXT NOT NULL DEFAULT 'Applied',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE application_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER NOT NULL,
                event_type TEXT NOT NULL, event_date TEXT NOT NULL,
                description TEXT, source TEXT NOT NULL DEFAULT 'manual',
                created_at TEXT NOT NULL);
            """
        )
        conn.commit()
        return conn

    def test_migration_adds_columns_and_is_idempotent(self):
        conn = self._legacy_db()
        database._migrate_schema(conn)
        database._migrate_schema(conn)  # second run must be a no-op, not an error
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(application_events)")}
        self.assertLessEqual({"gmail_message_id", "scheduled_for", "item_status"}, cols)
        conn.close()

    def test_migration_backs_up_existing_data(self):
        conn = self._legacy_db()
        conn.execute(
            "INSERT INTO applications (company, position, application_date, "
            "created_at, updated_at) VALUES ('Real', 'Role', '2026-01-01', '', '')")
        conn.commit()
        conn.close()
        database.get_connection()  # triggers migration + backup
        backups = os.listdir(database.BACKUP_DIR)
        self.assertTrue(any(b.startswith("pre_migration_") for b in backups), backups)


if __name__ == "__main__":
    unittest.main()
