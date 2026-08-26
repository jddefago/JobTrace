"""Headless Gmail -> JobTrace sync using the user's own Anthropic + Google
API keys. Unlike GMAIL_SYNC.md's workflow, this script does NOT need an AI
assistant app (Claude Desktop/Code, Codex CLI) installed or running -- it
calls the Gmail API and the Anthropic API directly, so it can be scheduled
(Task Scheduler / launchd / cron) on a machine with nothing but Python and
this project's dependencies installed.

See GMAIL_SYNC_API.md for one-time setup (a Google Cloud OAuth client, an
Anthropic API key). See GMAIL_SYNC.md for the actual sync *policy* -- this
script reads that file from disk at runtime and uses it as the bulk of the
system prompt below, so the classification rules, matching tiers, and
duplicate-protection rules have exactly one source of truth shared with the
assistant-driven sync path. Never fork a second copy of that policy here.

This module only ever calls into backend/repository.py and
backend/gmail_sync.py -- the same functions the manual, assistant-driven
sync uses -- so every safety guarantee documented there (transactions,
validation, WAL mode, idempotent creates) applies unchanged.
"""

import argparse
import base64
import datetime
import email
import email.policy
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import repository as repo
from backend import gmail_sync

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
GMAIL_SYNC_DOC_PATH = os.path.join(BASE_DIR, "GMAIL_SYNC.md")

# Each secret-bearing file's location can be overridden with an environment
# variable. This matters when the project folder sits inside a cloud-synced
# tree (OneDrive/Dropbox/Google Drive/iCloud): the API key, OAuth client
# secret, and live Gmail token should not be uploaded to a sync provider
# along with the rest of the folder. Point these somewhere outside the
# synced tree (e.g. ~/.jobtrace/) and the defaults below are ignored.
CONFIG_PATH = os.environ.get(
    "JOBTRACE_GMAIL_CONFIG", os.path.join(DATA_DIR, "gmail_api_config.json"))
GMAIL_CREDENTIALS_PATH = os.environ.get(
    "JOBTRACE_GMAIL_CREDENTIALS", os.path.join(DATA_DIR, "gmail_api_credentials.json"))
GMAIL_TOKEN_PATH = os.environ.get(
    "JOBTRACE_GMAIL_TOKEN", os.path.join(DATA_DIR, "gmail_api_token.json"))
SYNC_LOG_DIR = os.path.join(DATA_DIR, "sync_logs")

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Check https://docs.claude.com/en/docs/about-claude/models for the current
# model catalog if this default ever starts erroring as unknown -- model IDs
# change over time. Override via the "model" key in data/gmail_api_config.json.
DEFAULT_MODEL = "claude-sonnet-5"
MAX_TURNS = 60
MAX_BODY_CHARS = 20000

WRITE_TOOLS = {
    "create_application",
    "update_application_stage",
    "update_application",
    "add_event",
    "mark_message_processed",
    "add_unresolved_item",
    "remove_unresolved_item",
    "record_sync_result",
}


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config():
    config = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)

    config.setdefault("anthropic_api_key", os.environ.get("ANTHROPIC_API_KEY"))
    config.setdefault("model", DEFAULT_MODEL)
    config.setdefault("gmail_label", "Job Applications")
    config.setdefault("lookback_days", 30)
    # Off by default: email content is untrusted input reaching a model that,
    # with this on, also has a live internet-search tool. A crafted email
    # could try to prompt-inject a search query that leaks fragments of your
    # local data. Turn on deliberately if you want the location/job-URL/
    # source enrichment step badly enough to accept that.
    config.setdefault("enable_web_search", False)

    if not config.get("anthropic_api_key"):
        raise SystemExit(
            "No Anthropic API key found. Put it in data/gmail_api_config.json "
            '("anthropic_api_key") or set the ANTHROPIC_API_KEY environment '
            "variable. See GMAIL_SYNC_API.md."
        )
    return config


# ---------------------------------------------------------------------------
# Gmail: auth + read-only helpers
# ---------------------------------------------------------------------------

