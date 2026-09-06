"""Boot the real HTTP server against a temp database and smoke every route."""

import json
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from backend import database
from tests.helpers import (
    redirect_database, restore_database, redirect_sync_config, restore_sync_config,
    redirect_sync_state, restore_sync_state,
)


class ServerSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="jobtrace-srv-")
        cls._db_token = redirect_database(cls._tmp)
        cls._cfg_token = redirect_sync_config(cls._tmp)
        cls._state_token = redirect_sync_state(cls._tmp)
        database.get_connection()

        from backend import server

        class QuietHandler(server.Handler):
            def log_message(self, *a):  # keep test output clean
                pass

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        restore_sync_state(cls._state_token)
        restore_database(cls._db_token)
        restore_sync_config(cls._cfg_token)
        shutil.rmtree(cls._tmp, ignore_errors=True)

    # -- helpers ----------------------------------------------------------
    def _req(self, method, path, body=None):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"null")

    # -- tests ----------------------------------------------------------
    def test_read_routes_ok(self):
        for path in ("/api/health", "/api/meta", "/api/meta/distinct",
                     "/api/applications", "/api/tracker", "/api/stats/summary",
                     "/api/stats/analytics", "/api/gmail/sync-status",
                     "/api/gmail/unresolved", "/api/sync/config", "/api/sync/doctor"):
            status, _ = self._req("GET", path)
            self.assertEqual(200, status, path)

    def test_application_lifecycle_over_http(self):
        status, app = self._req("POST", "/api/applications", {
            "company": "HTTP Co", "position": "Dev", "application_date": "2026-04-01"})
        self.assertEqual(201, status)
        app_id = app["id"]

        status, got = self._req("GET", f"/api/applications/{app_id}")
        self.assertEqual(200, status)
        self.assertEqual("HTTP Co", got["company"])

        status, _ = self._req("PUT", f"/api/applications/{app_id}", {"current_stage": "Screening"})
        self.assertEqual(200, status)

        status, _ = self._req("POST", f"/api/applications/{app_id}/events",
                              {"event_type": "Recruiter Contact", "event_date": "2026-04-02"})
        self.assertEqual(201, status)

        status, _ = self._req("DELETE", f"/api/applications/{app_id}")
        self.assertEqual(200, status)
        status, _ = self._req("GET", f"/api/applications/{app_id}")
        self.assertEqual(404, status)

    def test_bad_payload_is_400_not_500(self):
        status, body = self._req("POST", "/api/applications", {"company": ""})
        self.assertEqual(400, status)
        self.assertIn("error", body)

    def test_unknown_route_is_404(self):
        status, _ = self._req("GET", "/api/nope")
        self.assertEqual(404, status)

    def test_unresolved_item_delete(self):
        from backend.sync import state as sync_state
        items = sync_state.load_unresolved()
        row = sync_state.add_unresolved_item(items, {
            "gmailMessageId": "m-http", "reason": "test", "body": "hello world"})
        sync_state.save_unresolved(items)

        status, listing = self._req("GET", "/api/gmail/unresolved")
        self.assertEqual(200, status)
        self.assertEqual("hello world", listing["items"][-1]["body"])

        status, body = self._req("DELETE", f"/api/gmail/unresolved/{row['id']}")
        self.assertEqual(200, status)
        self.assertTrue(body["deleted"])

        status, _ = self._req("DELETE", f"/api/gmail/unresolved/{row['id']}")
        self.assertEqual(404, status)

    def test_sync_config_put_roundtrip(self):
        status, _ = self._req("PUT", "/api/sync/config", {"auto": {"interval_hours": 12}})
        self.assertEqual(200, status)
        status, cfg = self._req("GET", "/api/sync/config")
        self.assertEqual(12, cfg["auto"]["interval_hours"])


if __name__ == "__main__":
    unittest.main()
