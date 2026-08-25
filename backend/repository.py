"""Business-logic layer: the single place that reads and writes
application data.

This is the module a future background worker (Gmail polling, AI
classification, etc.) should import directly -- it never needs to go
through the HTTP server. Keeping all business rules here (rather than in
server.py or the frontend) means automation and the UI can never
disagree about what a "stage change" means or how stats are computed.

Example of the kind of call a future script will make:

    from backend import repository as repo

    app = repo.find_matching_application(company="KLM", position="Management Trainee")
    if app:
        repo.add_event(app["id"], event_type="Assessment Invitation", event_date="2026-08-24")
        repo.update_application_stage(app["id"], stage="Assessment", outcome="Positive")
"""

import csv
import datetime
import io
import os
import shutil
import sqlite3
import threading

from . import constants, database, validation

_write_lock = threading.RLock()

LIST_SORT_COLUMNS = {
    "company": "company",
    "position": "position",
    "location": "location",
    "application_date": "application_date",
    "current_stage": "current_stage",
    "outcome": "outcome",
    "source": "source",
    "created_at": "created_at",
    "days_since_application": "application_date",
}

CSV_IMPORT_HEADERS = [
    "company",
    "position",
    "location",
    "application_date",
    "source",
    "job_url",
    "job_description",
    "stage",
    "outcome",
    "notes",
]

CSV_EXPORT_HEADERS = [
    "id",
    "company",
    "position",
    "location",
    "application_date",
    "current_stage",
    "outcome",
    "source",
    "job_url",
    "job_description",
    "notes",
    "created_at",
    "updated_at",
]

# A stage invitation (screening call, coffee chat, interview, etc.) counts
# as a response even if the user only advanced the stage and hasn't
# separately flipped outcome away from Pending yet.
HEARD_BACK_SQL = "(outcome != 'Pending' OR max_stage_reached != 'Applied')"
POSITIVE_SQL = "(outcome IN ('Positive', 'Accepted') OR (outcome = 'Pending' AND max_stage_reached != 'Applied'))"


def _now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _today_iso():
    return datetime.date.today().isoformat()


def _row_to_dict(row):
    return dict(row) if row is not None else None


def _stages_at_or_above(stage_name):
    min_rank = constants.STAGE_RANK[stage_name]
    return [s for s in constants.STAGE_PROGRESSION if constants.STAGE_RANK[s] >= min_rank]


def _advance_max_stage(current_max, new_stage):
    """Return the furthest progression stage reached so far. 'Closed' never
    overwrites max_stage_reached -- it is a terminal marker, not a
    progression step."""
    if new_stage not in constants.STAGE_RANK:
        return current_max
    if current_max not in constants.STAGE_RANK:
        return new_stage
    if constants.STAGE_RANK[new_stage] > constants.STAGE_RANK[current_max]:
        return new_stage
    return current_max


# ---------------------------------------------------------------------------
# Applications: CRUD
# ---------------------------------------------------------------------------