def get_gmail_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(GMAIL_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_PATH, GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(GMAIL_CREDENTIALS_PATH):
                raise SystemExit(
                    f"Missing {GMAIL_CREDENTIALS_PATH}. Download your OAuth "
                    "client secret (Desktop app type) from Google Cloud "
                    "Console -- see GMAIL_SYNC_API.md."
                )
            # Opens a browser once for consent. Only needed interactively,
            # the first time (or after revoking access) -- every run after
            # that reuses/refreshes the cached token with no browser needed,
            # which is what makes unattended scheduling possible.
            flow = InstalledAppFlow.from_client_secrets_file(GMAIL_CREDENTIALS_PATH, GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
        os.makedirs(os.path.dirname(os.path.abspath(GMAIL_TOKEN_PATH)), exist_ok=True)
        with open(GMAIL_TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def gmail_list_labels(service):
    result = service.users().labels().list(userId="me").execute()
    return [{"id": l["id"], "name": l["name"]} for l in result.get("labels", [])]


def gmail_search_messages(service, query, include_trash=True, max_results=300):
    # Gmail excludes Trash from search results by default -- same lesson
    # documented in GMAIL_SYNC.md. in:anywhere covers Trash and Spam too.
    full_query = f"({query}) in:anywhere" if include_trash else query
    ids = []
    page_token = None
    while True:
        resp = service.users().messages().list(
            userId="me", q=full_query, pageToken=page_token, maxResults=100
        ).execute()
        ids.extend(m["id"] for m in resp.get("messages", []))
        page_token = resp.get("nextPageToken")
        if not page_token or len(ids) >= max_results:
            break
    return ids[:max_results]


def _extract_body_text(msg):
    body_part = msg.get_body(preferencelist=("plain", "html"))
    if body_part is None:
        return ""
    content = body_part.get_content()
    if body_part.get_content_type() == "text/html":
        content = re.sub(r"<[^>]+>", " ", content)
        content = re.sub(r"\s+", " ", content).strip()
    return content[:MAX_BODY_CHARS]


def gmail_get_message(service, message_id):
    raw = service.users().messages().get(userId="me", id=message_id, format="raw").execute()
    raw_bytes = base64.urlsafe_b64decode(raw["raw"])
    msg = email.message_from_bytes(raw_bytes, policy=email.policy.default)
    return {
        "id": message_id,
        "threadId": raw.get("threadId"),
        "labelIds": raw.get("labelIds", []),
        "from": msg.get("From", ""),
        "to": msg.get("To", ""),
        "subject": msg.get("Subject", ""),
        "date": msg.get("Date", ""),
        "body": _extract_body_text(msg),
    }


# ---------------------------------------------------------------------------
# Tool schemas (Anthropic tool-use) -- one per operation GMAIL_SYNC.md
# describes, either against Gmail or against repository.py/gmail_sync.py.
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "search_gmail",
        "description": (
            "Search Gmail (equivalent to GMAIL_SYNC.md's search_threads). "
            "Returns a list of message IDs only -- call get_gmail_message on "
            "each one you want to read. include_trash defaults to true; "
            "GMAIL_SYNC.md explains why that matters."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Gmail search syntax, e.g. label:\"Job Applications\" or a keyword sweep with -label:\"Job Applications\"."},
                "include_trash": {"type": "boolean", "default": True},
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_gmail_labels",
        "description": "List Gmail labels (equivalent to GMAIL_SYNC.md's list_labels), to resolve a label name to scope a search.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_gmail_message",
        "description": "Fetch one Gmail message's headers and plain-text body (equivalent to get_thread/get_message).",
        "input_schema": {
            "type": "object",
            "properties": {"message_id": {"type": "string"}},
            "required": ["message_id"],
        },
    },
    {
        "name": "is_message_processed",
        "description": (
            "Check both duplicate-protection signals (the JSON sync-state file "
            "and the database) for one Gmail message ID. Call this before "
            "acting on any message. If true, skip that message entirely."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"message_id": {"type": "string"}},
            "required": ["message_id"],
        },
    },
    {
        "name": "mark_message_processed",
        "description": (
            "Mark a Gmail message as reviewed, without creating an event -- "
            "use this for IRRELEVANT messages or anything else you decided "
            "not to act on. Messages that DO get an event via add_event are "
            "marked processed automatically; don't call this for those."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"message_id": {"type": "string"}},
            "required": ["message_id"],
        },
    },
    {
        "name": "find_matching_application",
        "description": "Find the most recent application for a company (optionally narrowed by exact position). Tier 3 of the matching rules.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {"type": "string"},
                "position": {"type": "string"},
            },
            "required": ["company"],
        },
    },
    {
        "name": "list_applications",
        "description": "List applications, optionally filtered by a partial company match -- for fuzzier matching tiers (4-7) when find_matching_application isn't confident enough.",
        "input_schema": {
            "type": "object",
            "properties": {"company": {"type": "string"}},
        },
    },
    {
        "name": "get_application",
        "description": "Get one application's full detail, including its event timeline.",
        "input_schema": {
            "type": "object",
            "properties": {"application_id": {"type": "integer"}},
            "required": ["application_id"],
        },
    },
    {
        "name": "create_application",
        "description": (
            "Create a new application from a clear confirmation email. "
            "Auto-creates a generic 'Application Submitted' event -- "
            "separately call add_event for the Gmail-specific confirmation "
            "event. If gmail_message_id is given, this call is idempotent "
            "(safe to retry) and is refused if that message was already "
            "processed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {"type": "string"},
                "position": {"type": "string"},
                "location": {"type": "string"},
                "application_date": {"type": "string", "description": "YYYY-MM-DD"},
                "source": {"type": "string"},
                "job_url": {"type": "string"},
                "job_description": {"type": "string"},
                "notes": {"type": "string"},
                "gmail_message_id": {"type": "string"},
            },
            "required": ["company", "position", "application_date"],
        },
    },
    {
        "name": "update_application_stage",
        "description": "Update an application's stage and, optionally, its outcome. Auto-creates 'Stage Update'/'Outcome Update' events only when the value actually changes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "application_id": {"type": "integer"},
                "stage": {"type": "string"},
                "outcome": {"type": "string"},
            },
            "required": ["application_id", "stage"],
        },
    },
    {
        "name": "update_application",
        "description": "Update arbitrary application fields (e.g. location/job_url/source enrichment, or a note). Only include fields you're actually changing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "application_id": {"type": "integer"},
                "fields": {"type": "object", "description": "Partial field->value map, e.g. {\"location\": \"Amsterdam, NL\"}"},
            },
            "required": ["application_id", "fields"],
        },
    },
    {
        "name": "add_event",
        "description": (
            "Add a Gmail-sourced timeline event. Always pass gmail_message_id "
            "for anything Gmail touched -- this call refuses to run if that "
            "message was already processed (checked independently of your own "
            "judgement), and marks the message processed automatically on "
            "success."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "application_id": {"type": "integer"},
                "event_type": {"type": "string"},
                "event_date": {"type": "string", "description": "YYYY-MM-DD, the email's date"},
                "description": {"type": "string"},
                "gmail_message_id": {"type": "string"},
            },
            "required": ["application_id", "event_type", "event_date", "gmail_message_id"],
        },
    },
    {
        "name": "add_unresolved_item",
        "description": "Record an email you couldn't confidently match or classify, for the user to review later.",
        "input_schema": {
            "type": "object",
            "properties": {
                "gmail_message_id": {"type": "string"},
                "email_date": {"type": "string"},
                "sender": {"type": "string"},
                "subject": {"type": "string"},
                "possible_company": {"type": "string"},
                "possible_position": {"type": "string"},
                "possible_event_type": {"type": "string"},
                "reason": {"type": "string"},
                "candidate_application_ids": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["gmail_message_id", "reason"],
        },
    },
    {
        "name": "remove_unresolved_item",
        "description": "Remove a stale unresolved item -- e.g. the user resolved it manually since the last sync.",
        "input_schema": {
            "type": "object",
            "properties": {"item_id": {"type": "integer"}},
            "required": ["item_id"],
        },
    },
    {
        "name": "record_sync_result",
        "description": (
            "Call exactly once, at the very end of a fully completed run, with "
            "the run's counters. This stamps lastSuccessfulSync and ends the "
            "sync -- nothing else will be executed after this call."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "emails_reviewed": {"type": "integer"},
                "recruitment_related": {"type": "integer"},
                "applications_created": {"type": "integer"},
                "applications_updated": {"type": "integer"},
                "rejections_detected": {"type": "integer"},
                "assessments_detected": {"type": "integer"},
                "interviews_detected": {"type": "integer"},
                "offers_detected": {"type": "integer"},
                "emails_ignored": {"type": "integer"},
                "summary": {"type": "string", "description": "A short human-readable report, matching the format in GMAIL_SYNC.md's step 15."},
            },
        },
    },
]

WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 15}


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

class ToolError(Exception):
    pass


class SyncSession:
    """Holds the mutable local state a sync run reads/writes, and dispatches
    each Anthropic tool call to the real Gmail/repository/gmail_sync call it
    represents. Every write tool re-checks duplicate protection itself,
    independent of whatever the model believes -- see GMAIL_SYNC.md's
    "duplicate protection (critical)" section, which this mirrors exactly."""

    def __init__(self, service, dry_run=False):
        self.service = service
        self.dry_run = dry_run
        self.state = gmail_sync.load_sync_state()
        self.unresolved = gmail_sync.load_unresolved()
        self.done = False
        self.report = None

    def _save_state(self):
        if not self.dry_run:
            gmail_sync.save_sync_state(self.state)

    def _save_unresolved(self):
        if not self.dry_run:
            gmail_sync.save_unresolved(self.unresolved)

    def _already_processed(self, message_id):
        return gmail_sync.is_message_processed(self.state, message_id) or repo.has_processed_gmail_message(message_id)

    def dispatch(self, name, args):
        if self.dry_run and name in WRITE_TOOLS and name != "record_sync_result":
            return {"dry_run": True, "would_call": name, "args": args}

        handler = getattr(self, f"_tool_{name}", None)
        if handler is None:
            raise ToolError(f"Unknown tool: {name}")
        return handler(args)

    # -- Gmail (read-only) ---------------------------------------------

    def _tool_search_gmail(self, args):
        ids = gmail_search_messages(self.service, args["query"], args.get("include_trash", True))
        return {"message_ids": ids, "count": len(ids)}

    def _tool_list_gmail_labels(self, args):
        return {"labels": gmail_list_labels(self.service)}

    def _tool_get_gmail_message(self, args):
        return gmail_get_message(self.service, args["message_id"])

    # -- Duplicate protection -------------------------------------------

    def _tool_is_message_processed(self, args):
        return {"processed": self._already_processed(args["message_id"])}

    def _tool_mark_message_processed(self, args):
        gmail_sync.mark_message_processed(self.state, args["message_id"])
        self._save_state()
        return {"marked": args["message_id"]}

    # -- Application read/match ------------------------------------------

    def _tool_find_matching_application(self, args):
        app = repo.find_matching_application(args["company"], args.get("position"))
        return {"application": app}

    def _tool_list_applications(self, args):
        return repo.list_applications(company=args.get("company"), page_size=50)

    def _tool_get_application(self, args):
        app = repo.get_application(args["application_id"])
        if app is None:
            raise ToolError(f"No application with id {args['application_id']}")
        return app

    # -- Application writes -----------------------------------------------

    def _tool_create_application(self, args):
        message_id = args.get("gmail_message_id")
        if message_id and self._already_processed(message_id):
            raise ToolError(f"Message {message_id} was already processed -- refusing to create a duplicate application.")
        client_request_id = f"gmail-create-{message_id}" if message_id else None
        payload = {
            "company": args["company"],
            "position": args["position"],
            "location": args.get("location", ""),
            "application_date": args["application_date"],
            "source": args.get("source", "Unknown"),
            "job_url": args.get("job_url", ""),
            "job_description": args.get("job_description", ""),
            "notes": args.get("notes", ""),
            "current_stage": "Applied",
            "outcome": "Pending",
        }
        return repo.create_application(payload, client_request_id=client_request_id)

    def _tool_update_application_stage(self, args):
        app = repo.update_application_stage(args["application_id"], args["stage"], args.get("outcome"))
        if app is None:
            raise ToolError(f"No application with id {args['application_id']}")
        return app

    def _tool_update_application(self, args):
        app = repo.update_application(args["application_id"], args.get("fields", {}))
        if app is None:
            raise ToolError(f"No application with id {args['application_id']}")
        return app

    def _tool_add_event(self, args):
        message_id = args["gmail_message_id"]
        if self._already_processed(message_id):
            raise ToolError(f"Message {message_id} was already processed -- refusing to add a duplicate event.")
        event = repo.add_event(
            args["application_id"],
            event_type=args["event_type"],
            event_date=args["event_date"],
            description=args.get("description", ""),
            source="Gmail",
            gmail_message_id=message_id,
        )
        if event is None:
            raise ToolError(f"No application with id {args['application_id']}")
        gmail_sync.mark_message_processed(self.state, message_id)
        self._save_state()
        return event

    # -- Unresolved queue ---------------------------------------------------

    def _tool_add_unresolved_item(self, args):
        row = gmail_sync.add_unresolved_item(self.unresolved, {
            "gmailMessageId": args["gmail_message_id"],
            "emailDate": args.get("email_date"),
            "sender": args.get("sender"),
            "subject": args.get("subject"),
            "possibleCompany": args.get("possible_company"),
            "possiblePosition": args.get("possible_position"),
            "possibleEventType": args.get("possible_event_type"),
            "reason": args["reason"],
            "candidateApplicationIds": args.get("candidate_application_ids", []),
        })
        self._save_unresolved()
        return row

    def _tool_remove_unresolved_item(self, args):
        removed = gmail_sync.remove_unresolved_item(self.unresolved, args["item_id"])
        self._save_unresolved()
        return {"removed": removed}

    # -- Finish -------------------------------------------------------------

    def _tool_record_sync_result(self, args):
        result = {
            "emailsReviewed": args.get("emails_reviewed", 0),
            "recruitmentRelated": args.get("recruitment_related", 0),
            "applicationsCreated": args.get("applications_created", 0),
            "applicationsUpdated": args.get("applications_updated", 0),
            "rejectionsDetected": args.get("rejections_detected", 0),
            "assessmentsDetected": args.get("assessments_detected", 0),
            "interviewsDetected": args.get("interviews_detected", 0),
            "offersDetected": args.get("offers_detected", 0),
            "emailsIgnored": args.get("emails_ignored", 0),
            "unresolvedCount": len(self.unresolved),
        }
        if not self.dry_run:
            gmail_sync.record_sync_result(self.state, result)
            self._save_state()
        self.done = True
        self.report = {"result": result, "summary": args.get("summary", "")}
        return {"recorded": True}


