"""Input validation for everything that reaches the database.

Kept separate from repository.py so the rules are easy to audit in one
place, and so a future automation script importing repository functions
gets the same validation "for free" -- it cannot bypass business rules by
calling a different entry point.
"""

import datetime

from . import constants


class ValidationError(Exception):
    """Raised when caller-supplied data fails validation. The server layer
    turns these into HTTP 400 responses."""

    def __init__(self, message, field=None):
        super().__init__(message)
        self.message = message
        self.field = field


def require_text(value, field, max_len=500, allow_empty=False):
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be text", field)
    value = value.strip()
    if not allow_empty and not value:
        raise ValidationError(f"{field} is required", field)
    if len(value) > max_len:
        raise ValidationError(f"{field} must be {max_len} characters or fewer", field)
    return value


def optional_text(value, field, max_len=20000):
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be text", field)
    value = value.strip()
    if len(value) > max_len:
        raise ValidationError(f"{field} must be {max_len} characters or fewer", field)
    return value


def require_date(value, field):
    value = require_text(value, field, max_len=10)
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{field} must be a valid date (YYYY-MM-DD)", field)
    return value


def optional_datetime(value, field):
    """Accepts '' / None, a 'YYYY-MM-DD' date, or a 'YYYY-MM-DDTHH:MM' local
    datetime (what an <input type=datetime-local> emits). Returns the string
    unchanged, or '' to mean 'cleared'."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be text", field)
    value = value.strip()
    if not value:
        return ""
    if len(value) > 25:
        raise ValidationError(f"{field} is not a valid date-time", field)
    try:
        datetime.datetime.fromisoformat(value)
    except ValueError:
        raise ValidationError(
            f"{field} must be an ISO date or date-time (YYYY-MM-DD or YYYY-MM-DDTHH:MM)", field
        )
    return value


def require_stage(value):
    value = require_text(value, "stage", max_len=50)
    if value not in constants.ALL_STAGES:
        raise ValidationError(
            f"stage must be one of: {', '.join(constants.ALL_STAGES)}", "stage"
        )
    return value


def require_outcome(value):
    value = require_text(value, "outcome", max_len=50)
    if value not in constants.OUTCOMES:
        raise ValidationError(
            f"outcome must be one of: {', '.join(constants.OUTCOMES)}", "outcome"
        )
    return value


def require_event_type(value):
    # Custom event types are allowed (the UI offers "Other" + free text),
    # so we only enforce non-empty + length, not membership.
    return require_text(value, "event_type", max_len=100)


def validate_application_payload(data, partial=False):
    """Validate a create/update payload for an application.

    When partial=True (used by PATCH/PUT-style edits), fields absent from
    `data` are skipped rather than treated as errors.
    """
    out = {}

    def touched(key):
        return (not partial) or (key in data)

    if touched("company"):
        out["company"] = require_text(data.get("company"), "company", max_len=200)
    if touched("position"):
        out["position"] = require_text(data.get("position"), "position", max_len=200)
    if touched("location"):
        out["location"] = optional_text(data.get("location"), "location", max_len=200)
    if touched("application_date"):
        out["application_date"] = require_date(
            data.get("application_date"), "application_date"
        )
    if touched("current_stage"):
        out["current_stage"] = require_stage(data.get("current_stage"))
    if touched("outcome"):
        out["outcome"] = require_outcome(data.get("outcome"))
    if touched("source"):
        out["source"] = optional_text(data.get("source"), "source", max_len=100)
    if touched("job_url"):
        out["job_url"] = optional_text(data.get("job_url"), "job_url", max_len=2000)
    if touched("job_description"):
        out["job_description"] = optional_text(
            data.get("job_description"), "job_description", max_len=100000
        )
    if touched("notes"):
        out["notes"] = optional_text(data.get("notes"), "notes", max_len=50000)

    return out


def validate_event_payload(data, partial=False):
    out = {}

    def touched(key):
        return (not partial) or (key in data)

    if touched("event_type"):
        out["event_type"] = require_event_type(data.get("event_type"))
    if touched("event_date"):
        out["event_date"] = require_date(data.get("event_date"), "event_date")
    if touched("description"):
        out["description"] = optional_text(
            data.get("description"), "description", max_len=5000
        )
    if touched("scheduled_for"):
        out["scheduled_for"] = optional_datetime(data.get("scheduled_for"), "scheduled_for")
    if touched("item_status"):
        raw = data.get("item_status")
        raw = "" if raw is None else str(raw).strip()
        if raw and raw not in constants.ITEM_STATUSES:
            raise ValidationError(
                f"item_status must be one of: {', '.join(constants.ITEM_STATUSES)}", "item_status"
            )
        out["item_status"] = raw

    return out