def create_application(data, client_request_id=None):
    with _write_lock:
        conn = database.get_connection()

        if client_request_id:
            existing = conn.execute(
                "SELECT application_id FROM request_log WHERE client_request_id = ?",
                (client_request_id,),
            ).fetchone()
            if existing is not None and existing["application_id"] is not None:
                return get_application(existing["application_id"])

        payload = dict(data or {})
        payload.setdefault("application_date", _today_iso())
        payload.setdefault("current_stage", constants.STAGE_PROGRESSION[0])
        payload.setdefault("outcome", constants.OUTCOMES[0])

        clean = validation.validate_application_payload(payload, partial=False)
        now = _now_iso()
        max_stage = clean["current_stage"] if clean["current_stage"] in constants.STAGE_RANK else constants.STAGE_PROGRESSION[0]

        try:
            cur = conn.execute(
                """
                INSERT INTO applications (
                    company, position, location, application_date, current_stage,
                    outcome, source, job_url, job_description, notes,
                    max_stage_reached, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clean["company"], clean["position"], clean.get("location", ""),
                    clean["application_date"], clean["current_stage"], clean["outcome"],
                    clean.get("source", ""), clean.get("job_url", ""),
                    clean.get("job_description", ""), clean.get("notes", ""),
                    max_stage, now, now,
                ),
            )
            application_id = cur.lastrowid

            _insert_event(
                conn, application_id, "Application Submitted",
                clean["application_date"], "", "system",
            )

            if client_request_id:
                conn.execute(
                    "INSERT OR IGNORE INTO request_log (client_request_id, application_id, created_at) VALUES (?, ?, ?)",
                    (client_request_id, application_id, now),
                )

            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            if client_request_id:
                existing = conn.execute(
                    "SELECT application_id FROM request_log WHERE client_request_id = ?",
                    (client_request_id,),
                ).fetchone()
                if existing is not None and existing["application_id"] is not None:
                    return get_application(existing["application_id"])
            raise
        except Exception:
            conn.rollback()
            raise

        return get_application(application_id)


def get_application(application_id):
    conn = database.get_connection()
    row = conn.execute(
        "SELECT * FROM applications WHERE id = ?", (application_id,)
    ).fetchone()
    if row is None:
        return None
    app = _row_to_dict(row)
    app["days_since_application"] = _days_since(app["application_date"])
    events = conn.execute(
        "SELECT * FROM application_events WHERE application_id = ? ORDER BY event_date ASC, id ASC",
        (application_id,),
    ).fetchall()
    app["events"] = [_row_to_dict(e) for e in events]
    return app


def _days_since(date_str):
    try:
        d = datetime.date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None
    return (datetime.date.today() - d).days


def list_applications(
    search=None, stage=None, outcome=None, company=None, source=None,
    location=None, date_from=None, date_to=None,
    sort_by="application_date", sort_order="desc", page=1, page_size=50,
):
    conn = database.get_connection()

    where = []
    params = []

    if search:
        where.append("(company LIKE ? OR position LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like])
    if stage:
        where.append("current_stage = ?")
        params.append(stage)
    if outcome:
        where.append("outcome = ?")
        params.append(outcome)
    if company:
        where.append("company LIKE ?")
        params.append(f"%{company}%")
    if source:
        where.append("source = ?")
        params.append(source)
    if location:
        where.append("location LIKE ?")
        params.append(f"%{location}%")
    if date_from:
        where.append("application_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("application_date <= ?")
        params.append(date_to)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    sort_col = LIST_SORT_COLUMNS.get(sort_by, "application_date")
    order = "ASC" if str(sort_order).lower() == "asc" else "DESC"
    if sort_by == "days_since_application":
        order = "DESC" if order == "ASC" else "ASC"

    total = conn.execute(
        f"SELECT COUNT(*) AS c FROM applications {where_sql}", params
    ).fetchone()["c"]

    page = max(1, int(page or 1))
    page_size = min(200, max(1, int(page_size or 50)))
    offset = (page - 1) * page_size

    rows = conn.execute(
        f"""
        SELECT id, company, position, location, application_date, current_stage,
               outcome, source, max_stage_reached, created_at, updated_at
        FROM applications
        {where_sql}
        ORDER BY {sort_col} {order}, id DESC
        LIMIT ? OFFSET ?
        """,
        params + [page_size, offset],
    ).fetchall()

    items = []
    for row in rows:
        item = _row_to_dict(row)
        item["days_since_application"] = _days_since(item["application_date"])
        items.append(item)

    return {"items": items, "total": total, "page": page, "page_size": page_size}


def update_application(application_id, data):
    with _write_lock:
        conn = database.get_connection()
        existing = conn.execute(
            "SELECT * FROM applications WHERE id = ?", (application_id,)
        ).fetchone()
        if existing is None:
            return None
        existing = _row_to_dict(existing)

        clean = validation.validate_application_payload(data or {}, partial=True)
        if not clean:
            return get_application(application_id)

        stage_changed = "current_stage" in clean and clean["current_stage"] != existing["current_stage"]
        outcome_changed = "outcome" in clean and clean["outcome"] != existing["outcome"]

        new_max_stage = existing["max_stage_reached"]
        if stage_changed:
            new_max_stage = _advance_max_stage(existing["max_stage_reached"], clean["current_stage"])

        now = _now_iso()
        set_parts = [f"{col} = ?" for col in clean]
        set_values = list(clean.values())
        set_parts.append("max_stage_reached = ?")
        set_values.append(new_max_stage)
        set_parts.append("updated_at = ?")
        set_values.append(now)

        try:
            conn.execute(
                f"UPDATE applications SET {', '.join(set_parts)} WHERE id = ?",
                set_values + [application_id],
            )

            today = _today_iso()
            if stage_changed:
                _insert_event(
                    conn, application_id, "Stage Update", today,
                    f"Stage changed to {clean['current_stage']}", "system",
                )
            if outcome_changed:
                _insert_event(
                    conn, application_id, "Outcome Update", today,
                    f"Outcome changed to {clean['outcome']}", "system",
                )

            conn.commit()
        except Exception:
            conn.rollback()
            raise

        return get_application(application_id)


def update_application_stage(application_id, stage, outcome=None):
    """Convenience wrapper matching the shape a future automation script
    is expected to call: update the pipeline stage and, optionally, the
    outcome in one go."""
    data = {"current_stage": stage}
    if outcome is not None:
        data["outcome"] = outcome
    return update_application(application_id, data)


def delete_application(application_id):
    with _write_lock:
        conn = database.get_connection()
        try:
            cur = conn.execute("DELETE FROM applications WHERE id = ?", (application_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return cur.rowcount > 0


def find_matching_application(company, position=None):
    """Find the most recent application for a company (optionally
    narrowed by position). Intended for future automation that needs to
    map an incoming email to an existing tracked application."""
    conn = database.get_connection()
    if position:
        row = conn.execute(
            """
            SELECT * FROM applications
            WHERE company = ? COLLATE NOCASE AND position = ? COLLATE NOCASE
            ORDER BY application_date DESC, id DESC LIMIT 1
            """,
            (company, position),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT * FROM applications
            WHERE company = ? COLLATE NOCASE
            ORDER BY application_date DESC, id DESC LIMIT 1
            """,
            (company,),
        ).fetchone()
    if row is None:
        return None
    return get_application(row["id"])


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

