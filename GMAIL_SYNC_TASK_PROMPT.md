Synchronize my Gmail recruitment correspondence with my local JobTrace application tracker.

You have access to:

1. My connected Gmail account.
2. The local JobTrace project folder (this folder — wherever you've placed it on your own computer).
3. The instructions in `GMAIL_SYNC.md` — **read this in full before doing anything else.** It has a "Lessons from the first sync" section near the top that documents mistakes already made once; do not repeat them.
4. The application's local data files (`data/applications.db`, `data/gmail_sync_state.json`, `data/unresolved_gmail_items.json`).

Your job is to inspect relevant recruitment emails, determine what happened with each application, and safely update JobTrace.

## Important

This is a read-only Gmail task. You may search and read Gmail, but do NOT:

- send emails
- create drafts
- delete emails
- archive emails
- change labels
- mark messages read/unread
- unsubscribe from anything
- modify Gmail in any way

Only modify the local JobTrace files, and only through `backend/repository.py` and `backend/gmail_sync.py` functions — never with hand-written SQL or by editing JSON files directly. You do not need to stop the local server before writing; the database runs in WAL mode specifically so a background sync and the running dashboard can coexist safely.

## 1. Read JobTrace before touching Gmail

First:

1. Read `GMAIL_SYNC.md` in full, including the lessons section.
2. Read the current application data.
3. Read `data/gmail_sync_state.json`.
4. Read `data/unresolved_gmail_items.json`.
5. Understand the current stages, outcomes, application IDs, and event structure.

Do not modify anything yet.

Determine the timestamp of `lastSuccessfulSync`.

**If a previous successful sync exists:** only investigate emails received after that timestamp, with a ~24 hour overlap to avoid missing delayed or threaded correspondence. Regardless of the window, use Gmail message IDs to ensure previously processed emails are never processed twice — check both `gmail_sync.is_message_processed` (the JSON state file) and `repository.has_processed_gmail_message` (a second, database-level check) before acting on any message.

**If there has never been a successful sync:** inspect recruitment-related emails from the last 30 days. Do not indiscriminately read the entire mailbox.

**Before searching, reconcile the unresolved queue:** for each item already in `data/unresolved_gmail_items.json`, check whether a matching application now exists in JobTrace (the user sometimes resolves these manually through the UI without telling you). If a match exists, remove the stale unresolved entry with `gmail_sync.remove_unresolved_item` instead of leaving a duplicate signal sitting there.

## 2. Search Gmail — two passes, not one

**Gmail excludes Trash from search results by default. Every `search_threads` call below must explicitly set `includeTrash: true`.** In the first sync, this single default cost 76% of the relevant emails — the user routinely trashes messages after reading them, so this is the normal case here, not an edge case.

Run **two separate searches**, because the label alone is not reliable — some real recruitment emails (including two scheduled interviews in the first sync) were never labeled at all:

**Pass A — the label.** Use `list_labels` to resolve "Job Applications" to its label ID, then search `label:"Job Applications"` (the display name in quotes works directly) with `includeTrash: true`, scoped to your date window. Page through with `nextPageToken` until it's absent — don't trust `resultCountEstimate` as an exact count, it's known to be approximate and can shift between pages.

**Pass B — a broader keyword sweep,** scoped to the same date window, with `includeTrash: true` and `-label:"Job Applications"` (so you don't reprocess what Pass A already found). Useful signals include, but are not limited to:

application received · application submitted · thank you for applying · thank you for your application · your application · application update · recruitment process · selection process · next step · next stage · assessment · online assessment · case study · screening · recruiter · interview · interview invitation · meeting invitation · final round · unfortunately · regret to inform · after careful consideration · decided not to proceed · pleased to inform · congratulations · offer · employment offer

Also watch for known ATS/recruitment-platform senders: `*.myworkday.com`, `*.greenhouse-mail.io`, `*.teamtailor-mail.com`, `*.recruitee-mail.com`, `*.workablemail.com`, `*.icims.com`, `*.successfactors.eu`, `*.hibob.com`, `beapplied-email.com`, and similar. **The sending domain is not the employer** — the real company name is usually in the body or signature, sometimes only inferable from a subdomain.

Do NOT rely only on keywords — interpret the actual context of the message. Ignore:

- LinkedIn job recommendations / "apply now" alerts (as opposed to LinkedIn's own application-status notifications, which are real signals — see the classification notes below)
- Indeed job alerts, newsletters, career marketing emails, generic employer advertising
- networking messages unrelated to an active application
- recruiter cold outreach that doesn't correspond to an application
- promotional emails

## 3. Process only unprocessed Gmail messages

Before using any email, check its Gmail message ID against both `gmail_sync.is_message_processed` and `repository.has_processed_gmail_message`. If it's already there, skip it entirely — a previously processed email must never create another application, create another event, or change a stage/outcome again.

The synchronization must be idempotent: running this task twice over the same emails must leave JobTrace unchanged the second time.

## 4. Classify each relevant email

For every relevant, unprocessed recruitment email, determine:

**Company** — the actual employer, not the ATS platform (see the domain list above).

**Position** — as precisely as possible. Preserve meaningful distinctions between jobs at the same company (e.g. "Business Analyst Graduate Programme" and "Strategy Analyst Graduate Programme" are different applications, never the same one).

**LinkedIn notification sub-type**, if the sender is `jobs-noreply@linkedin.com`:
- "Your application was sent to `<Company>`" / "...was viewed by `<Company>`" → no position stated, this alone is not enough to create or match an application. Route to unresolved.
- "Your application to `<Position>` at `<Company>`" → states both, usable directly.
- If the visible body is stripped/empty but the footer tracking links contain `application_rejected`, treat it as a rejection even without readable body text.

**Recruitment event**, one of:

- APPLICATION_CONFIRMATION
- RECRUITER_CONTACT
- SCREENING_INVITATION
- ASSESSMENT_INVITATION
- ASSESSMENT_REMINDER
- INTERVIEW_INVITATION
- INTERVIEW_RESCHEDULE
- NEXT_ROUND
- FINAL_ROUND
- OFFER
- REJECTION
- APPLICATION_STILL_UNDER_REVIEW
- WITHDRAWAL
- GENERAL_RECRUITMENT_UPDATE
- IRRELEVANT

Map these to JobTrace's actual event-type values (`Application Confirmation`, `Recruiter Contact`, `Screening`, `Assessment Invitation`, `Assessment Completed`, `Interview Invitation`, `Interview Completed`, `Next Round`, `Offer`, `Rejection`, `Withdrawal`, `Other`) — use `Other` with a clear description for anything that doesn't map cleanly (e.g. ASSESSMENT_REMINDER, INTERVIEW_RESCHEDULE, APPLICATION_STILL_UNDER_REVIEW when no stage change applies).

## 5. Match the email to an application

Before changing anything, attempt to identify the correct existing application. Use evidence in roughly this order:

1. Exact job/requisition ID.
2. Existing Gmail thread already associated with an application (check past events for a `gmail_message_id` from the same `threadId`).
3. Exact company + exact position (`repository.find_matching_application`).
4. Company + extremely close position title.
5. Recruiter/ATS sender + identifiable position.
6. Other strong contextual evidence.

Do NOT match on company alone — many people have multiple independent applications at the same employer over time. Do NOT guess when two or more applications are plausible. If not sufficiently confident, route to the unresolved queue rather than modifying an application.

## 6. Create missing applications from confirmation emails

If an email clearly confirms an application was submitted and no corresponding JobTrace application exists, create it. Extract what's reliably available: company, position, application date, location, source (only if reasonably clear — otherwise `"Unknown"`), requisition/job ID if present.

Set stage `Applied`, outcome `Pending`, and add an `Application Confirmation` event using `client_request_id=f"gmail-create-{message_id}"` on the create call for idempotency. Use the email date as the application date unless a more accurate date is explicitly stated. If the company or position can't be reliably determined, route to unresolved instead of inventing anything.

## 7. Enrich location, job URL, and source via web search

For every application you create or touch in this sync where `location`, `job_url`, or `source` is still empty or `"Unknown"`, use your web search tool to try to find the original job posting and fill in what you can:

- Search on company + position (e.g. `"<Position>" "<Company>" job posting`), optionally narrowed with `site:linkedin.com/jobs`, `site:<company-domain>`, or the specific ATS the confirmation email came from (Greenhouse, Workday, Lever, etc.).
- **`source`** — classify from the domain of whatever posting you find: `linkedin.com` → `"LinkedIn"`; the company's own domain or its ATS subdomain (e.g. `boards.greenhouse.io/<company>`, `<company>.wd1.myworkdayjobs.com`) → `"Company Website"`; `indeed.com` → `"Indeed"`; `glassdoor.com` → `"Glassdoor"`; anything else → that site's name, or `"Other"` if nothing fits.
- **`job_url`** — the direct link to the specific posting, only if you're confident it's the same role (company + position match, ideally location/date consistent with the application). Prefer the original listing over a search-results page. Never invent or guess a URL.
- **`location`** — as written on the posting (city/country as stated there — don't normalize, translate, or guess).
- Write via `repo.update_application(app_id, {...})`, including only the fields you actually found. Never overwrite a field that already holds a real (non-empty, non-`"Unknown"`) value with a guess — this is enrichment for missing data, not a correction pass.
- Older or already-closed postings often won't be findable any more — that's expected. Leave the field as-is rather than guessing or leaving a placeholder.
- This is metadata enrichment, not a status change, so it doesn't need its own timeline event — but list which applications you filled in details for in your final report (step 14).

## 8. Update stages conservatively

- **Application confirmation** → Applied / Pending.
- **Screening invitation** → Screening / Positive.
- **Assessment invitation** → Assessment / Positive.
- **Assessment reminder** → don't advance the stage if already at Assessment; only add an event if it contains meaningful new information (e.g. a deadline).
- **Interview invitation** → move to Interview 1, Interview 2, or Final Interview based on context; if you can't determine the round but know it's the first interview, use Interview 1. Don't advance a stage just because an interview is being rescheduled — that's a `Other`/informational event on the current stage.
- **Next round / final round** → advance only when the email clearly confirms progression.
- **Offer** → Offer / Positive.
- **Rejection** → Closed / Negative.
- **Withdrawal** (the user's own choice to withdraw, not a rejection) → Closed / Withdrawn.
- **Still under review** → do not mark Positive or Negative, do not change the stage unless the email explicitly says so; add an informational event only.
- **Two near-simultaneous emails about the same status** (e.g. an assessment invite from both the employer's ATS and the assessment vendor within a minute of each other) are genuinely separate Gmail messages — log an event for each, but only change stage/outcome once per actual status change, not once per email.

When uncertain, prefer no automatic status change over an incorrect one.

## 9. Preserve the full application history

Whenever an email causes a meaningful update, create an event via `repository.add_event`, always with `source="Gmail"` and `gmail_message_id=<id>`. Keep descriptions short and factual — store the minimum needed to understand what happened, not a copy of the email. Examples: "Assessment invitation received.", "Invited to first-round interview.", "Application rejected by employer.", "Application progressed to final interview."

## 10. Never move an application backwards accidentally

Stages represent progression. If an application is already at Interview 1 and you find an older assessment email (already processed or newly discovered but dated earlier), do not move it back to Assessment. Final Interview must not be replaced by Interview 1 because an older email surfaced. Use event dates and the current tracker state together — historical emails can be added to the timeline without overwriting the current stage.

**Exception — reapplication.** A rejection followed much later by a *fresh* confirmation for the same requisition ID is a genuine reapplication, not noise to ignore. Keep both events on the timeline in order, let the current stage/outcome reflect whichever event is more recent (so a later confirmation correctly un-rejects it back to Applied/Pending), and add a short note on the application explaining what happened. This is different from "moving backwards" — it's the real sequence of events.

## 11. Handle conflicting information carefully

If Gmail appears to contradict JobTrace, don't immediately overwrite — check the relevant thread and the application's existing timeline first. If JobTrace says Interview 1 and a new, more recent email is clearly a rejection, updating to Closed/Negative is correct. If the contradictory information is from an older email than what's already reflected, preserve the newer state instead (see the reapplication exception above for the one case where an older-vs-newer conflict should still update the current state).

## 12. Record unresolved items

If you cannot confidently determine the company, the position, which application an email belongs to, or whether an email actually changes anything — do not guess. Add it via `gmail_sync.add_unresolved_item` with: Gmail message ID, email date, sender, subject, likely company, likely position, likely event type, candidate application IDs if any, and a clear reason. Don't store the full email body — enough context for the user to look it up later is sufficient.

## 13. Update synchronization state

Only after the sync completes successfully: call `gmail_sync.record_sync_result` with the run's counters (emails reviewed, recruitment-related, applications created, applications updated, rejections/assessments/interviews/offers detected, ignored, unresolved), then `gmail_sync.save_sync_state`. This stamps `lastSuccessfulSync` and is what the dashboard's Gmail pill reads.

**Do not update `lastSuccessfulSync` if the process fails or is interrupted before completing** — mark each message processed as you go (not batched at the end) so a partial run doesn't lose its place, but only call `record_sync_result` at the very end of a fully completed run.

## 14. Verify JobTrace after making changes

After modifying the tracker:

1. Confirm no duplicate applications were created (same company + same position).
2. Confirm no duplicate events were created for the same Gmail message ID.
3. Confirm existing application IDs, job descriptions, URLs, and notes are untouched for applications you didn't need to change.
4. Confirm summary stats and analytics still compute without errors (`GET /api/stats/summary`, `GET /api/stats/analytics`).
5. Confirm every stage/outcome value used is a valid one from `backend/constants.py`.
6. Confirm `data/gmail_sync_state.json` and `data/unresolved_gmail_items.json` are valid JSON.

Do not redesign the JobTrace interface or touch any file outside the local data files during this task — this is a data synchronization task only.

## 15. Give me a concise report

When finished, tell me:

**Gmail Sync Complete**

Then report:

- Emails reviewed
- Recruitment emails found
- New applications created
- Existing applications updated
- Rejections
- Assessments
- Interviews
- Offers
- Ignored emails
- Unresolved items
- Applications enriched via web search (location/URL/source filled in)

Then list the applications that changed, in a compact format such as:

```
KLM — Management Trainee → Assessment
Deloitte — Business Analyst → Rejected
JDE Peet's — Graduate Programme → New application detected
```

Finally, list any unresolved items that need my attention. Do not show me or reproduce private email content unless it's necessary to explain an unresolved classification.
