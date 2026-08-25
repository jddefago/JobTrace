# JobTrace

A local-first dashboard for tracking job applications: pipeline stage, outcome,
timeline history, job descriptions, notes, and application statistics.

Everything runs on your computer. There is no cloud service, no external
account, and no data leaves your machine. The entire app is a local Python
web server (stdlib only) serving a plain HTML/CSS/JS frontend, backed by a
single SQLite file.

This is Phase 1. Gmail integration, AI classification, scheduled background
workers, and cloud sync are explicitly **not** part of this build — see
[Future automation](#future-automation) for how this phase was designed to
support them later without a rewrite.

## Getting started

Just downloaded this? The fastest path is to open this folder with your AI
coding assistant (Claude Code, Claude Desktop, Codex CLI, or similar) and
ask it to set JobTrace up for you — it can read **[SETUP.md](SETUP.md)**,
a self-contained guide written for exactly that, and walk you through
starting the app and (optionally) linking your own Gmail. No account,
API key, or payment is required for the base app.

Prefer to do it by hand? See [Requirements](#requirements) and
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
- An **analytics** view: applications over time, a response funnel, stage and
  outcome distribution, and per-source performance.
- **CSV/JSON export**, **CSV import** with validation, and one-click
  **database backup**.

## Folder structure

```
JobTracker/
├── backend/
│   ├── server.py        # HTTP server + routing (stdlib http.server only)
│   ├── repository.py    # All business logic & DB access — the module a
│   │                     # future automation script should import directly
│   ├── database.py      # Connection handling + schema (SQLite)
│   ├── validation.py    # Input validation shared by every write path
│   ├── constants.py     # Allowed stages / outcomes / sources / event types
│   └── gmail_sync.py    # Local JSON state for Gmail sync (see below) —
│                         # no network calls, just file I/O
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── js/
│       ├── api.js         # fetch wrapper for the backend API
│       ├── utils.js        # formatting, badges, toasts, confirm dialog
│       ├── charts.js       # dependency-free SVG/bar chart rendering
│       ├── dashboard.js    # summary cards, filters, table, pagination
│       ├── modal.js        # add/edit application side panel
│       ├── detail.js       # application detail panel + timeline events
│       ├── analytics.js    # analytics view
│       ├── importexport.js # export menu, backup, CSV import
│       └── app.js          # bootstrap, tab navigation, shared state
├── data/
│   ├── applications.db             # created automatically on first run (gitignored)
│   ├── gmail_sync_state.json       # last Gmail sync result + processed message IDs
│   └── unresolved_gmail_items.json # emails a Gmail sync couldn't confidently act on
├── backups/              # timestamped DB backups land here (gitignored)
├── assets/
│   └── logo.ico          # used by the desktop shortcut
├── start.bat
├── start_hidden.vbs
├── stop.bat
├── JobTrace.lnk          # ready-made Desktop shortcut — drag this onto your Desktop
├── requirements.txt
├── SETUP.md              # self-contained setup guide for a fresh AI assistant session
├── GMAIL_SYNC.md         # instructions an AI assistant follows to sync Gmail into this app
├── GMAIL_SYNC_TASK_PROMPT.md # ready-to-paste prompt for a future scheduled sync task
├── run_gmail_sync_claude.bat # scheduled-sync runner for Claude Code
├── run_gmail_sync_codex.bat  # scheduled-sync runner for Codex CLI
└── README.md
```

The app logo lives at `frontend/assets/logo.png` so the running server can
serve it (browser tab icon, top bar). If you replace the logo, update that
file, then regenerate `assets/logo.ico` from it (see below).

## Desktop shortcut

A ready-made **`JobTrace.lnk`** shortcut is included in this folder —
just drag or copy it onto your Desktop. It launches `start_hidden.vbs` (a
tiny wrapper that runs `start.bat` with no window at all — not even a
brief flash) and uses the app logo as its icon.

That shortcut points at this exact folder's current location, so **if you
move or rename this folder after copying the shortcut out, the shortcut
will stop working** — double-clicking it will do nothing or show an
error. If that happens (or you deleted it and want it back), regenerate
it by running this in PowerShell from the project folder:

```powershell
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$([Environment]::GetFolderPath('Desktop'))\JobTrace.lnk")
$Shortcut.TargetPath = "$PWD\start_hidden.vbs"
$Shortcut.WorkingDirectory = "$PWD"
$Shortcut.IconLocation = "$PWD\assets\logo.ico,0"
$Shortcut.Save()
```

## Requirements

- **Windows**
- **Python 3.10+** (uses only the standard library — `http.server`,
  `sqlite3`, `csv`, `json`; nothing to `pip install` for this phase)
- Any modern browser (Chrome, Edge, Firefox)
- No Node.js, no external database server, no internet connection needed

## Installing dependencies

There are none to install for this phase — `requirements.txt` is kept as a
placeholder for later phases (e.g. a Gmail-polling worker will need
`google-api-python-client`; an AI-classification client will need
`anthropic`). Just make sure Python is installed and on your PATH:

```bash
python --version
```

If that fails, install Python from https://www.python.org/downloads/ and make
sure **"Add python.exe to PATH"** is checked during setup.

## Starting the app

Easiest: double-click the **JobTrace** shortcut on your Desktop. Nothing
flashes on screen — after a couple of seconds your browser opens straight to
the app.

You can also double-click **`start.bat`** directly inside the project
folder (shows a console window for a second while it launches, then closes
it). Both do the same thing:

1. Start the local server invisibly in the background, listening on
   `http://localhost:8766` (a different port than a stock JobTrace
   install, specifically so this copy can run side-by-side with another
   one on the same machine without either interfering with the other).
2. Open that URL in your default browser automatically.
3. If JobTrace is already running, it just opens the browser again instead
   of starting a second copy.

You do not need to type any commands. The database (`data/applications.db`)
is created automatically the first time the server starts. Server output is
written to `data/server.log` — check that file if something seems wrong,
since there's no console window to read it from anymore.

### Stopping the app

Double-click **`stop.bat`**. Because the server now runs with no visible
window (so it doesn't clutter your screen), this is the only way to shut it
down — there's no window to close or `Ctrl+C` inside.

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

JobTrace itself still makes no network calls to Gmail or any AI API — it
only reads and writes its own local files. Gmail sync is performed by an
**AI coding assistant session** (Claude Code, Claude Desktop, Codex CLI,
or similar), using its own Gmail connector/MCP tool, that reads
recruitment emails and writes the results directly into this app's
database and into `data/gmail_sync_state.json` /
`data/unresolved_gmail_items.json`. It's a manual, on-demand process by
default — nothing is scheduled automatically unless you set that up.

- **[GMAIL_SYNC.md](GMAIL_SYNC.md)** is the full, self-contained
  instruction set an assistant session follows to do this safely
  (matching rules, status mapping, duplicate protection, unresolved-item
  handling, and a "lessons from the first sync" section documenting real
  mistakes worth not repeating — e.g. Gmail search excludes Trash by
  default). Ask your assistant to "sync Gmail" or "check for job
  application updates" and point it at that file if it doesn't already
  know about it.
- **[GMAIL_SYNC_TASK_PROMPT.md](GMAIL_SYNC_TASK_PROMPT.md)** is a
  ready-to-use prompt for turning this into a recurring scheduled task
  later — paste it as the task's instructions when you're ready to set
  that up, or use it with **`run_gmail_sync_claude.bat`** /
  **`run_gmail_sync_codex.bat`** plus Windows Task Scheduler. It's not
  scheduled by itself; nothing runs automatically until you create the
  schedule.
- The top bar shows a **Gmail sync status pill** with the last sync time
  and result; click it for the full breakdown and any unresolved items.
- Duplicate protection is enforced two ways: `data/gmail_sync_state.json`
  tracks every Gmail message ID already processed, and
  `application_events.gmail_message_id` is checked as a second,
  database-level guard — running the same sync twice is safe and leaves
  the tracker unchanged the second time.
- **[JobTrace_System_Brief.pdf](JobTrace_System_Brief.pdf)** is an
  optional plain-language walkthrough of how the whole system fits
  together. It was written with Claude Code specifically in mind for the
  automation section — if you're using Codex instead, the concepts carry
  over directly, just substitute "Codex CLI" wherever it says "Claude
  Code."

## Future automation

The architecture is intentionally shaped so a **separate** future script
(e.g. a scheduled Gmail-polling worker, once that phase is built) can plug
in later without touching the frontend or the HTTP layer at all. It would
import `backend/repository.py` directly and call the same functions the UI
and the Gmail sync workflow above both use:

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

This works today, from any standalone Python script, with no server running
— `repository.database.new_connection()` opens the same `data/applications.db`
file directly. When Gmail/AI phases are built, they'll likely add a few new
tables (e.g. `recruiters`, `recruitment_emails`, `ai_classifications`,
`assessments`) that reference `applications.id`, following the same pattern
as `application_events`. Nothing in the current schema needs to change for
that — it was designed with those tables in mind from the start.