def _insert_event(conn, application_id, event_type, event_date, description, source, gmail_message_id=None):
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO application_events (application_id, event_type, event_date, description, source, gmail_message_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (application_id, event_type, event_date, description or "", source, gmail_message_id, now),
    )


def add_event(application_id, event_type, event_date, description="", source="manual", gmail_message_id=None):
    with _write_lock:
        conn = database.get_connection()
        app_exists = conn.execute(
            "SELECT id FROM applications WHERE id = ?", (application_id,)
        ).fetchone()
        if app_exists is None:
            return None

        clean = validation.validate_event_payload(
            {"event_type": event_type, "event_date": event_date, "description": description},
            partial=False,
        )

        try:
            _insert_event(conn, application_id, clean["event_type"], clean["event_date"], clean["description"], source, gmail_message_id)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        row = conn.execute(
            "SELECT * FROM application_events WHERE id = last_insert_rowid()"
        ).fetchone()
        return _row_to_dict(row)


def has_processed_gmail_message(gmail_message_id):
    """Secondary, DB-level duplicate guard. The primary idempotency check
    is data/gmail_sync_state.json (see backend/gmail_sync.py) -- this just
    makes sure a message can never leave two events behind even if the
    JSON state file and the database ever disagree."""
    if not gmail_message_id:
        return False
    conn = database.get_connection()
    row = conn.execute(
        "SELECT 1 FROM application_events WHERE gmail_message_id = ? LIMIT 1",
        (gmail_message_id,),
    ).fetchone()
    return row is not None


