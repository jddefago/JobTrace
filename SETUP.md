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
- `requirements.txt` has nothing to install for this phase — the backend
  uses only the Python standard library. Don't run `pip install` unless
  you hit an actual `ModuleNotFoundError`.
- The launcher scripts (`start.bat`, `stop.bat`, `start_hidden.vbs`) are
  Windows-specific. If the user is on macOS/Linux, skip to the "Non-Windows"
  note at the end of step 2 instead of trying to run the `.bat` files.

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

**Non-Windows (macOS/Linux):** there's no `.bat`/`.vbs` equivalent yet.
Run the server directly from the project root:

```bash
python3 backend/server.py
```

Then open `http://localhost:8766` in a browser. Offer to write equivalent
shell scripts (`start.sh`/`stop.sh`) if the user wants the same
one-click convenience `start.bat` gives on Windows — that's a reasonable
thing to build for them, just don't assume it already exists.

## 3. Optional: Gmail sync

**Only do this if the user actually asks for it** — it's opt-in, not
required for the tracker itself to work.

Explain clearly: JobTrace has no Gmail integration of its own. Gmail sync
works by *you* (or whichever assistant runs it) reading the user's Gmail
through your own connector/MCP tool and writing results into JobTrace's
local files — the assistant session is the integration, not the app.

- **One-off sync:** read `GMAIL_SYNC.md` in full first (it has a
  "lessons from the first sync" section with mistakes worth not
  repeating), then follow `GMAIL_SYNC_TASK_PROMPT.md`.
- **Recurring/scheduled sync:** this needs two things the user sets up
  themselves, not something you can fully configure from inside a
  sandboxed session:
  1. A Gmail MCP connector authorized under whichever CLI will run the
     scheduled task (Claude Code or Codex CLI) — done once, in that
     tool's own account/connector settings.
  2. A Windows Task Scheduler entry pointed at `run_gmail_sync_claude.bat`
     (for Claude Code) or `run_gmail_sync_codex.bat` (for Codex CLI),
     running on whatever interval the user wants (every 6-8 hours is
     reasonable). You can create this scheduled task for them if asked,
     using the Windows Task Scheduler CLI (`schtasks`) — just confirm the
     interval and behavior with the user first, since it runs
     unattended.

Never claim Gmail sync is "active" unless you've actually walked the user
through authorizing the connector and, if they wanted scheduling, created
the scheduled task yourself in this session.

## 4. Tell the user what you did

Report plainly: what you checked, what's now running, the dashboard URL,
and whether Gmail sync was set up or left for later. Don't assume
follow-up steps happened silently — say what's actually configured now
versus what the user would still need to do themselves.
