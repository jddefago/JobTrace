"""Local HTTP server: thin glue between HTTP requests and repository.py.

Deliberately built on the Python standard library only (http.server +
sqlite3), so the whole app runs with nothing but python.exe -- no pip
install required for day-to-day use. Business logic and validation live
in repository.py / validation.py; this file only translates HTTP <-> Python.
"""

import json
import mimetypes
import os
import re
import sys
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import constants, database, repository, validation
from backend.sync import config as sync_config, doctor as sync_doctor, state as sync_state
from backend.sync.runner import (
    runner as sync_runner, last_run as sync_last_run, autosync_due,
)

FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend"
)
HOST = "127.0.0.1"
PORT = 8766

ROUTES = []


def _q(query, key, default=None):
    """First value for `key` in a urllib.parse.parse_qs() dict, or `default`."""
    return query.get(key, [default])[0]


def route(method, pattern):
    regex = re.compile("^" + pattern + "$")

    def decorator(fn):
        ROUTES.append((method, regex, fn))
        return fn

    return decorator


# ---------------------------------------------------------------------------
# API handlers
# ---------------------------------------------------------------------------

@route("GET", r"/api/health")
def health(handler, match, query, body):
    return 200, {"status": "ok"}


@route("GET", r"/api/meta")
def meta(handler, match, query, body):
    return 200, {
        "stages": constants.ALL_STAGES,
        "stage_progression": constants.STAGE_PROGRESSION,
        "outcomes": constants.OUTCOMES,
        "default_sources": constants.DEFAULT_SOURCES,
        "default_event_types": constants.DEFAULT_EVENT_TYPES,
    }


@route("GET", r"/api/meta/distinct")
def meta_distinct(handler, match, query, body):
    return 200, repository.get_distinct_values()


@route("GET", r"/api/applications")
def list_applications(handler, match, query, body):
    result = repository.list_applications(
        search=_q(query, "search"),
        stage=_q(query, "stage"),
        outcome=_q(query, "outcome"),
        company=_q(query, "company"),
        source=_q(query, "source"),
        location=_q(query, "location"),
        date_from=_q(query, "date_from"),
        date_to=_q(query, "date_to"),
        sort_by=_q(query, "sort_by", "application_date"),
        sort_order=_q(query, "sort_order", "desc"),
        page=_q(query, "page", 1),
        page_size=_q(query, "page_size", 50),
    )
    return 200, result


@route("POST", r"/api/applications")
def create_application(handler, match, query, body):
    client_request_id = body.get("client_request_id")
    app = repository.create_application(body, client_request_id=client_request_id)
    return 201, app


@route("GET", r"/api/applications/(?P<id>\d+)")
def get_application(handler, match, query, body):
    app = repository.get_application(int(match.group("id")))
    if app is None:
        return 404, {"error": "Application not found"}
    return 200, app


@route("PUT", r"/api/applications/(?P<id>\d+)")
def update_application(handler, match, query, body):
    app = repository.update_application(int(match.group("id")), body)
    if app is None:
        return 404, {"error": "Application not found"}
    return 200, app


@route("DELETE", r"/api/applications/(?P<id>\d+)")
def delete_application(handler, match, query, body):
    ok = repository.delete_application(int(match.group("id")))
    if not ok:
        return 404, {"error": "Application not found"}
    return 200, {"deleted": True}


@route("POST", r"/api/applications/(?P<id>\d+)/events")
def add_event(handler, match, query, body):
    application_id = int(match.group("id"))
    event = repository.add_event(
        application_id,
        event_type=body.get("event_type"),
        event_date=body.get("event_date"),
        description=body.get("description", ""),
        source="manual",
        scheduled_for=body.get("scheduled_for"),
        item_status=body.get("item_status"),
    )
    if event is None:
        return 404, {"error": "Application not found"}
    return 201, event


@route("PUT", r"/api/events/(?P<id>\d+)")
def update_event(handler, match, query, body):
    event = repository.update_event(int(match.group("id")), body)
    if event is None:
        return 404, {"error": "Event not found"}
    return 200, event


@route("DELETE", r"/api/events/(?P<id>\d+)")
def delete_event(handler, match, query, body):
    ok = repository.delete_event(int(match.group("id")))
    if not ok:
        return 404, {"error": "Event not found"}
    return 200, {"deleted": True}


