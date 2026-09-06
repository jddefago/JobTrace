# Gmail Synchronization — Instructions for your AI assistant

This document is written so a **new AI coding assistant session (Claude
Code, Claude Desktop, Codex CLI, or similar) — with no memory of any prior
conversation — can perform a correct, safe Gmail sync** by reading this
file alone. If you've been asked to "sync Gmail" or "check for job
application updates," read this whole document before touching anything.

## What this integration is and is not

- JobTrace (this folder) is a local Python + SQLite app. It has **no
  Gmail integration of its own** and makes **no calls to Gmail, or to
  any AI provider's API**. It only reads and writes its own local files.
- **You** (the assistant session doing the sync) are the integration. You
  read Gmail through your own Gmail connector/MCP tool, reason about what
  each email means, and write the result directly into JobTrace's local
  files using the tools described below.
- These are the rules for **one sync run**. They're identical whether the
  run is you (asked directly), the scheduler shelling out to a CLI with
  `GMAIL_SYNC_TASK_PROMPT.md`, or `backend/sync/agent.py` (which reads
  this file as its system prompt). Automatic runs only happen if the user
  turned them on in the dashboard — don't assume one is active.
- Gmail access is **read-only**. Never send, draft, forward, delete,
  archive, label, unlabel, mark read/unread, or otherwise modify anything
  in Gmail. Only search and read.

## Architecture

```
Gmail (read-only, via your Gmail connector)
   ↓
You interpret each recruitment email
   ↓
You read local application data (SQLite, via backend/repository.py)
   ↓
You match the email to an application (or decide to create one, or give up)
   ↓
You write the result locally (application + event + sync-state files)
   ↓
The HTML dashboard (unchanged) displays it next time it's opened
```

## Lessons from the first sync — read this before running again