# ---------------------------------------------------------------------------
# System prompt: GMAIL_SYNC.md is the single source of truth for the policy.
# ---------------------------------------------------------------------------

ADAPTER_PREFACE = """You are running headlessly as a standalone script -- there is no
Claude Code/Desktop session, no MCP connector, no Bash or Python tool
available to you. You have exactly the tool set defined for this API call,
which maps onto the workflow document below like this:

  search_threads (MCP)              -> search_gmail
  get_thread / get_message (MCP)    -> get_gmail_message
  list_labels (MCP)                 -> list_gmail_labels
  gmail_sync.is_message_processed + repository.has_processed_gmail_message
                                     -> is_message_processed (checks both)
  gmail_sync.mark_message_processed -> mark_message_processed (for messages
                                        you don't add an event for, e.g.
                                        IRRELEVANT) -- add_event marks
                                        processed for you automatically
  repo.find_matching_application    -> find_matching_application
  repo.list_applications            -> list_applications
  repo.get_application              -> get_application
  repo.create_application           -> create_application
  repo.update_application_stage     -> update_application_stage
  repo.update_application           -> update_application
  repo.add_event                    -> add_event
  gmail_sync.add_unresolved_item    -> add_unresolved_item
  gmail_sync.remove_unresolved_item -> remove_unresolved_item
  gmail_sync.record_sync_result     -> record_sync_result (call this exactly
                                        once, at the very end -- the run ends
                                        as soon as you call it)

Every rule below -- duplicate protection, matching tiers, the status-mapping
table, "when uncertain, prefer no automatic status change" -- applies exactly
as written; only the tool names differ, per the mapping above. A web_search
tool is available for the enrichment step (location/job_url/source) if the
document below describes one.

Begin the run now: read the current sync state via is_message_processed as
you go, resolve the Gmail label, search, and work through the workflow below
end to end, finishing with record_sync_result.

---

"""