@route("GET", r"/api/tracker")
def tracker(handler, match, query, body):
    return 200, repository.get_tracker()


@route("PUT", r"/api/events/(?P<id>\d+)/schedule")
def set_event_schedule(handler, match, query, body):
    result = repository.set_item_schedule(int(match.group("id")), (body or {}).get("scheduled_for", ""))
    if result is None:
        return 404, {"error": "Event not found"}
    return 200, result


@route("POST", r"/api/applications/(?P<id>\d+)/assessment-complete")
def assessment_complete(handler, match, query, body):
    completed = (body or {}).get("completed", True)
    result = repository.complete_assessment(int(match.group("id")), completed=bool(completed))
    if result is None:
        return 404, {"error": "Application not found"}
    return 200, result


@route("POST", r"/api/events/(?P<id>\d+)/interview-result")
def interview_result(handler, match, query, body):
    result = repository.set_interview_result(int(match.group("id")), (body or {}).get("result"))
    if result is None:
        return 404, {"error": "Interview item not found"}
    return 200, result


def _require_app_id(body):
    try:
        return int((body or {}).get("application_id"))
    except (TypeError, ValueError):
        raise validation.ValidationError("application_id is required", "application_id")


@route("POST", r"/api/tracker/interviews")
def add_tracker_interview(handler, match, query, body):
    body = body or {}
    result = repository.add_tracker_interview(
        _require_app_id(body),
        body.get("scheduled_for", ""),
        body.get("round", "Interview 1"),
        body.get("description", ""),
    )
    if result is None:
        return 404, {"error": "Application not found"}
    return 201, result


@route("POST", r"/api/tracker/assessments")
def add_tracker_assessment(handler, match, query, body):
    body = body or {}
    result = repository.add_tracker_assessment(
        _require_app_id(body),
        body.get("scheduled_for", ""),
        body.get("description", ""),
    )
    if result is None:
        return 404, {"error": "Application not found"}
    return 201, result


@route("GET", r"/api/stats/summary")
def stats_summary(handler, match, query, body):
    return 200, repository.get_summary_stats()


@route("GET", r"/api/stats/analytics")
def stats_analytics(handler, match, query, body):
    granularity = _q(query, "granularity", "day")
    if granularity not in ("day", "week", "month"):
        granularity = "day"
    return 200, repository.get_analytics(granularity)


@route("GET", r"/api/gmail/sync-status")
def gmail_sync_status(handler, match, query, body):
    # The sync itself is done either by an AI assistant (manual), the runner
    # shelling out to a CLI, or the runner running the keys-based job
    # in-process. All three write data/gmail_sync_state.json the same way.
    state = sync_state.load_sync_state()
    cfg = sync_config.load()
    return 200, {
        "lastSuccessfulSync": state.get("lastSuccessfulSync"),
        "connectedAccount": state.get("connectedAccount"),
        "lastSyncResult": state.get("lastSyncResult"),
        "unresolvedCount": len(sync_state.load_unresolved()),
        "processedMessageCount": len(state.get("processedMessageIds", [])),
        "method": cfg["method"],
        "autoEnabled": cfg["method"] != "manual",
        "running": sync_runner.is_running,
        "lastRun": sync_last_run(),
    }


@route("GET", r"/api/gmail/unresolved")
def gmail_unresolved(handler, match, query, body):
    return 200, {"items": sync_state.load_unresolved()}


@route("DELETE", r"/api/gmail/unresolved/(?P<id>\d+)")
def gmail_unresolved_delete(handler, match, query, body):
    # Used both for "discard" and to clear an item the user has just turned
    # into (or attached to) an application from the dashboard.
    items = sync_state.load_unresolved()
    removed = sync_state.remove_unresolved_item(items, int(match.group("id")))
    if not removed:
        return 404, {"error": "Unresolved item not found"}
    sync_state.save_unresolved(items)
    return 200, {"deleted": True}


# --- Sync configuration + automation ------------------------------------

@route("GET", r"/api/sync/config")
def sync_config_get(handler, match, query, body):
    return 200, sync_config.get_public()


@route("PUT", r"/api/sync/config")
def sync_config_put(handler, match, query, body):
    updated = sync_config.update(body or {})
    sync_doctor.invalidate()  # next GET /api/sync/doctor recomputes
    return 200, updated