def update_event(event_id, data):
    with _write_lock:
        conn = database.get_connection()
        existing = conn.execute(
            "SELECT * FROM application_events WHERE id = ?", (event_id,)
        ).fetchone()
        if existing is None:
            return None

        clean = validation.validate_event_payload(data or {}, partial=True)
        if not clean:
            return _row_to_dict(existing)

        set_parts = [f"{col} = ?" for col in clean]
        set_values = list(clean.values())

        try:
            conn.execute(
                f"UPDATE application_events SET {', '.join(set_parts)} WHERE id = ?",
                set_values + [event_id],
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        row = conn.execute(
            "SELECT * FROM application_events WHERE id = ?", (event_id,)
        ).fetchone()
        return _row_to_dict(row)


def delete_event(event_id):
    with _write_lock:
        conn = database.get_connection()
        try:
            cur = conn.execute("DELETE FROM application_events WHERE id = ?", (event_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Stats & analytics
# ---------------------------------------------------------------------------

def get_summary_stats():
    conn = database.get_connection()

    total = conn.execute("SELECT COUNT(*) AS c FROM applications").fetchone()["c"]
    # "Heard back" counts a stage invitation (screening call, coffee chat,
    # interview, etc.) as a response even if the user only updated the
    # stage and hasn't separately flipped outcome away from Pending yet.
    heard_back = conn.execute(
        f"SELECT COUNT(*) AS c FROM applications WHERE {HEARD_BACK_SQL}"
    ).fetchone()["c"]
    pending = total - heard_back
    positive = conn.execute(
        f"SELECT COUNT(*) AS c FROM applications WHERE {POSITIVE_SQL}"
    ).fetchone()["c"]
    negative = conn.execute(
        "SELECT COUNT(*) AS c FROM applications WHERE outcome = 'Negative'"
    ).fetchone()["c"]

    assessment_stages = _stages_at_or_above("Assessment")
    interview_stages = _stages_at_or_above("Interview 1")

    placeholders_a = ",".join("?" * len(assessment_stages))
    placeholders_i = ",".join("?" * len(interview_stages))

    assessments = conn.execute(
        f"SELECT COUNT(*) AS c FROM applications WHERE max_stage_reached IN ({placeholders_a})",
        assessment_stages,
    ).fetchone()["c"]
    interviews = conn.execute(
        f"SELECT COUNT(*) AS c FROM applications WHERE max_stage_reached IN ({placeholders_i})",
        interview_stages,
    ).fetchone()["c"]
    offers = conn.execute(
        "SELECT COUNT(*) AS c FROM applications WHERE max_stage_reached = 'Offer' OR outcome = 'Accepted'"
    ).fetchone()["c"]

    def rate(n, d):
        return round(n / d, 4) if d else 0.0

    return {
        "total_applications": total,
        "pending": pending,
        "heard_back": heard_back,
        "positive_responses": positive,
        "negative_responses": negative,
        "assessments": assessments,
        "interviews": interviews,
        "offers": offers,
        "response_rate": rate(heard_back, total),
        "positive_response_rate": rate(positive, total),
        "interview_conversion_rate": rate(interviews, total),
    }


def get_analytics(granularity="day"):
    conn = database.get_connection()

    date_rows = conn.execute("SELECT application_date FROM applications").fetchall()
    buckets = {}
    for r in date_rows:
        d = r["application_date"]
        try:
            date_obj = datetime.date.fromisoformat(d)
        except (ValueError, TypeError):
            continue
        if granularity == "week":
            iso = date_obj.isocalendar()
            key = f"{iso[0]}-W{iso[1]:02d}"
        elif granularity == "month":
            key = f"{date_obj.year}-{date_obj.month:02d}"
        else:
            key = date_obj.isoformat()
        buckets[key] = buckets.get(key, 0) + 1
    applications_over_time = [
        {"period": k, "count": v} for k, v in sorted(buckets.items())
    ]

    stats = get_summary_stats()
    funnel = [
        {"stage": "Applications", "count": stats["total_applications"]},
        {"stage": "Responses", "count": stats["heard_back"]},
        {"stage": "Assessments", "count": stats["assessments"]},
        {"stage": "Interviews", "count": stats["interviews"]},
        {"stage": "Offers", "count": stats["offers"]},
    ]

    interview_stages = _stages_at_or_above("Interview 1")
    placeholders_i = ",".join("?" * len(interview_stages))
    source_rows = conn.execute(
        f"""
        SELECT
            COALESCE(NULLIF(TRIM(source), ''), 'Unspecified') AS source,
            COUNT(*) AS total,
            SUM(CASE WHEN {HEARD_BACK_SQL} THEN 1 ELSE 0 END) AS heard_back,
            SUM(CASE WHEN {POSITIVE_SQL} THEN 1 ELSE 0 END) AS positive,
            SUM(CASE WHEN max_stage_reached IN ({placeholders_i}) THEN 1 ELSE 0 END) AS interviews
        FROM applications
        GROUP BY source
        ORDER BY total DESC
        """,
        interview_stages,
    ).fetchall()

    def rate(n, d):
        return round(n / d, 4) if d else 0.0

    source_performance = []
    for r in source_rows:
        source_performance.append({
            "source": r["source"],
            "total": r["total"],
            "response_rate": rate(r["heard_back"], r["total"]),
            "positive_response_rate": rate(r["positive"], r["total"]),
            "interview_rate": rate(r["interviews"], r["total"]),
        })

    stage_rows = conn.execute(
        "SELECT current_stage, COUNT(*) AS c FROM applications GROUP BY current_stage"
    ).fetchall()
    stage_counts = {r["current_stage"]: r["c"] for r in stage_rows}
    stage_distribution = [
        {"stage": s, "count": stage_counts.get(s, 0)} for s in constants.ALL_STAGES
    ]

    outcome_rows = conn.execute(
        "SELECT outcome, COUNT(*) AS c FROM applications GROUP BY outcome"
    ).fetchall()
    outcome_counts = {r["outcome"]: r["c"] for r in outcome_rows}
    outcome_distribution = [
        {"outcome": o, "count": outcome_counts.get(o, 0)} for o in constants.OUTCOMES
    ]

    # A simplified, mutually-exclusive breakdown of each application's
    # *current* state (not "ever reached", unlike `funnel` above) -- each
    # application lands in exactly one bucket, so the counts always sum to
    # the total. Priority order matters: a rejected application counts as
    # Negative even if it once reached Interview, since current status is
    # what this view is about.
    interview_current_stages = ["Interview 1", "Interview 2", "Final Interview"]
    placeholders_ic = ",".join("?" * len(interview_current_stages))
    summary_row = conn.execute(
        f"""
        SELECT
            SUM(CASE WHEN outcome IN ('Negative', 'Withdrawn') THEN 1 ELSE 0 END) AS negative,
            SUM(CASE WHEN outcome NOT IN ('Negative', 'Withdrawn')
                      AND (current_stage = 'Offer' OR outcome = 'Accepted') THEN 1 ELSE 0 END) AS offer,
            SUM(CASE WHEN outcome NOT IN ('Negative', 'Withdrawn')
                      AND current_stage != 'Offer' AND outcome != 'Accepted'
                      AND current_stage IN ({placeholders_ic}) THEN 1 ELSE 0 END) AS interview,
            SUM(CASE WHEN outcome NOT IN ('Negative', 'Withdrawn')
                      AND current_stage != 'Offer' AND outcome != 'Accepted'
                      AND current_stage NOT IN ({placeholders_ic})
                      AND current_stage = 'Assessment' THEN 1 ELSE 0 END) AS assessment
        FROM applications
        """,
        interview_current_stages + interview_current_stages,
    ).fetchone()
    negative_c = summary_row["negative"] or 0
    offer_c = summary_row["offer"] or 0
    interview_c = summary_row["interview"] or 0
    assessment_c = summary_row["assessment"] or 0
    pending_c = stats["total_applications"] - negative_c - offer_c - interview_c - assessment_c
    stage_summary = [
        {"stage": "Interview", "count": interview_c},
        {"stage": "Offer", "count": offer_c},
        {"stage": "Assessment", "count": assessment_c},
        {"stage": "Negative", "count": negative_c},
        {"stage": "Pending", "count": pending_c},
    ]

    return {
        "applications_over_time": applications_over_time,
        "funnel": funnel,
        "source_performance": source_performance,
        "stage_distribution": stage_distribution,
        "outcome_distribution": outcome_distribution,
        "stage_summary": stage_summary,
    }


# ---------------------------------------------------------------------------
# Distinct values (for filter dropdowns)
# ---------------------------------------------------------------------------

def get_distinct_values():
    conn = database.get_connection()
    companies = [r["company"] for r in conn.execute(
        "SELECT DISTINCT company FROM applications ORDER BY company COLLATE NOCASE"
    ).fetchall()]
    sources = [r["source"] for r in conn.execute(
        "SELECT DISTINCT source FROM applications WHERE source IS NOT NULL AND source != '' ORDER BY source COLLATE NOCASE"
    ).fetchall()]
    locations = [r["location"] for r in conn.execute(
        "SELECT DISTINCT location FROM applications WHERE location IS NOT NULL AND location != '' ORDER BY location COLLATE NOCASE"
    ).fetchall()]
    return {"companies": companies, "sources": sources, "locations": locations}


# ---------------------------------------------------------------------------
# Export / Import / Backup
# ---------------------------------------------------------------------------

def export_all_json():
    conn = database.get_connection()
    rows = conn.execute(
        f"SELECT {', '.join(CSV_EXPORT_HEADERS)} FROM applications ORDER BY application_date DESC, id DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def export_all_csv():
    conn = database.get_connection()
    rows = conn.execute(
        f"SELECT {', '.join(CSV_EXPORT_HEADERS)} FROM applications ORDER BY application_date DESC, id DESC"
    ).fetchall()

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_EXPORT_HEADERS)
    writer.writeheader()
    for r in rows:
        writer.writerow(dict(r))
    return buf.getvalue()


def parse_and_validate_csv_import(csv_text):
    """Parse CSV text and validate every row before anything is inserted.
    Returns (valid_rows, errors) where valid_rows are cleaned payloads
    ready for insertion and errors is a list of {row, message}."""
    reader = csv.DictReader(io.StringIO(csv_text))
    missing_headers = [h for h in ("company", "position", "application_date") if h not in (reader.fieldnames or [])]
    if missing_headers:
        raise validation.ValidationError(
            f"CSV is missing required column(s): {', '.join(missing_headers)}. "
            f"Expected headers: {', '.join(CSV_IMPORT_HEADERS)}"
        )

    valid_rows = []
    errors = []
    for i, raw_row in enumerate(reader, start=2):  # row 1 is the header
        payload = {
            "company": raw_row.get("company", ""),
            "position": raw_row.get("position", ""),
            "location": raw_row.get("location", ""),
            "application_date": raw_row.get("application_date") or _today_iso(),
            "source": raw_row.get("source", ""),
            "job_url": raw_row.get("job_url", ""),
            "job_description": raw_row.get("job_description", ""),
            "current_stage": raw_row.get("stage") or constants.STAGE_PROGRESSION[0],
            "outcome": raw_row.get("outcome") or constants.OUTCOMES[0],
            "notes": raw_row.get("notes", ""),
        }
        try:
            clean = validation.validate_application_payload(payload, partial=False)
            valid_rows.append(clean)
        except validation.ValidationError as e:
            errors.append({"row": i, "message": e.message})

    return valid_rows, errors


def import_applications(valid_rows):
    """Insert already-validated rows in a single transaction."""
    with _write_lock:
        conn = database.get_connection()
        now = _now_iso()
        inserted_ids = []
        try:
            for clean in valid_rows:
                max_stage = clean["current_stage"] if clean["current_stage"] in constants.STAGE_RANK else constants.STAGE_PROGRESSION[0]
                cur = conn.execute(
                    """
                    INSERT INTO applications (
                        company, position, location, application_date, current_stage,
                        outcome, source, job_url, job_description, notes,
                        max_stage_reached, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        clean["company"], clean["position"], clean.get("location", ""),
                        clean["application_date"], clean["current_stage"], clean["outcome"],
                        clean.get("source", ""), clean.get("job_url", ""),
                        clean.get("job_description", ""), clean.get("notes", ""),
                        max_stage, now, now,
                    ),
                )
                application_id = cur.lastrowid
                _insert_event(conn, application_id, "Application Submitted", clean["application_date"], "Imported from CSV", "import")
                inserted_ids.append(application_id)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return inserted_ids


def backup_database():
    with _write_lock:
        database.ensure_data_dirs()
        conn = database.get_connection()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(database.BACKUP_DIR, f"applications_backup_{timestamp}.db")
        dest = sqlite3.connect(backup_path)
        try:
            conn.backup(dest)
        finally:
            dest.close()
        return backup_path
