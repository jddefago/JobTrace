# JobTrace — Setup Guide (for your AI assistant)

This file is written so a **fresh AI assistant session — Claude Code, Claude
Desktop, Codex CLI, or similar, with no memory of any prior conversation —
can set JobTrace up by reading this file alone.** If a user just downloaded
this and asked you to "set it up," read this whole file first.

> **Golden rule.** The tracker is the product. Gmail sync is an optional
> add-on with several moving parts, and some of them you *cannot* finish from
> a sandboxed session. If a sync step is blocked, say plainly which step and
> what the user must do, then stop — never leave the app itself broken while
> chasing sync.

---

## 1. Get the app running — required, ~2 minutes

Pure standard-library Python; nothing to `pip install` for the app.

1. **Check Python 3:** `python3 --version` (or `python --version`). 3.9+ is
   fine — macOS's built-in `/usr/bin/python3` works. If it's missing, send
   the user to <https://www.python.org/downloads/> (on Windows, tick "Add
   python.exe to PATH") and **stop here** until that's done.

2. **Run setup:**
   - macOS: `./setup.command` (or double-click it in Finder)
   - Windows: `setup.bat`
   - Either one is safe to re-run. It clears the macOS quarantine flag,
     (re)creates the desktop launcher with this folder's path baked in,
     starts the server, and opens <http://localhost:8766>.
   - No `setup.*`? Use `./start.command` / `start.bat` directly.

3. **Confirm:** the dashboard loads at `http://localhost:8766` with an empty
   state, and `data/applications.db` now exists. That's the whole app
   working.

**macOS quarantine:** a downloaded (non-`git clone`) copy is Gatekeeper-
flagged. `setup.command` clears it; if double-clicking still refuses,
right-click → Open → Open once, or run
`xattr -dr com.apple.quarantine .` in the project folder.

**Linux:** untested but `python3 backend/server.py` runs unmodified.

If step 1–3 fail it's almost always Python not installed or not on PATH.
Fix that and nothing else until the dashboard loads.

---

## 2. Gmail sync — optional, only if the user asks

JobTrace has **no Gmail integration of its own.** There are three ways to
sync it. **Ask the user which they want; default to A** unless they
specifically want it to run automatically.

All three write the same local files (`data/applications.db`,
`data/gmail_sync_state.json`, `data/unresolved_gmail_items.json`) following
the same rules, so they can be mixed.

### A. Manual — "sync when I ask" · recommended, zero setup

**You** (this assistant session) are the integration. When the user says
"sync my Gmail" / "check for job updates":

1. Read **[GMAIL_SYNC.md](GMAIL_SYNC.md)** in full, including its "lessons
   from the first sync" section.
2. Follow it: search Gmail through your own connector, classify each mail,
   write results via `backend/repository.py` and `backend/sync/state.py`.

Needs only that your assistant app has Gmail access (Claude Desktop: connect
Gmail in its settings). Nothing to install, identical on macOS and Windows,
nothing runs unless asked. **This is the low-friction path — steer here
unless the user wants unattended sync.**

### B. Automatic via the `claude` / `codex` CLI · free, more moving parts

JobTrace's own scheduler (in the running server) shells out to the CLI on a
timer. Configure it in the dashboard — **Gmail pill (top-right) → Settings →
"Scheduled via CLI"** — which shows a live readiness checklist. Or drive it
over the API:

```
PUT /api/sync/config   {"method":"cli","cli":{"command":"claude"},
                        "auto":{"enabled":true,"interval_hours":6}}
GET /api/sync/doctor    -> tells you exactly what's still missing
POST /api/sync/run      -> run once now
```

This is the **highest-friction** option — recommend it only if the user
already runs a Gmail MCP server in their CLI. Two prerequisites, **neither
of which you can complete from a sandboxed session**:

1. The CLI **installed and signed in** — `claude` (or `codex`) once in a
   terminal.
2. A **Gmail connector on that CLI** — either a Gmail connector enabled in
   their Claude account (if their plan has connectors; Claude Code can use
   it), or a community Gmail MCP server added with `claude mcp add`. The
   latter runs its own Google OAuth — same Cloud-client work as option C's
   OAuth transport. Separate from connecting Gmail in the desktop app.
   Verify: `claude mcp list` must show Gmail.

`GET /api/sync/doctor` reports both. If not `ready`, name the red item and
its fix, then move on.

### C. Automatic with your own keys · no CLI, no assistant app

The scheduler runs the sync in-process. Needs an **Anthropic API key**
(<https://console.anthropic.com>, billed per run — confirm the user is OK)
and Gmail access — one of two transports:

- **Google sign-in (OAuth) — recommended.** Token is scoped
  `gmail.readonly` (cannot send/delete), revocable per-app. Costs a one-time
  Google Cloud OAuth client (~10 min): enable Gmail API, make a Desktop
  OAuth client, save the JSON as `data/gmail_api_credentials.json`, run
  `python3 backend/sync/agent.py --dry-run` once for the browser
  consent. Needs `pip install google-api-python-client google-auth-oauthlib`.
- **Gmail app password (IMAP) — quicker, less locked-down.** No Cloud
  console (myaccount.google.com → Security → App passwords), but the
  password **can't be scoped read-only** — it grants read *and send* — and
  sits in `data/sync_config.json` (chmod 600). Fine on a machine the user
  controls; make sure they know they can revoke it. Only `anthropic` to
  install.

Set it up in the dashboard (**Settings → "Scheduled with my keys"**) or via
API:

```
PUT /api/sync/config  {"method":"keys","keys":{
    "gmail_transport":"api",        # or "imap"
    "gmail_address":"…","gmail_app_password":"…",   # imap only
    "anthropic_api_key":"…"},"auto":{"enabled":true,"interval_hours":6}}
POST /api/sync/run
```

Full walkthrough: **[GMAIL_SYNC_SETUP.md](GMAIL_SYNC_SETUP.md)**.

### Automatic sync only runs while the server runs

The scheduler lives in the server process. For unattended coverage the user
should keep JobTrace running — add the desktop launcher to Login Items
(macOS: System Settings → General → Login Items) or the Startup folder
(Windows). Say this; don't assume it.

---

## 3. Tell the user what you did

Plainly:

- App running at `http://localhost:8766` (or why not).
- Which sync method is configured, and whether `GET /api/sync/doctor` says
  it's `ready`.
- What's left for the user to do themselves — CLI sign-in, adding the CLI
  Gmail connector, generating an app password, `pip install`.

**Never say automatic sync is "on" unless `GET /api/sync/doctor` returns
`ready: true` and you enabled it.** For the manual path, never say it's
"active" — it runs only when asked.