@route("GET", r"/api/sync/doctor")
def sync_doctor_get(handler, match, query, body):
    force = _q(query, "force", "0") in ("1", "true", "yes")
    return 200, sync_doctor.report(force=force)


@route("POST", r"/api/sync/test-imap")
def sync_test_imap(handler, match, query, body):
    return 200, sync_doctor.check_imap_login()


@route("POST", r"/api/sync/run")
def sync_run_now(handler, match, query, body):
    # ifStale: the dashboard-load auto-trigger. Runs only if a non-manual
    # method is configured and nothing has synced yet today; otherwise a
    # quiet no-op. Without the flag (the Update button) it always runs.
    if (body or {}).get("ifStale"):
        if not autosync_due(sync_config.load()):
            return 202, {"started": False, "skipped": True}
        return 202, sync_runner.run_now_async(trigger="dashboard")
    return 202, sync_runner.run_now_async(trigger="manual")


@route("GET", r"/api/export/json")
def export_json(handler, match, query, body):
    data = repository.export_all_json()
    payload = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Disposition", 'attachment; filename="applications_export.json"')
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)
    return None


@route("GET", r"/api/export/csv")
def export_csv(handler, match, query, body):
    csv_text = repository.export_all_csv()
    payload = csv_text.encode("utf-8-sig")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/csv; charset=utf-8")
    handler.send_header("Content-Disposition", 'attachment; filename="applications_export.csv"')
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)
    return None


@route("POST", r"/api/import/csv")
def import_csv(handler, match, query, body_raw_text):
    valid_rows, errors = repository.parse_and_validate_csv_import(body_raw_text)
    if errors:
        return 400, {"error": "Import validation failed", "row_errors": errors, "valid_row_count": len(valid_rows)}
    inserted_ids = repository.import_applications(valid_rows)
    return 200, {"inserted": len(inserted_ids), "application_ids": inserted_ids}


@route("POST", r"/api/backup")
def backup(handler, match, query, body):
    path = repository.backup_database()
    return 200, {"backup_path": path, "filename": os.path.basename(path)}


# ---------------------------------------------------------------------------
# HTTP plumbing
# ---------------------------------------------------------------------------

CSV_ROUTES = {("POST", "/api/import/csv")}


class Handler(BaseHTTPRequestHandler):
    server_version = "JobTrackerHTTP/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _read_body(self, as_json=True):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length > 0 else b""
        if not as_json:
            return raw.decode("utf-8", errors="replace")
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise validation.ValidationError("Request body must be valid JSON")

    def _send_json(self, status, data):
        payload = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _dispatch(self, method):
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)
        query = urllib.parse.parse_qs(parsed.query)

        if not path.startswith("/api/"):
            if method == "GET":
                self._serve_static(path)
            else:
                self._send_json(405, {"error": "Method not allowed"})
            return

        for route_method, regex, fn in ROUTES:
            if route_method != method:
                continue
            match = regex.match(path)
            if not match:
                continue
            try:
                as_json = (method, path) not in CSV_ROUTES
                body = self._read_body(as_json=as_json) if method in ("POST", "PUT") else None
                result = fn(self, match, query, body)
                if result is None:
                    return
                status, data = result
                self._send_json(status, data)
            except validation.ValidationError as e:
                self._send_json(400, {"error": e.message, "field": e.field})
            except Exception as e:
                traceback.print_exc()
                self._send_json(500, {"error": "Internal server error", "detail": str(e)})
            return

        self._send_json(404, {"error": "Not found"})

    def _serve_static(self, path):
        if path == "/":
            path = "/index.html"
        safe_path = os.path.normpath(path).lstrip("\\/")
        full_path = os.path.abspath(os.path.join(FRONTEND_DIR, safe_path))

        if not full_path.startswith(os.path.abspath(FRONTEND_DIR)):
            self._send_json(403, {"error": "Forbidden"})
            return
        if not os.path.isfile(full_path):
            self._send_json(404, {"error": "Not found"})
            return

        content_type, _ = mimetypes.guess_type(full_path)
        content_type = content_type or "application/octet-stream"
        with open(full_path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")


def main():
    database.ensure_data_dirs()
    database.get_connection()  # creates schema on first run
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"JobTrace server running at http://{HOST}:{PORT}")
    print(f"Database: {database.DB_PATH}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
