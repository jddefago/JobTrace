"""Local state for Gmail synchronization performed by Claude Desktop/Cowork.

This module owns two JSON files under data/ and nothing else. It never
talks to Gmail and never talks to the Claude/Anthropic API -- it is pure
local file I/O, imported both by the local HTTP server (read-only, to show
sync status in the dashboard) and by whichever Claude session is doing a
Gmail sync (read+write, following the rules in GMAIL_SYNC.md).

    data/gmail_sync_state.json      -- one row of sync bookkeeping
    data/unresolved_gmail_items.json -- a list of emails a sync could not
                                         confidently act on

See GMAIL_SYNC.md for the full workflow these files support.
"""

import datetime
import json
import os

from .. import database

SYNC_STATE_PATH = os.path.join(database.DATA_DIR, "gmail_sync_state.json")
UNRESOLVED_PATH = os.path.join(database.DATA_DIR, "unresolved_gmail_items.json")

DEFAULT_SYNC_STATE = {
    "lastSuccessfulSync": None,
    "connectedAccount": None,  # which Gmail address the last sync actually read
    "processedMessageIds": [],
    "lastSyncResult": {
        "emailsReviewed": 0,
        "recruitmentRelated": 0,
        "applicationsCreated": 0,
        "applicationsUpdated": 0,
        "rejectionsDetected": 0,
        "assessmentsDetected": 0,
        "interviewsDetected": 0,
        "offersDetected": 0,
        "emailsIgnored": 0,
        "unresolvedCount": 0,
    },
}


def _read_json(path, default):
    if not os.path.exists(path):
        return json.loads(json.dumps(default))  # deep copy
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if not content:
        return json.loads(json.dumps(default))
    return json.loads(content)


def _write_json_atomic(path, data):
    """Write via a temp file + rename so a crash mid-write can never leave
    a half-written, corrupt JSON file behind."""
    database.ensure_data_dirs()
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)


# ---------------------------------------------------------------------------
# Sync state
# ---------------------------------------------------------------------------

def load_sync_state():
    state = _read_json(SYNC_STATE_PATH, DEFAULT_SYNC_STATE)
    state.setdefault("lastSuccessfulSync", None)
    state.setdefault("connectedAccount", None)
    state.setdefault("processedMessageIds", [])
    state.setdefault("lastSyncResult", dict(DEFAULT_SYNC_STATE["lastSyncResult"]))
    return state


def save_sync_state(state):
    _write_json_atomic(SYNC_STATE_PATH, state)


def set_connected_account(state, address):
    """Record the Gmail address this sync run is reading from. Surfaced in
    the dashboard so a sync run against the wrong mailbox (wrong Claude
    account / wrong connector) is visible before it imports anything."""
    state["connectedAccount"] = (address or "").strip() or None


def is_message_processed(state, gmail_message_id):
    return gmail_message_id in state.get("processedMessageIds", [])


def mark_message_processed(state, gmail_message_id):
    """Mutates state in place. Never removes existing IDs -- the list only
    ever grows, by design (see GMAIL_SYNC.md: duplicate protection)."""
    ids = state.setdefault("processedMessageIds", [])
    if gmail_message_id not in ids:
        ids.append(gmail_message_id)


def record_sync_result(state, result):
    """Stamp a completed sync. `result` should have the same keys as
    DEFAULT_SYNC_STATE['lastSyncResult']; missing keys default to 0."""
    merged = dict(DEFAULT_SYNC_STATE["lastSyncResult"])
    merged.update(result)
    state["lastSyncResult"] = merged
    state["lastSuccessfulSync"] = datetime.datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Unresolved items
# ---------------------------------------------------------------------------

def load_unresolved():
    return _read_json(UNRESOLVED_PATH, [])


def save_unresolved(items):
    _write_json_atomic(UNRESOLVED_PATH, items)


def add_unresolved_item(items, item):
    """`item` should include at least: gmailMessageId, emailDate, sender,
    subject, reason. possibleCompany/possiblePosition/possibleEventType/
    candidateApplicationIds are optional. Adds recordedAt and a local id
    automatically."""
    next_id = 1 + max([it.get("id", 0) for it in items], default=0)
    row = {
        "id": next_id,
        "gmailMessageId": item.get("gmailMessageId"),
        "emailDate": item.get("emailDate"),
        "sender": item.get("sender"),
        "subject": item.get("subject"),
        "possibleCompany": item.get("possibleCompany"),
        "possiblePosition": item.get("possiblePosition"),
        "possibleEventType": item.get("possibleEventType"),
        "reason": item.get("reason"),
        "candidateApplicationIds": item.get("candidateApplicationIds", []),
        "recordedAt": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    items.append(row)
    return row


def remove_unresolved_item(items, item_id):
    """Used once a human (or a later sync with more context) resolves an
    item -- e.g. by manually matching it to an application. Returns True
    if a row was removed."""
    before = len(items)
    items[:] = [it for it in items if it.get("id") != item_id]
    return len(items) != before
