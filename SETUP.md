# JobTrace — Setup Guide (for your AI assistant)

This document is written so that a **fresh AI coding assistant session —
Claude Code, Claude Desktop, Codex CLI, or similar — with no memory of any
prior conversation, can set JobTrace up correctly** by reading this file
alone. If a user has just downloaded this project and asked you to "set
up JobTrace" or "get this running," read this whole file before doing
anything.

## What you're setting up

JobTrace is a local, offline job-application tracker: a small Python HTTP
server + SQLite database, serving a plain HTML/CSS/JS dashboard. It makes
no network calls of its own — nothing here talks to the internet except
the optional Gmail-sync workflow described in step 3, which is a separate,
opt-in feature the user has to explicitly ask for.

This is a fresh, empty copy: there is no existing data yet. `data/` and
`backups/` are present but empty (aside from a `.gitkeep` placeholder) —
that's expected, not a bug.

## 1. Check prerequisites

- Confirm Python 3.10+ is installed and on PATH: run `python --version`
  (or `python3 --version`). If it's missing, tell the user to install it
  from https://www.python.org/downloads/ and, on Windows, make sure
  **"Add python.exe to PATH"** is checked during install.
- `requirements.txt` has nothing to install for the app itself, or for the
  manual/assistant-driven Gmail sync — the backend uses only the Python
  standard library. Don't run `pip install` unless you're setting up the
  headless API Gmail sync (step 3, option C) or hit an actual
  `ModuleNotFoundError`.
- The launcher scripts come in two flavors: `start.bat`/`stop.bat`/
  `start_hidden.vbs` for Windows, `start.command`/`stop.command` for macOS.
  Both are checked into the repo — check the user's OS (from your own
  environment context if you have it, otherwise ask) before step 2 so you
  run the right one.

## 2. First run

**Windows:**
1. Run `start.bat` from the project root (or double-click it). This
   starts the server hidden in the background on `http://localhost:8766`
   and opens the dashboard in the default browser. (This port deliberately
   differs from a stock JobTrace install's 8765, so this copy can run at
   the same time as another one on the same machine without either seeing
   the other's data.)
2. Confirm `data/applications.db` gets created automatically — it won't
   exist yet in a fresh download, and that's expected.
3. Confirm the dashboard loads with an empty state (no applications yet).
   That confirms the server and database are working.
4. A ready-made `JobTrace.lnk` shortcut is already sitting in the project
   folder — offer to copy/move it onto the user's Desktop for them.
   **It only works if this project folder stays where it currently is** —
   its target path is baked in at the folder's current location. If the
   user has already moved this folder since downloading it (or plans to),
   regenerate the shortcut instead using the PowerShell snippet in
   `README.md`'s "Desktop shortcut" section, run from the project's
   *current* location.

**macOS:**
1. Make sure `start.command`/`stop.command` are executable (they're
   committed with the exec bit set, so this is usually already true after a
   `git clone`; if it was downloaded some other way — a zip, AirDrop, a
   cloud-synced folder — run `chmod +x start.command stop.command` once
   first).
2. Run `./start.command` from the project root, or double-click it in
   Finder (a Terminal window briefly appears, then the dashboard opens at
   `http://localhost:8766` — the same non-hidden experience plain
   `start.bat` gives on Windows; there's no fully-hidden launcher for macOS
   yet).
3. Confirm `data/applications.db` gets created automatically and the
   dashboard loads with an empty state, same as the Windows steps above.
4. To stop the server later: `./stop.command` (or double-click it).
5. Offer to drag `start.command` onto the Dock or Desktop as a one-click
   launcher, if the user wants that convenience.

**Linux:** not tested, but `python3 backend/server.py` directly should work
unmodified (pure-stdlib server) — the `.command` script's logic (minus the
macOS-specific `open` command, which would need to become `xdg-open`) should
port over if the user wants the same convenience.

## 3. Optional: Gmail sync

**Only do this if the user actually asks for it** — it's opt-in, not
required for the tracker itself to work.

Explain clearly: JobTrace has no Gmail integration of its own. There are
**three ways** to sync it, and the user should pick based on whether they
want it automatic and whether they're OK with their own Anthropic API
billing:

**A. One-off, manual, free** — *you* (this assistant session) read the
user's Gmail through your own connector/MCP tool and write results into
JobTrace's local files directly — the assistant session is the integration,
not the app. Read `GMAIL_SYNC.md` in full first (it has a "lessons from the
first sync" section with mistakes worth not repeating), then follow
`GMAIL_SYNC_TASK_PROMPT.md`.

**B. Recurring, free, but requires an assistant app installed** — same
mechanism as A, run on a schedule instead of on demand. This needs two
things the user sets up themselves, not something you can fully configure
from inside a sandboxed session:
  1. A Gmail MCP connector authorized under whichever CLI will run the
     scheduled task (Claude Code or Codex CLI) — done once, in that
     tool's own account/connector settings.
  2. A scheduled task pointed at the right runner script, running on
     whatever interval the user wants (every 6-8 hours is reasonable):
     - **Windows**: Task Scheduler → `run_gmail_sync_claude.bat` (Claude
       Code) or `run_gmail_sync_codex.bat` (Codex CLI). You can create this
       with `schtasks` if asked.
     - **macOS**: `launchd` → `run_gmail_sync_claude.sh` or
       `run_gmail_sync_codex.sh`, using `com.jobtrace.gmailsync.plist.example`
       as the template (copy to `~/Library/LaunchAgents/`, fill in the
       placeholders, `launchctl load`).

     Confirm the interval and behavior with the user first either way, since
     it runs unattended.

**C. Recurring, headless, no assistant app required — billed to the user's
own Anthropic API key.** `backend/gmail_api_sync.py` calls the Gmail API and
Anthropic API directly, so nothing needs to be installed/running at sync
time beyond Python. This needs real one-time setup on the user's part
(a Google Cloud OAuth client, an Anthropic API key) — walk them through
**`GMAIL_SYNC_API.md`** in full if they want this option; don't try to
improvise the Google Cloud steps from memory. Once set up, it's scheduled
the same way as option B, just pointed at `run_gmail_sync_api.bat` /
`run_gmail_sync_api.sh` instead.

If the user hasn't said which they want, ask — don't default to one
silently, since B and C both run unattended and C has real billing
implications.

Never claim Gmail sync is "active" unless you've actually walked the user
through authorizing the connector and, if they wanted scheduling, created
the scheduled task yourself in this session.

## 4. Tell the user what you did

Report plainly: what you checked, what's now running, the dashboard URL,
and whether Gmail sync was set up or left for later. Don't assume
follow-up steps happened silently — say what's actually configured now
versus what the user would still need to do themselves.
