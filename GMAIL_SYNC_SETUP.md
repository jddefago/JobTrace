# Automatic Gmail Sync — Setup

The tracker works with no Gmail sync at all. This covers the two **automatic**
options; for the on-demand "ask your assistant to sync" path (no setup),
see [GMAIL_SYNC.md](GMAIL_SYNC.md).

Everything is configured from the dashboard: the **Gmail pill (top-right) →
Settings**. That panel shows a live readiness checklist and the one fix for
each gap. This file is the longer reference behind it.

| | **Ask your assistant** | **Scheduled via CLI** | **Scheduled with your keys** |
|---|---|---|---|
| Assistant app needed | Yes (its Gmail connector) | Yes (`claude`/`codex` CLI) | **No** |
| Runs automatically | No | Yes | Yes |
| Cost | your assistant plan | your assistant plan | **your Anthropic API key**, per run |
| Setup | none | CLI sign-in + Gmail connector | one or two pasted secrets |

All paths follow **[GMAIL_SYNC.md](GMAIL_SYNC.md)** (read at runtime — one
copy of the rules) and write the same local files. Gmail access is
**read-only** in every case.

---

## Scheduled via the `claude` / `codex` CLI

The running server shells out to the CLI on a timer. **This is the option
with the most friction** — pick it only if you already run a Gmail MCP
server in your CLI, or want to. Otherwise "ask your assistant" (no setup) or
"scheduled with your keys" (below) are easier.

1. Settings → **"Scheduled via CLI"**, pick `claude` or `codex`.
2. The checklist flags two things you do once, in a terminal:
   - **Sign in:** run `claude` (or `codex`) and log in.
   - **Give the CLI a Gmail connector.** This is separate from connecting
     Gmail in the Claude desktop app — the CLI has its own connector list
     (`claude mcp list`). Ways to do it, easiest first:
     - If your Claude plan has **connectors**, enable the Gmail connector in
       your Claude account settings; Claude Code can use it. Confirm with
       `claude mcp list`.
     - Otherwise add a **community Gmail MCP server** with `claude mcp add`
       (e.g. an `npx`-run Gmail server). Note these run their *own* Google
       OAuth — you end up doing the same Google Cloud OAuth-client setup as
       the "Google sign-in" transport below, just wired into the CLI instead
       of JobTrace.
3. When the checklist is green, tick **"Run automatically"** and pick a
   frequency. **"Sync now"** tests it.

The CLI runs with `GMAIL_SYNC_TASK_PROMPT.md` as its instructions and a
tool allow-list restricted to reading Gmail and running Python against the
repository — a crafted email can't get it to run arbitrary commands.

---

## Scheduled with your own keys

The server runs the sync in-process — no CLI, no assistant app. You provide
Gmail access and an Anthropic API key.

### Anthropic API key

<https://console.anthropic.com> → create a key. Paste it into Settings.
Billed per run (typically cents — check the console after a couple of runs
before scheduling it every few hours). Or set `ANTHROPIC_API_KEY` in the
environment and leave the field blank.

```bash
pip install -r requirements.txt        # just `anthropic` for the IMAP path
```

### Gmail access — pick a transport

#### Option 1: Google sign-in (OAuth)  ·  recommended

The token is scoped to **`gmail.readonly`** — it literally cannot send,
delete, or modify mail — and you can revoke it per-app from your Google
account. The cost is a one-time Google Cloud OAuth client (~10 min).

```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

1. <https://console.cloud.google.com> → create/choose a project.
2. **APIs & Services → Library** → **Gmail API** → Enable.
3. **OAuth consent screen** → **External** → fill required fields → add your
   own Gmail under **Test users** (keeps it in "Testing" mode — fine for
   personal use, no Google verification needed).
4. **Credentials → Create Credentials → OAuth client ID** → **Desktop app**.
5. Download the JSON → save as `data/gmail_api_credentials.json` (gitignored).
6. Settings → transport **"Google sign-in (OAuth)"**, then run the one-time
   consent from a terminal:
   ```bash
   python3 backend/sync/agent.py --dry-run
   ```
   A browser opens once to approve read-only access; the token is cached in
   `data/gmail_api_token.json` and every later run is unattended.

#### Option 2: Gmail app password (IMAP)  ·  quick, less locked-down

No Google Cloud console — but a **security trade-off**: a Gmail app password
**cannot** be limited to read-only (it grants full IMAP/SMTP, i.e. read
*and send*), and it's a static secret sitting in `data/sync_config.json`
(written `chmod 600`). Use it only on a machine you control, and know you
can revoke it instantly. JobTrace's IMAP code only ever reads — but that's
our restraint, not a limit Google enforces.

1. <https://myaccount.google.com> → **Security** → **2-Step Verification**
   (turn on if needed) → **App passwords** → generate one for "Mail".
2. Settings → transport **"Gmail app password"** → enter your Gmail address
   and the 16-character password → **"Test Gmail connection"**.
3. To revoke later: same App passwords page → remove it.

Under the hood this is IMAP with Gmail's `X-GM-RAW` search (same query
syntax as the API) and `X-GM-MSGID` (the same message id the API uses), so
dedup is identical across transports. Standard library only — no
`pip install` beyond `anthropic`.

### Turn it on

Settings → **"Run automatically"** + a frequency. **"Sync now"** runs one
immediately. `--dry-run` on the CLI logs intended actions without writing.

---

## Automatic sync only runs while JobTrace is open

The scheduler is part of the server process. For unattended coverage keep
JobTrace running:

- **macOS:** System Settings → General → Login Items → add the JobTrace
  launcher.
- **Windows:** put a shortcut in the Startup folder (`shell:startup`).

---

## Keeping secrets out of a synced folder

`.gitignore` keeps `data/sync_config.json`,
`data/gmail_api_credentials.json`, and `data/gmail_api_token.json` out of
git — but that's separate from a cloud *file-sync* client (OneDrive,
Dropbox, Google Drive, iCloud). If the project folder lives inside a synced
tree, those files — and `data/applications.db` — are uploaded like anything
else. Either move the project out of the synced tree, or point the OAuth
files elsewhere with `JOBTRACE_GMAIL_CREDENTIALS` / `JOBTRACE_GMAIL_TOKEN`
(and `ANTHROPIC_API_KEY` instead of storing the key). The IMAP app password
lives only in `data/sync_config.json` (written `chmod 600`).

---

## Troubleshooting

Every run's log lands in `data/sync_logs/`. The dashboard's Gmail pill shows
the last automatic run and its error, if any.

- **"Gmail rejected the address / app password"** — it must be an *app
  password*, not your normal password; 2-Step Verification must be on.
- **CLI run "did nothing" / sign-in expired** — run `claude` / `codex` in a
  terminal and log back in; confirm `claude mcp list` still shows Gmail.
- **"No Anthropic API key"** — set it in Settings or `ANTHROPIC_API_KEY`.
- **OAuth errors after it previously worked** — access was revoked or the
  refresh token expired. Delete `data/gmail_api_token.json`, run the
  `--dry-run` consent again.
- **Model errors** — set `model` in Settings to a current ID from
  <https://docs.claude.com/en/docs/about-claude/models>.

## Data safety

`backend/sync/agent.py` only ever calls `backend/repository.py` and
`backend/sync/state.py` (no ad-hoc SQL), never modifies Gmail, never deletes
tracker data, and every write re-checks duplicate protection — a model
mistake can't create the same event or application twice.
