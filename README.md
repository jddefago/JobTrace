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
│   ├── gmail_sync.py    # Local JSON state for Gmail sync (see below) —
│   │                     # no network calls, just file I/O
│   └── gmail_api_sync.py # Optional: headless Gmail sync via your own
│                         # Google + Anthropic API keys — see GMAIL_SYNC_API.md
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
│   └── logo.ico          # used by the Windows desktop shortcut
├── start.bat             # Windows: launch (hidden, background)
├── start_hidden.vbs      # Windows: no-window wrapper around start.bat
├── stop.bat              # Windows: stop
├── JobTrace.lnk          # ready-made Windows Desktop shortcut — drag this onto your Desktop
├── start.command         # macOS: launch (background, opens browser)
├── stop.command          # macOS: stop
├── requirements.txt      # only needed for the optional headless API Gmail sync
├── SETUP.md              # self-contained setup guide for a fresh AI assistant session
├── GMAIL_SYNC.md         # sync policy/rules an AI assistant (or gmail_api_sync.py) follows
├── GMAIL_SYNC_TASK_PROMPT.md # ready-to-paste prompt for a future scheduled sync task
├── GMAIL_SYNC_API.md     # setup guide for the headless, no-assistant-app sync option
├── run_gmail_sync_claude.bat / .sh # scheduled-sync runner for Claude Code (Windows / macOS)
├── run_gmail_sync_codex.bat / .sh  # scheduled-sync runner for Codex CLI (Windows / macOS)
├── run_gmail_sync_api.bat / .sh    # scheduled-sync runner for the headless API path
├── com.jobtrace.gmailsync.plist.example # macOS launchd template for scheduled sync
└── README.md
```

The app logo lives at `frontend/assets/logo.png` so the running server can
serve it (browser tab icon, top bar). If you replace the logo, update that
file, then regenerate `assets/logo.ico` from it (see below).

## Desktop shortcut

**Windows:** a ready-made **`JobTrace.lnk`** shortcut is included in this
folder — just drag or copy it onto your Desktop. It launches
`start_hidden.vbs` (a tiny wrapper that runs `start.bat` with no window at
all — not even a brief flash) and uses the app logo as its icon.

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

**macOS:** there's no equivalent hidden-window shortcut yet — drag
`start.command` onto the Dock or the Desktop for one-click launching
instead. Double-clicking it briefly opens a Terminal window while the
server starts (the same non-hidden experience plain `start.bat` gives on
Windows), then opens the dashboard in your browser.

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

There are none to install to run the app itself, or the manual/assistant-driven
Gmail sync — `requirements.txt` only lists dependencies for the optional
headless API Gmail sync (see [Gmail synchronization](#gmail-synchronization)).
Just make sure Python is installed and on your PATH:

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

JobTrace itself still makes no network calls to Gmail or any AI API on its
own — it only reads and writes its own local files
(`data/gmail_sync_state.json`, `data/unresolved_gmail_items.json`, and the
database). There are three ways to actually perform a sync, and you choose
which fits you:

| | **A. Manual assistant session** | **B. Assistant + scheduler** | **C. Headless API sync** |
|---|---|---|---|
| How it works | You ask Claude Code/Desktop/Codex to sync now; it reads Gmail via its own connector | Same as A, run automatically on a schedule | `backend/gmail_api_sync.py` calls the Gmail + Anthropic APIs directly with your own keys |
| Needs an assistant app installed | Yes | Yes | **No** |
| Runs automatically | No | Yes | Yes |
| Cost | Free | Free | Billed to your own Anthropic API key, per run |
| Setup | None | Gmail connector authorized once | Google Cloud OAuth client + Anthropic API key (one-time) |
| Set up via | `GMAIL_SYNC_TASK_PROMPT.md` | + Task Scheduler/`launchd` | [GMAIL_SYNC_API.md](GMAIL_SYNC_API.md) |

All three follow the exact same rules and write into the exact same local
files, so you can mix and match (e.g. use A day-to-day and only set up C
later for unattended coverage) without anything breaking.

- **[GMAIL_SYNC.md](GMAIL_SYNC.md)** is the full, self-contained
  instruction set both A/B (an assistant session) and C
  (`gmail_api_sync.py`, which reads this file at runtime as its policy —
  see [GMAIL_SYNC_API.md](GMAIL_SYNC_API.md)) follow to do this safely
  (matching rules, status mapping, duplicate protection, unresolved-item
  handling, and a "lessons from the first sync" section documenting real
  mistakes worth not repeating — e.g. Gmail search excludes Trash by
  default). Ask your assistant to "sync Gmail" or "check for job
  application updates" and point it at that file if it doesn't already
  know about it.
- **[GMAIL_SYNC_TASK_PROMPT.md](GMAIL_SYNC_TASK_PROMPT.md)** is a
  ready-to-use prompt for option A, and for turning it into option B later
  — paste it as the task's instructions when you're ready to set that up,
  or use it with **`run_gmail_sync_claude.bat`/`.sh`** or
  **`run_gmail_sync_codex.bat`/`.sh`** plus Windows Task Scheduler or
  macOS `launchd` (see `com.jobtrace.gmailsync.plist.example`). Nothing
  runs automatically until you create the schedule yourself.
- **[GMAIL_SYNC_API.md](GMAIL_SYNC_API.md)** covers option C end to end:
  Google Cloud + Anthropic API key setup, the first interactive run, and
  scheduling via `run_gmail_sync_api.bat`/`.sh`.
- The top bar shows a **Gmail sync status pill** with the last sync time
  and result; click it for the full breakdown and any unresolved items —
  it can't tell which of the three options produced a given sync, since
  they all write the same way.
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