def build_system_prompt():
    with open(GMAIL_SYNC_DOC_PATH, "r", encoding="utf-8") as f:
        policy_doc = f.read()
    return ADAPTER_PREFACE + policy_doc


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

def run_sync(config, dry_run=False, log=print):
    import anthropic

    service = get_gmail_service()
    session = SyncSession(service, dry_run=dry_run)
    client = anthropic.Anthropic(api_key=config["anthropic_api_key"])

    tools = list(TOOLS)
    if config.get("enable_web_search", True):
        tools = tools + [WEB_SEARCH_TOOL]

    system_prompt = build_system_prompt()
    user_prompt = (
        f"Run a Gmail sync now.\n"
        f"Gmail label to check first: \"{config['gmail_label']}\"\n"
        f"Lookback window if there is no previous successful sync: {config['lookback_days']} days.\n"
        f"{'This is a DRY RUN: log what you would do, but treat every write tool as a no-op.' if dry_run else ''}"
    )
    messages = [{"role": "user", "content": user_prompt}]

    for turn in range(1, MAX_TURNS + 1):
        try:
            response = client.messages.create(
                model=config["model"],
                max_tokens=4096,
                system=system_prompt,
                tools=tools,
                messages=messages,
            )
        except Exception as e:
            if tools and any(t.get("type", "").startswith("web_search") for t in tools):
                log(f"Anthropic API call failed ({e}); retrying once without web_search.")
                tools = [t for t in TOOLS]
                continue
            raise

        messages.append({"role": "assistant", "content": response.content})

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        for block in response.content:
            if block.type == "text" and block.text.strip():
                log(f"[turn {turn}] {block.text.strip()}")

        if not tool_uses:
            log(f"Model finished without calling record_sync_result after {turn} turn(s).")
            break

        tool_results = []
        for block in tool_uses:
            log(f"[turn {turn}] tool: {block.name}({json.dumps(block.input, default=str)})")
            try:
                result = session.dispatch(block.name, block.input)
                content = json.dumps(result, ensure_ascii=False, default=str)
                is_error = False
            except ToolError as e:
                content = json.dumps({"error": str(e)})
                is_error = True
            except Exception as e:
                content = json.dumps({"error": f"{type(e).__name__}: {e}"})
                is_error = True
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
                "is_error": is_error,
            })

        messages.append({"role": "user", "content": tool_results})

        if session.done:
            log("record_sync_result called -- sync complete.")
            break
    else:
        log(f"Hit the {MAX_TURNS}-turn safety cap without record_sync_result being called.")

    return session


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Headless Gmail -> JobTrace sync via the Anthropic + Gmail APIs.")
    parser.add_argument("--dry-run", action="store_true", help="Log intended actions without writing anything.")
    parser.add_argument("--lookback-days", type=int, help="Override the config's lookback_days.")
    parser.add_argument("--label", type=str, help="Override the config's gmail_label.")
    args = parser.parse_args()

    config = load_config()
    if args.lookback_days:
        config["lookback_days"] = args.lookback_days
    if args.label:
        config["gmail_label"] = args.label

    os.makedirs(SYNC_LOG_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(SYNC_LOG_DIR, f"gmail_sync_api_{timestamp}.log")

    lines = []

    def log(msg):
        print(msg)
        lines.append(msg)

    log(f"===== Gmail API sync run started {datetime.datetime.now().isoformat(timespec='seconds')} =====")
    if args.dry_run:
        log("Running in --dry-run mode: no data will be written.")

    try:
        session = run_sync(config, dry_run=args.dry_run, log=log)
        if session.report:
            log("")
            log("Gmail Sync Complete")
            log(json.dumps(session.report["result"], indent=2))
            if session.report["summary"]:
                log("")
                log(session.report["summary"])
    except SystemExit:
        raise
    except Exception as e:
        log(f"Sync run failed: {type(e).__name__}: {e}")
        raise
    finally:
        log(f"===== Gmail API sync run finished {datetime.datetime.now().isoformat(timespec='seconds')} =====")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
