# Headless Gmail Sync via Your Own API Keys

This is the third way to keep JobTrace in sync with your Gmail, alongside
the two described in [README.md](README.md#gmail-synchronization):

| | Manual assistant session | Assistant + scheduler | **This: headless API sync** |
|---|---|---|---|
| Requires an AI assistant app installed | Yes (Claude Desktop/Code or Codex CLI) | Yes | **No** |
| Runs automatically on a schedule | No | Yes | Yes |
| Cost | Free (uses your assistant subscription) | Free | **Billed to your own Anthropic API key**, per run |
| One-time setup | None | Connector auth | Google Cloud OAuth client + Anthropic API key |
| Follows the same rules | [GMAIL_SYNC.md](GMAIL_SYNC.md) | [GMAIL_SYNC.md](GMAIL_SYNC.md) | [GMAIL_SYNC.md](GMAIL_SYNC.md) (same file, read at runtime) |

Use this if you want scheduled sync on a machine that doesn't have Claude
Desktop/Code or Codex CLI installed, or you'd rather pay for API usage
directly than rely on an assistant subscription being present. `backend/gmail_api_sync.py`
*is* the integration here — it calls the Gmail API and the Anthropic API
directly, using your own keys, and writes into the same local files
(`data/applications.db`, `data/gmail_sync_state.json`,
`data/unresolved_gmail_items.json`) as the other two options. The dashboard's
Gmail sync pill can't tell which of the three methods produced a given sync.

Gmail access is still **read-only** — the OAuth scope requested is
`gmail.readonly`, the same guarantee as the assistant-driven workflow.

## 1. One-time setup

### a. Install the extra dependencies

These aren't needed for the base app or the assistant-driven sync — only for
this path:

```bash
pip install -r requirements.txt
```

### b. Create a Google Cloud OAuth client (for Gmail access)

1. Go to [console.cloud.google.com](https://console.cloud.google.com/) and
   create a project (or reuse one you already have).
2. **APIs & Services → Library** → search for **Gmail API** → Enable.
3. **APIs & Services → OAuth consent screen** → choose **External** (unless
   you have a Google Workspace org) → fill in the required fields (app name,
   your email) → under **Test users**, add your own Gmail address. This
   keeps the app in "Testing" mode, which is fine for personal use — you
   don't need to submit it for Google's verification.
4. **APIs & Services → Credentials → Create Credentials → OAuth client ID**
   → Application type: **Desktop app** → Create.
5. Download the resulting JSON and save it as:
   `data/gmail_api_credentials.json`
   (this file is gitignored — it's specific to your machine, never commit it)

### c. Get an Anthropic API key

1. Go to [console.anthropic.com](https://console.anthropic.com/) and create
   an API key.
2. Create `data/gmail_api_config.json` with at least:

   ```json
   {
     "anthropic_api_key": "sk-ant-...",
     "gmail_label": "Job Applications",
     "lookback_days": 30
   }
   ```

   (You can instead set the `ANTHROPIC_API_KEY` environment variable and
   omit it from the file, if you'd rather not keep it in a plaintext file.)

   Optional keys: `"model"` (defaults to a current Claude model — check
   [the model list](https://docs.claude.com/en/docs/about-claude/models) if
   the default ever starts erroring as unrecognized) and
   `"enable_web_search"` (defaults to `false`; used for the same
   location/job-URL/source enrichment step `GMAIL_SYNC.md` describes).
   It's opt-in on purpose: email content is untrusted input, and turning
   this on gives the model that reads it a live internet-search tool too —
   only enable it if you want the enrichment step and accept that trade-off.

   `data/gmail_api_config.json` is also gitignored — never commit it.

### d. First run (interactive — completes the Gmail OAuth consent)

From the project root:

```bash
python backend/gmail_api_sync.py --dry-run
```

The first run opens a browser window for you to approve read-only Gmail
access. It's cached afterward in `data/gmail_api_token.json` (also
gitignored) — every run after this one is fully unattended, no browser
needed, until/unless you revoke access in your Google account.

`--dry-run` logs everything the sync *would* do without writing anything —
review the log in `data/sync_logs/` before trusting a real run. When you're
satisfied, run it for real:

```bash
python backend/gmail_api_sync.py
```

Useful flags: `--lookback-days N` and `--label "Some Other Label"` override
the config file for a single run.

## 2. Scheduling it

Once a manual run has completed the OAuth consent, point your OS's scheduler
at the runner script instead of running it by hand every time.

### Windows: Task Scheduler

Point a scheduled task at `run_gmail_sync_api.bat`, the same way
`SETUP.md`/`README.md` describe for `run_gmail_sync_claude.bat` — every
6-8 hours is a reasonable interval. You can create this with `schtasks` or
the Task Scheduler GUI.

### macOS: launchd

1. Copy `com.jobtrace.gmailsync.plist.example` to
   `~/Library/LaunchAgents/com.jobtrace.gmailsync.plist`.
2. Replace `__PROJECT_PATH__` with this project's absolute path, and
   `__SCRIPT__` with `run_gmail_sync_api.sh`.
3. `chmod +x run_gmail_sync_api.sh` if it isn't already executable.
4. `launchctl load ~/Library/LaunchAgents/com.jobtrace.gmailsync.plist`

See the comments inside the `.plist.example` file for the unload/list
commands.

## 3. Cost expectations

Each run sends `GMAIL_SYNC.md`'s full text (a few thousand tokens) as the
system prompt, plus whatever emails it reads and the tool-call back-and-forth
for a typical sync. Check usage/cost in the Anthropic console after a couple
of runs to see what a normal sync costs for your mailbox volume before
scheduling it to run unattended every few hours.

## 4. How it stays in sync with the assistant-driven workflow

`backend/gmail_api_sync.py` reads `GMAIL_SYNC.md` from disk at runtime and
uses it as the bulk of the system prompt sent to the Anthropic API — the
classification rules, matching tiers, status-mapping table, and duplicate
protection are defined **once**, in that file, and both sync paths follow
it. If you ever edit `GMAIL_SYNC.md`'s policy, both paths pick up the change
automatically; there's no second copy of the rules to keep in sync by hand.

## 5. If this project folder is inside OneDrive, Dropbox, Google Drive, or iCloud Drive

`.gitignore` keeps `data/gmail_api_config.json`, `data/gmail_api_credentials.json`,
and `data/gmail_api_token.json` out of git (so they never reach a public
GitHub repo) — but that's a completely separate mechanism from a cloud
*file-sync* client. If this project folder lives inside a folder OneDrive,
Dropbox, Google Drive, or iCloud Drive is syncing (check whether the path
contains one of those names), those three files — your Anthropic API key,
your Gmail OAuth client secret, and a live, reusable Gmail read token — get
uploaded to that provider's servers automatically, the same as any other
file in that folder. That's true of `data/applications.db` too, for what
it's worth: this whole project's "everything stays on this computer"
promise only holds if the *folder itself* isn't inside a synced tree.

If it is, either move the whole project folder somewhere not cloud-synced,
or keep just the secret files outside it: the script honors three
environment variables that override where each file lives —

- `JOBTRACE_GMAIL_CONFIG` → replaces `data/gmail_api_config.json`
- `JOBTRACE_GMAIL_CREDENTIALS` → replaces `data/gmail_api_credentials.json`
- `JOBTRACE_GMAIL_TOKEN` → replaces `data/gmail_api_token.json`

Point them at a folder outside the synced tree (e.g. `C:\Users\you\.jobtrace\`
or `~/.jobtrace/`) *before* doing the one-time setup above, and set the same
variables in whatever runs the scheduled task so it finds them too. The
`ANTHROPIC_API_KEY` environment variable already works as an alternative to
putting the key in the config file at all.

## 6. Troubleshooting

- **"Missing data/gmail_api_credentials.json"** — you skipped step 1b, or
  saved the downloaded file under a different name/location.
- **"No Anthropic API key found"** — set it in `data/gmail_api_config.json`
  or the `ANTHROPIC_API_KEY` environment variable.
- **OAuth errors after it previously worked** — you likely revoked access in
  your Google account, or the refresh token expired from long inactivity.
  Delete `data/gmail_api_token.json` and run once interactively again.
- **Model errors ("model not found" or similar)** — set `"model"` in
  `data/gmail_api_config.json` to a current model ID from
  [the model list](https://docs.claude.com/en/docs/about-claude/models).
- Every run's full log lands in `data/sync_logs/gmail_sync_api_<timestamp>.log`
  — check there first for anything unexpected.

## Data safety

Same guarantees as the assistant-driven workflow: this script only ever
calls into `backend/repository.py` and `backend/gmail_sync.py` (no ad-hoc
SQL), never modifies Gmail, never deletes tracker data, and every write tool
independently re-checks duplicate protection before acting — a model mistake
can't create the same event or application twice.
