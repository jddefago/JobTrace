# JobTrace

A local-first dashboard for tracking job applications: pipeline stage, outcome,
timeline history, job descriptions, notes, and application statistics.

Everything runs on your computer. There is no cloud service and no external
account. The entire app is a local Python web server (stdlib only) serving a
plain HTML/CSS/JS frontend, backed by a single SQLite file.

**Optional Gmail sync** reads your inbox for recruiter replies and updates
the tracker. It's off by default, has three setup levels (from "ask your AI
assistant" with zero setup, to fully unattended), and nothing leaves your
machine unless you turn it on — see
[Gmail synchronization](#gmail-synchronization).

## Getting started

**Fastest:** double-click **`setup.command`** (macOS) or **`setup.bat`**
(Windows). It checks for Python, creates a desktop launcher, starts the
server, and opens the dashboard. Re-run it any time.

**With an AI assistant:** open this folder with Claude Code / Claude Desktop
/ Codex and ask it to "set up JobTrace" — it reads **[SETUP.md](SETUP.md)**,
a self-contained guide for exactly that. No account, API key, or payment is
required for the tracker itself.

**By hand:** see [Requirements](#requirements) and
[Starting the app](#starting-the-app) below.

## What it does

- Tracks each application's **company, position, location, source, dates,
  job description, notes, job URL**.
- Separates **Stage** (Applied → Screening → Assessment → Interview 1/2 →
  Final Interview → Offer → Closed) from **Outcome** (Pending, Positive,
  Negative, Accepted, Withdrawn) — so "got an assessment invite" and "got
  rejected" are both representable without overloading one status field.
- Keeps a full **timeline** of events per application (submitted, recruiter
  contact, assessment, interview, offer, rejection, etc.), with automatic
  entries whenever you change stage or outcome.
- A **dashboard** with summary metrics, response/interview conversion rates,
  and a searchable, sortable, filterable, paginated table (built to stay fast
  past 1,000+ applications).
- A **Tracker** tab for the things email can't tell you: a to-do list of
  assessments you haven't finished (with deadlines and a "mark completed"
  button), and your interviews as a list or month calendar — set the exact
  date/time, and record the outcome yourself (offer / next round / not
  selected), since that's often never emailed.
- An **analytics** view: applications over time, a response funnel, stage and
  outcome distribution, and per-source performance.
- **CSV/JSON export**, **CSV import** with validation, and one-click
  **database backup**.
- **Optional Gmail sync** (off by default) that reads recruiter mail and
  updates all of the above — see [below](#gmail-synchronization).

## Folder structure

```
JobTrace/
├── backend/
│   ├── server.py        # HTTP server + routing (stdlib http.server only)
│   ├── repository.py    # all business logic & DB access — import this directly
│   ├── database.py      # connection handling + schema + additive migrations
│   ├── validation.py    # input validation shared by every write path
│   ├── constants.py     # allowed stages / outcomes / sources / event types
│   └── sync/            # Gmail synchronization
│       ├── state.py     #   data/gmail_sync_state.json + unresolved items
│       ├── config.py    #   data/sync_config.json (method, schedule, secrets)
│       ├── doctor.py    #   "can automatic sync run, and what's missing?"
│       ├── scheduler.py #   in-process timer + the two execution paths
│       ├── agent.py     #   the keys-based sync agent (Anthropic API)
│       └── imap.py      #   read-only Gmail over an app password
├── frontend/
│   └── js/
│       ├── dashboard.js  # summary cards, filters, table, pagination
│       ├── tracker.js    # Tracker tab: assessment to-dos + interviews
│       ├── analytics.js  # analytics view
│       ├── detail.js     # application detail panel + timeline
│       ├── gmailsync.js  # Gmail pill + sync status/settings modal
│       └── …              # api.js, utils.js, charts.js, modal.js, importexport.js, app.js
├── tests/               # stdlib unittest — python3 -m unittest discover tests
├── data/                 # per-install, all gitignored
│   ├── applications.db             # created on first run
│   ├── sync_config.json            # sync method + any secrets (chmod 600)
│   ├── gmail_sync_state.json       # last sync result + processed message IDs
│   ├── sync_runs.json              # recent automatic-run history
│   └── unresolved_gmail_items.json # emails a sync couldn't act on
├── backups/              # timestamped DB backups (gitignored)
├── setup.command / setup.bat   # one-double-click first-run setup
├── start.command / start.bat   # launch the server
├── stop.command  / stop.bat    # stop the server
├── run_tests.command           # python3 -m unittest discover tests
├── start_hidden.vbs            # Windows: no-window wrapper around start.bat
├── requirements.txt      # only for the "scheduled with your keys" sync path
├── SYSTEM_BRIEF.pdf      # plain-language walkthrough for a non-technical reader
├── SETUP.md              # setup guide for a fresh AI assistant session
├── GMAIL_SYNC.md         # the sync policy every method follows
├── GMAIL_SYNC_TASK_PROMPT.md    # prompt the CLI method / a manual paste uses
├── GMAIL_SYNC_SETUP.md   # reference for the two automatic sync options
└── README.md
```

The app logo lives at `frontend/assets/logo.png` (browser tab icon, top
bar). `setup.command` renders it into the macOS app icon; on Windows,
`assets/logo.ico` is used for the shortcut.

## Desktop launcher

`setup.command` / `setup.bat` create it for you and bake in this folder's
path. **Move the project folder later → re-run setup** to refresh it.

- **macOS:** `~/Desktop/JobTrace.app` (built locally, so it's never
  Gatekeeper-quarantined). Drag it to the Dock. It runs with no visible
  window.
- **Windows:** `JobTrace.lnk` on the Desktop, pointing at `start_hidden.vbs`
  (no console flash).

To recreate either by hand, just re-run `setup.*`.

## Requirements

- **Windows or macOS** (Linux is untested but should work — see
  [Starting the app](#starting-the-app))
- **Python 3.10+** (uses only the standard library — `http.server`,
  `sqlite3`, `csv`, `json`; nothing to `pip install` to run the app or the
  manual/assistant-driven Gmail sync — only the optional headless API sync
  path needs real dependencies, see
  [Gmail synchronization](#gmail-synchronization))
- Any modern browser (Chrome, Edge, Firefox, Safari)
- No Node.js, no external database server, no internet connection needed

## Installing dependencies

None — for the app, the Tracker, the assistant-driven Gmail sync, and the
CLI-driven scheduled sync. `requirements.txt` is only for the "scheduled
with your keys" sync option (see
[Gmail synchronization](#gmail-synchronization)), and even then the default
IMAP path needs just `anthropic`. Just make sure Python is installed:

```bash
python3 --version
```

(`python --version` on Windows, if `python3` isn't on PATH there.) If that
fails, install Python from https://www.python.org/downloads/ — on Windows,
make sure **"Add python.exe to PATH"** is checked during setup.

## Starting the app

**Windows:** easiest is to double-click the **JobTrace** shortcut on your
Desktop. Nothing flashes on screen — after a couple of seconds your browser
opens straight to the app. You can also double-click **`start.bat`**
directly inside the project folder (shows a console window for a second
while it launches, then closes it). Both do the same thing.

**macOS:** double-click **`start.command`** (or drag it to the Dock/Desktop
first — see [Desktop shortcut](#desktop-shortcut)), or run `./start.command`
from Terminal.

Either OS, starting the app:

1. Starts the local server in the background, listening on
   `http://localhost:8766` (a different port than a stock JobTrace
   install, specifically so this copy can run side-by-side with another
   one on the same machine without either interfering with the other).
2. Opens that URL in your default browser automatically.
3. If JobTrace is already running, it just opens the browser again instead
   of starting a second copy.

You do not need to type any commands. The database (`data/applications.db`)
is created automatically the first time the server starts. Server output is
written to `data/server.log` — check that file if something seems wrong,
since there's no console window to read it from once it's running.

### Stopping the app

**Windows:** double-click **`stop.bat`**. Because the server runs with no
visible window (so it doesn't clutter your screen), this is the only way to
shut it down — there's no window to close or `Ctrl+C` inside.

**macOS:** double-click **`stop.command`**, or run `./stop.command` from
Terminal.

## Where your data lives

Everything is in one file: **`data/applications.db`** (a standard SQLite
database). Nothing is sent anywhere. You can open it with any SQLite browser
(e.g. [DB Browser for SQLite](https://sqlitebrowser.org/)) if you ever want
to inspect it directly.

## Backing up the database

Click **Export ▾ → Back up database** in the top bar. This makes a safe,
consistent copy (using SQLite's own backup API, so it's safe even while the
app is running) into the `backups/` folder, named like
`applications_backup_20260824_221200.db`.

### Restoring a backup

1. Close the app (double-click `stop.bat`).
2. Rename or move the current `data/applications.db` somewhere safe (in case
   you want it back).
3. Copy the backup file from `backups/` into `data/`, and rename it to
   `applications.db`.
4. Start the app again with `start.bat`.

## CSV import format

Use **Export ▾ → Import from CSV**. Expected header row and columns:

```
company,position,location,application_date,source,job_url,job_description,stage,outcome,notes
```

- `company`, `position`, and `application_date` are required for every row.
  `application_date` must be `YYYY-MM-DD` (if left blank, it defaults to
  today's date).
- `stage` must be one of: `Applied`, `Screening`, `Assessment`,
  `Interview 1`, `Interview 2`, `Final Interview`, `Offer`, `Closed`
  (defaults to `Applied` if blank).
- `outcome` must be one of: `Pending`, `Positive`, `Negative`, `Accepted`,
  `Withdrawn` (defaults to `Pending` if blank).
- All other columns are free text and optional.

**The whole file is validated before anything is inserted.** If any row has
an error, you'll see exactly which rows and why, and *nothing* is imported —
fix the file and try again. This avoids ending up with a half-imported,
inconsistent batch.

Each imported row creates an application plus an "Application Submitted"
timeline event, exactly like adding one by hand.

## How the metrics are calculated

These definitions are fixed in `backend/repository.py::get_summary_stats`,
so the dashboard and analytics view can never disagree with each other:

| Metric | Definition |
|---|---|
| Waiting / Pending | Total − Heard Back |
| Heard Back | `outcome != Pending` OR the stage has moved past Applied (a screening call, coffee chat, or interview invite counts even if you haven't updated outcome yet) |
| Positive Responses | `outcome IN (Positive, Accepted)`, OR still Pending but the stage has moved past Applied |
| Negative Responses | `outcome = Negative` |
| Assessments | ever reached Assessment stage or later |
| Interviews | ever reached Interview 1 or later |
| Offers | ever reached Offer stage, or outcome = Accepted |
| Response Rate | Heard Back ÷ Total |
| Positive Response Rate | Positive Responses ÷ Total |
| Interview Conversion Rate | Interviews ÷ Total |

"Ever reached" matters because rejecting an application after an interview
sets its stage to `Closed` — without tracking the *furthest* stage reached
separately (`max_stage_reached` in the schema), that history would be lost
the moment something is closed out.

## Data safety

- All writes go through `backend/repository.py` inside SQLite transactions —
  any failure rolls back rather than leaving partial data.
- Foreign keys (`application_events.application_id → applications.id`) are
  enforced with `PRAGMA foreign_keys = ON`, and events cascade-delete with
  their parent application.
- Every request is validated server-side (`backend/validation.py`) — the
  frontend cannot bypass these rules, and neither will a future automation
  script that calls the same functions directly.
- Double-submitting the "Add Application" form (e.g. a double-click) is
  guarded on both ends: the submit button disables itself immediately, and
  the backend deduplicates by a per-form request ID, so retried/duplicated
  requests return the original record instead of creating a copy.
- The database file is never deleted or overwritten by the app itself — it's
  only ever opened, migrated (schema is additive and idempotent), and
  written to via transactions.
- Malformed requests (bad JSON, invalid dates, unknown stage/outcome values,
  oversized text) are rejected with a 400 error and a clear message instead
  of corrupting data.

## Gmail synchronization

**Off by default.** JobTrace makes no network calls on its own; a sync is a
separate thing you turn on. Everything below is configured in the dashboard:
the **Gmail pill (top-right) → Settings**, which shows a live readiness
checklist. Full reference: **[GMAIL_SYNC_SETUP.md](GMAIL_SYNC_SETUP.md)**.

| | **Ask your assistant** | **Scheduled via CLI** | **Scheduled with your keys** |
|---|---|---|---|
| How it works | You say "sync my Gmail"; it reads Gmail via its own connector | The server runs `claude`/`codex` on a timer | The server runs the sync in-process |
| Assistant app | Yes (its Gmail connector) | Yes (`claude`/`codex` CLI, signed in, Gmail connector added) | **No** |
| Runs automatically | No | Yes | Yes |
| Cost | your plan | your plan | **your Anthropic API key**, per run |
| Setup | none | CLI sign-in + a Gmail connector on the CLI | Anthropic key + Gmail (Google sign-in, or an app password) |

All three follow the **same rules** and write the **same files**, so they
mix freely.

- **[GMAIL_SYNC.md](GMAIL_SYNC.md)** is the self-contained policy every
  method follows (matching tiers, status mapping, duplicate protection, and
  a "lessons from the first sync" section — e.g. Gmail search excludes Trash
  by default). The keys-based agent reads it at runtime, so there's one copy
  of the rules. Ask your assistant to "sync Gmail" and point it here.
- **Automatic sync runs in the server process** — no launchd, no Task
  Scheduler. It only runs while JobTrace is open, so add the launcher to
  your login items for unattended coverage.
- **"Scheduled with your keys"** takes Gmail either way: **Google sign-in**
  (OAuth, `gmail.readonly` scope, revocable — recommended, but needs a
  one-time Google Cloud OAuth client) or a **Gmail app password** (no Cloud
  console, but can't be scoped read-only — a trade-off the Settings panel
  spells out).
- The **Gmail pill** shows the last sync, the last automatic run's result
  (and its error, if any), and unresolved items. It can't tell which method
  produced a given sync — they all write the same way.
- **Duplicate protection** is enforced twice: `data/gmail_sync_state.json`
  tracks every processed Gmail message ID, and
  `application_events.gmail_message_id` is a second, database-level guard.
  Running the same sync twice leaves the tracker unchanged.
- **[SYSTEM_BRIEF.pdf](SYSTEM_BRIEF.pdf)** is a plain-language walkthrough
  of the whole system — what it is, install, what it does, and how the
  backend works — with workflow diagrams, written for a non-technical reader.

## Development

```
backend/          core: server.py (routing) -> repository.py (business logic)
                  -> validation.py -> database.py (schema + connection)
backend/sync/      Gmail sync: state, config, doctor, scheduler, agent, imap
frontend/js/       one module per view; no build step, no framework
tests/             stdlib unittest, no dependencies
```

Run the suite (nothing to install):

```bash
python3 -m unittest discover tests        # or: ./run_tests.command
```

Schema changes are additive only — add a column with `_add_column()` in
`backend/database.py::_migrate_schema`; it backs the database up first and is
safe to run repeatedly.

## Extending it

Everything goes through `backend/repository.py` — a standalone script (or
another sync transport) imports it directly, no HTTP server needed, and
gets the same validation, transactions, and auto-generated timeline events:

```python
from backend import repository as repo

application = repo.find_matching_application(company="KLM", position="Management Trainee")

repo.add_event(
    application_id=application["id"],
    event_type="Assessment Invitation",
    event_date="2026-08-24",
)

repo.update_application_stage(
    application_id=application["id"],
    stage="Assessment",
    outcome="Positive",
)
```

`backend.database.new_connection()` opens an independent connection to the
same `data/applications.db` for scripts that live outside the server's
request-per-thread lifecycle. The schema is additive: `_migrate_schema()` in
`backend/database.py` adds columns idempotently on startup (that's how the
Tracker's `scheduled_for` / `item_status` and the Gmail `gmail_message_id`
columns arrived), and new tables that reference `applications.id` follow the
same `ON DELETE CASCADE` pattern as `application_events`.