The first manual sync (during this project's own development) initially
missed a large amount of real data. If you're a fresh assistant session
about to run this, read these first:

1. **Gmail search excludes Trash by default — always pass
   `includeTrash: true`.** In this project's own testing, a plain
   `label:"Job Applications"` search (Trash excluded, the tool default)
   silently skipped most of the labeled emails, because a large share of
   them were sitting in Trash. Many people routinely trash emails after
   reading them, so treat this as the normal case, not an edge case.
   **Every `search_threads` call in this workflow must set
   `includeTrash: true`.**

2. **The label alone is not enough — some real recruitment emails are
   never labeled at all.** In testing, some of the most important finds
   (a scheduled interview, in more than one case) had no "Job
   Applications" label whatsoever and were sitting in the inbox/Trash.
   Run two searches every time: the
   label search, and a second broader keyword sweep across the mailbox
   with the label excluded (`-label:<id>`) so you don't reprocess what
   the first search already covered. See the keyword list in the task
   prompt (`GMAIL_SYNC_TASK_PROMPT.md`) for the second search.

3. **`get_thread` can fail on trashed messages with a permission error,
   even though the message is perfectly readable.** If `get_thread`
   errors on a trashed thread, retry the same message ID with
   `get_message` instead — it works reliably where `get_thread` does
   not.

4. **LinkedIn notification emails come in different shapes — check
   which one you have before calling it unresolved:**
   - "Your application was sent to `<Company>`" / "...was viewed by
     `<Company>`" — never states the position. Unresolved.
   - "Your application to `<Position>` at `<Company>`" — states both.
     Usable directly.
   - Some LinkedIn rejection emails arrive with the visible body mostly
     stripped, but the tracking links in the footer still contain
     `application_rejected` in the URL — a legitimate signal you can use
     to classify it as a rejection even with no readable body text.

5. **The ATS/HR platform sending the email is not the employer.** Seen
   in practice: `*.myworkday.com`, `*.greenhouse-mail.io`,
   `*.teamtailor-mail.com`, `*.recruitee-mail.com`, `*.workablemail.com`,
   `*.icims.com`, `*.successfactors.eu`, `*.hibob.com`,
   `beapplied-email.com`. The real employer is usually named in the body
   or signature — occasionally it's only inferable from a subdomain
   (e.g. `<company>.teamtailor-mail.com` where the body never names the
   company by name, only the subdomain hints at it). If genuinely
   unclear, search the sender's domain for other messages that do name
   the company.

6. **A rejection followed much later by a fresh confirmation for the
   same requisition ID is a reapplication, not a data conflict.** Keep
   both events on the timeline in order; current stage/outcome should
   reflect whichever event is more recent (a later confirmation
   un-rejects it back to Applied/Pending). Add a short note on the
   application explaining the reapplication.

7. **The same status update sometimes arrives as two near-simultaneous,
   separate messages** (an assessment invite from both the employer's
   ATS and the assessment vendor within a minute of each other;
   duplicate confirmation emails from two systems at once). These are
   genuinely different Gmail messages, so log an event for each — but
   only change stage/outcome once per actual status change, not once
   per email.

8. **Multiple independent applications at the same company are common,
   not the exception** — plenty of people apply to several roles at one
   employer over time. Never collapse same-company emails together
   without confirming the position matches.

9. **Non-ASCII characters (®, em dashes, accented names) can get
   corrupted through some Windows console/subprocess pipelines.** Prefer
   plain ASCII in event descriptions and notes when the special
   character isn't essential, and spot-check what actually landed in
   the JSON/DB after a write rather than assuming it round-tripped
   cleanly.

10. **You do not need to stop the local JobTrace server before writing.**
    The database runs in WAL mode specifically so a background sync and
    the running dashboard can read/write safely at the same time. Don't
    kill the user's server process as part of this task.

11. **Reconcile the unresolved queue before adding to it.** The user can
    (and does) resolve an unresolved item themselves by adding the
    application by hand through the UI, without telling you. Before
    re-flagging something as unresolved, check whether a matching
    application already exists (by company, and position if now
    knowable); if so, remove the stale entry with
    `sync_state.remove_unresolved_item` instead of leaving a duplicate
    signal sitting there.

If the user files recruitment emails under a specific Gmail label (many
people use something like "Job Applications" or "Jobs"), ask them which
one, or call `list_labels` and look for a plausible candidate. Use
`label:<id>` in `search_threads` queries to scope your search to that
label rather than the whole mailbox. If there's no such label, skip
straight to the broader keyword sweep (Pass B in the task prompt).

## Files you should read

| File | Purpose |
|---|---|
| `data/applications.db` | The SQLite database — the actual tracker data. Read via `backend/repository.py`, never with raw SQL you write yourself (see "How to make changes" below). |
| `data/gmail_sync_state.json` | Which Gmail messages have already been processed, and the result of the last sync. **Read this before doing anything else.** |
| `data/unresolved_gmail_items.json` | Emails from previous syncs that couldn't be confidently matched. Check these first — a new email in the same thread may resolve an old ambiguity. |
| `backend/constants.py` | The exact allowed values for stage, outcome, and event types. Never write a stage/outcome/event_type value that isn't in this file. |

## Files you may modify

- `data/applications.db` — only through `backend/repository.py` functions (see below), never by editing the file directly or writing raw SQL from a separate connection while the app might be running.
- `data/gmail_sync_state.json` — through `backend/sync/state.py` functions.
- `data/unresolved_gmail_items.json` — through `backend/sync/state.py` functions.

**Never modify:** `backend/*.py` source files, `frontend/*`, `data/applications.db`'s schema, or anything outside the two JSON files and the applications/events rows themselves. If you think a schema or code change is genuinely needed, stop and ask the user — don't improvise it mid-sync.

## How to make changes (do not write ad-hoc SQL)

Run Python from the project root with the project root on `sys.path`, and
use the existing repository functions — they already handle validation,
transactions, and the auto-generated timeline events for you:

```python
import sys
sys.path.insert(0, r"<PATH_TO_THIS_PROJECT_FOLDER>")  # e.g. the folder this file is in — use its absolute path
from backend import repository as repo
from backend.sync import state as sync_state

# Load sync state FIRST, always.
state = sync_state.load_sync_state()

# --- Duplicate check (see "Duplicate protection" below) ---
if sync_state.is_message_processed(state, message_id):
    ...  # skip this message entirely, do not re-derive anything from it

# --- Finding an existing application ---
app = repo.find_matching_application(company="Acme Corp", position="Software Engineer")
# Returns the most recent exact (case-insensitive) company+position match, or None.
# For fuzzier matching (tiers 4-7 below), use:
candidates = repo.list_applications(company="Acme Corp")  # partial company match, summary rows only
# then use get_application(id) on plausible candidates to inspect details/events yourself.

# --- Creating a new application (only for clear confirmation emails) ---
new_app = repo.create_application(
    {
        "company": "Acme Corp",
        "position": "Software Engineer",
        "location": "",              # blank if unknown, never invent one
        "application_date": "2026-08-20",  # confirmation email date unless a more accurate date is stated
        "source": "Unknown",         # only infer if reasonably clear from the email
        "job_url": "",
        "job_description": "",
        "notes": "",
        "current_stage": "Applied",
        "outcome": "Pending",
    },
    client_request_id=f"gmail-create-{message_id}",  # makes creation idempotent for free
)
# This also auto-creates a generic "Application Submitted" event.
# Separately add the Gmail-specific confirmation event (see below).

# --- Updating stage/outcome (auto-creates "Stage Update"/"Outcome Update" events) ---
repo.update_application_stage(app["id"], stage="Assessment", outcome="Positive")

# --- Adding a Gmail-sourced event (always do this for anything Gmail touched) ---
repo.add_event(
    application_id=app["id"],
    event_type="Assessment Invitation",   # see mapping table below
    event_date="2026-08-24",              # the email's date, not today's date
    description="Online assessment invitation received via email.",
    source="Gmail",
    gmail_message_id=message_id,          # critical for traceability + duplicate protection
)

# --- Mark the message processed and save state (do this for EVERY message you touch,
#     including ones you decide to ignore) ---
sync_state.mark_message_processed(state, message_id)
sync_state.save_sync_state(state)
```

At the very end of the whole sync run, also call:

```python
sync_state.set_connected_account(state, "<the Gmail address you read from>")
sync_state.record_sync_result(state, {
    "emailsReviewed": ...,
    "recruitmentRelated": ...,
    "applicationsCreated": ...,
    "applicationsUpdated": ...,
    "rejectionsDetected": ...,
    "assessmentsDetected": ...,
    "interviewsDetected": ...,
    "offersDetected": ...,
    "emailsIgnored": ...,
})
sync_state.save_sync_state(state)
```

This stamps `lastSuccessfulSync` and is what the dashboard's Gmail pill
reads. `set_connected_account` records which inbox you actually read (find
your own address from a `label:sent` message's `From:` header) so the user
can spot a sync that ran against the wrong account. Only call these once,
after the whole batch is done — not per email.

## Duplicate protection (critical)

Before using a Gmail message to create an application, change a stage or
outcome, or create an event:

1. Check `sync_state.is_message_processed(state, message_id)`. If `True`,
   **skip this message entirely** — do not re-derive anything from it,
   even if you think the result would be the same.
2. `backend/repository.py::has_processed_gmail_message(message_id)` is a
   second, database-level check (has any event already been stamped with
   this message ID). Treat a `True` result the same way — skip.
3. After successfully acting on a message (or deciding to ignore it),
   call `sync_state.mark_message_processed(state, message_id)` and save
   state before moving to the next message. Don't batch this at the end —
   if the sync is interrupted partway through, already-processed messages
   must not be reprocessed on the next run.
4. **Never remove IDs from `processedMessageIds`** to "clean up" the
   list. It only grows.

Running the same sync twice must leave the tracker in exactly the same
state after the second run as after the first (idempotency). This is the
single most important property of this workflow — when in doubt, be more
conservative, not less.

## Application matching rules

Apply these tiers **in order** and stop at the first one that gives a
confident match. Never match on company name alone — the user may have
multiple applications at the same company (e.g. "Deloitte — Business
Analyst" and "Deloitte — Strategy Analyst" are different applications and
must never be merged).

1. **Explicit job/requisition ID** — if the email and an existing
   application both reference the same req/job ID (sometimes in the
   subject, a URL, or the body), that's a confident match regardless of
   title wording.
2. **Existing Gmail thread relationship** — if this message is a reply
   within a thread where an earlier message in that same thread was
   already matched to an application (check past events for a
   `gmail_message_id` from the same `threadId`), match the same
   application.
3. **Exact company + exact position** (case-insensitive) — use
   `repo.find_matching_application(company, position)`.
4. **Company + very close position title** — e.g. "Backend Engineer" vs
   "Backend Software Engineer" for the same company. Use your judgment;
   this is why you're doing this instead of a fuzzy-string algorithm.
5. **Sender domain + position** — e.g. mail from `@greenhouse.io` or the
   company's own domain, combined with a position title that clearly
   matches one existing application at that company.
6. **Company + recruitment context** — weaker signal, only when there's
   exactly one plausible application at that company and nothing about
   the email contradicts it.
7. **Other contextual evidence** — last resort. If you're still not
   confident, do not guess.

If more than one existing application is plausible and you can't
confidently pick one, or if none reach a confident match and it's not
clearly a fresh application confirmation (see below), **do not modify
the tracker**. Record it as an unresolved item instead.

## Creating new applications from confirmation emails

If an email is clearly an application confirmation (e.g. "Thank you for
applying for the Business Analyst position at Example Company") and no
matching application exists locally, you may create one:

- `company` / `position` — only if both can be determined with reasonable
  confidence from the email. If either is unclear, do **not** create a
  malformed application — record it as unresolved instead.
- `application_date` — the confirmation email's date, unless the email
  explicitly states a different, more accurate application date.
- `current_stage` — `"Applied"`, `outcome` — `"Pending"`.
- `source` — infer only when reasonably clear (e.g. "via LinkedIn" in the
  body); otherwise `"Unknown"`.
- Also add an `"Application Confirmation"` event with `source="Gmail"`
  and the message's `gmail_message_id`.

## Enriching location, job URL, and source via web search

The confirmation email itself rarely states the exact location, the direct
job posting URL, or a clean "source" (LinkedIn vs. the company's own site vs.
a job board). After you create or update an application in this sync, if
`location`, `job_url`, or `source` is still empty or `"Unknown"`, use your
web search tool to try to find the original posting and fill in what you
confidently find:

- Search on company + position (e.g. `"<Position>" "<Company>" job
  posting`), optionally narrowed with `site:linkedin.com/jobs`,
  `site:<company-domain>`, or the specific ATS named in the email
  (Greenhouse, Workday, Lever, etc.).
- **`source`** — classify from the domain of whatever posting you find:
  `linkedin.com` → `"LinkedIn"`; the company's own domain or its ATS
  subdomain (e.g. `boards.greenhouse.io/<company>`,
  `<company>.wd1.myworkdayjobs.com`) → `"Company Website"`; `indeed.com` →
  `"Indeed"`; `glassdoor.com` → `"Glassdoor"`; anything else → that site's
  name, or `"Other"` if nothing fits.
- **`job_url`** — the direct link to the specific posting, only if you're
  confident it's the same role (company + position match, and ideally
  location/date consistent with the application). Prefer the original
  listing over a search-results page. Never invent or guess a URL.
- **`location`** — as written on the posting (city/country as stated
  there — don't normalize, translate, or guess).
- Write with `repo.update_application(app_id, {...})`, including only the
  fields you actually found. Never overwrite a field that already holds a
  real (non-empty, non-`"Unknown"`) value with a guess — this is
  enrichment for missing data, not a correction pass.
- Many postings for older or already-closed applications won't be findable
  any more. That's expected — leave the field as-is rather than guessing
  or leaving a placeholder.
- This is metadata enrichment, not a status change, so it doesn't need its
  own timeline event — but mention in your end-of-sync report which
  applications you filled in details for.

## Status mapping rules

Stage values must come from `backend/constants.py::STAGE_PROGRESSION`
(`Applied`, `Screening`, `Assessment`, `Interview 1`, `Interview 2`,
`Final Interview`, `Offer`) or the terminal stage `Closed`. Outcome values
must come from `OUTCOMES` (`Pending`, `Positive`, `Negative`, `Accepted`,
`Withdrawn`).

| Email classification | Stage | Outcome | Event type | Notes |
|---|---|---|---|---|
| APPLICATION_CONFIRMATION | Applied | Pending | Application Confirmation | Only if stage isn't already further along |
| RECRUITER_CONTACT | *(unchanged)* | *(unchanged)* | Recruiter Contact | Log only, no stage/outcome change |
| SCREENING_INVITATION | Screening | Positive | Screening | |
| ASSESSMENT_INVITATION | Assessment | Positive | Assessment Invitation | |
| ASSESSMENT_REMINDER | *(unchanged)* | *(unchanged)* | Other (description: "Assessment reminder") | Do not re-create the Assessment stage if already there |
| INTERVIEW_INVITATION | Interview 1 / Interview 2 / Final Interview | Positive | Interview Invitation | Pick the round the email actually indicates — never assume "Interview 1" if the email clearly says otherwise (e.g. "second round", "final round") |
| INTERVIEW_RESCHEDULE | *(unchanged)* | *(unchanged)* | Other (description: "Interview rescheduled") | |
| NEXT_ROUND | next stage per context | Positive | Next Round | |
| OFFER | Offer | Positive | Offer | |
| REJECTION | Closed | Negative | Rejection | |
| APPLICATION_WITHDRAWN | Closed | Withdrawn | Withdrawal | Only if the email is from the user's own side withdrawing, not a rejection |
| APPLICATION_STILL_UNDER_REVIEW | *(unchanged)* | *(unchanged)* | Other (description: "Still under review") | Never mark Positive or Negative for this |
| GENERAL_RECRUITMENT_UPDATE | *(unchanged, unless unambiguous)* | *(unchanged, unless unambiguous)* | Other | Conservative default |
| IRRELEVANT | — | — | — | No event. Count in `emailsIgnored`. Still mark the message ID processed. |

**When uncertain, prefer no automatic status change over an incorrect
one.** Always add an event to record what the email said, even when you
don't change stage/outcome — the event itself is valuable history, and
`update_application_stage` only fires its own event when stage or outcome
actually changes, so a same-stage email needs its event added via
`add_event` directly.

Be conservative about what counts as "recruitment-related" in the first
place. Ignore (classify IRRELEVANT, don't create events, don't create
applications):
- Recruiter marketing / cold outreach with no application behind it
- Job alert digests, "jobs you may be interested in"
- LinkedIn recommended-jobs notifications
- Generic newsletters
- Unrelated networking messages

## Unresolved items

When you can't confidently match or classify something, call:

```python
unresolved = sync_state.load_unresolved()
sync_state.add_unresolved_item(unresolved, {
    "gmailMessageId": message_id,
    "emailDate": "2026-08-24",
    "sender": "recruiting@example.com",
    "subject": "Update on your application",
    "possibleCompany": "Example Corp",       # best guess, or None
    "possiblePosition": "Business Analyst",  # best guess, or None
    "possibleEventType": "GENERAL_RECRUITMENT_UPDATE",
    "reason": "Two existing applications at Example Corp; email doesn't specify which role.",
    "candidateApplicationIds": [12, 15],
    "body": message_body,                    # the plain-text email body
})
sync_state.save_unresolved(unresolved)
```

Include the plain-text `body` you already fetched — the dashboard shows it
so the user can read what the email was about and then turn it into (or
attach it to) an application in one click. It's truncated to ~16k
characters on write, so just pass the body as-is. Still mark the message
as processed (you *reviewed* it; you just didn't act on it) so it isn't
re-flagged as unresolved on every future sync — unless you expect a later
sync with more context to be able to resolve it, in which case use your
judgment about whether marking it processed is appropriate.

The dashboard shows a live count of unresolved items and lists them (via
`GET /api/gmail/unresolved`, read-only). The user can open the email,
create or update an application from it, or discard it — all from the
dashboard — or ask you to reconcile it in a future session with more
context.

## Data safety

- Before any schema migration, `backend/database.py` automatically backs
  up the database to `backups/pre_gmail_integration_<timestamp>.db`. You
  don't need to do this yourself for normal sync runs — it only fires the
  first time the new schema is needed. If you're ever about to do
  something unusually risky (bulk edits, re-matching many applications),
  make your own backup first with `repo.backup_database()`.
- Never delete applications, events, notes, job descriptions, or URLs as
  part of a sync. This workflow only creates applications/events or
  updates stage/outcome — it never deletes anything.
- Use the existing validation (`backend/validation.py`, enforced
  automatically by every `repository.py` function) — never bypass it with
  raw SQL.
- If something looks structurally wrong (e.g. `backend/constants.py`
  doesn't have a stage value you expected), stop and tell the user rather
  than working around it.

## Running a sync, end to end

1. Read `data/gmail_sync_state.json` and `data/unresolved_gmail_items.json`.
2. Resolve the "Job Applications" Gmail label to its ID via `list_labels`.
3. Search Gmail scoped to that label (and/or recent recruitment-signal
   keywords — see the skill/task prompt for the current run) using
   `search_threads`. Prefer recent messages over the entire mailbox
   unless explicitly asked to backfill further.
4. For each thread/message, in order:
   a. Skip if `sync_state.is_message_processed` is already `True`.
   b. Read the full message (`get_thread` / `get_message`, `PLAIN_TEXT`
      format to save context).
   c. Classify it (see table above).
   d. If IRRELEVANT: mark processed, count as ignored, continue.
   e. Otherwise, find or create the matching application (see matching
      rules). If ambiguous/unmatched, record as unresolved, mark
      processed, continue.
   f. Apply the stage/outcome mapping and add the Gmail-sourced event.
   g. If you created or touched this application and it's still missing
      location, job_url, or source, try to enrich it via web search (see
      "Enriching location, job URL, and source via web search" above).
   h. Mark the message processed and save state immediately.
5. After the loop, call `sync_state.record_sync_result(...)` and save
   state once more.
6. Report a summary to the user (see the sync report format used in the
   original setup conversation, or just: reviewed / recruitment-related /
   created / updated / rejections / assessments / interviews / offers /
   ignored / unresolved).
7. Suggest the user open the dashboard to review the Gmail sync pill (top
   right) and the "Unresolved items" list if any exist.

This document is the sync *policy*, not a setup task. If the user wants
automatic sync, don't build your own scheduler or cron job — point them at
the dashboard's Gmail sync settings (see SETUP.md), which already does it.
