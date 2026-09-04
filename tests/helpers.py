"""Shared test scaffolding: redirect the app's data files into a throwaway
directory so tests never touch a real install's data/."""

import os
import shutil
import tempfile
import threading
import unittest

from backend import database
from backend.sync import config as sync_config


# --- module-level redirect helpers (usable from setUp and setUpClass) -------

def redirect_database(tmp_root):
    """Point database.{DATA_DIR,BACKUP_DIR,DB_PATH} at a temp tree and drop
    any cached thread-local connection. Returns a token for restore_database."""
    token = (database.DATA_DIR, database.BACKUP_DIR, database.DB_PATH)
    database.DATA_DIR = os.path.join(tmp_root, "data")
    database.BACKUP_DIR = os.path.join(tmp_root, "backups")
    database.DB_PATH = os.path.join(database.DATA_DIR, "applications.db")
    database._local = threading.local()
    return token


def restore_database(token):
    conn = getattr(database._local, "conn", None)
    if conn is not None:
        conn.close()
    database.DATA_DIR, database.BACKUP_DIR, database.DB_PATH = token
    database._local = threading.local()


def redirect_sync_config(tmp_root):
    token = sync_config.CONFIG_PATH
    sync_config.CONFIG_PATH = os.path.join(tmp_root, "sync_config.json")
    return token


def restore_sync_config(token):
    sync_config.CONFIG_PATH = token


# --- base test cases ------------------------------------------------------

class TempDBTestCase(unittest.TestCase):
    """Each test gets a fresh SQLite database in a temp directory. Set
    ``create_db = False`` to get the redirect without an initial schema
    (e.g. to seed a pre-migration database yourself)."""

    create_db = True

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="jobtrace-test-")
        self._db_token = redirect_database(self._tmp)
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.addCleanup(restore_database, self._db_token)
        if self.create_db:
            database.get_connection()

    def make_application(self, **overrides):
        from backend import repository
        payload = {"company": "Example Co", "position": "Engineer",
                   "application_date": "2026-01-15"}
        payload.update(overrides)
        return repository.create_application(payload)


class SyncConfigTestCase(unittest.TestCase):
    """Redirects sync_config.CONFIG_PATH into a temp directory."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="jobtrace-cfg-")
        self._cfg_token = redirect_sync_config(self._tmp)
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.addCleanup(restore_sync_config, self._cfg_token)
