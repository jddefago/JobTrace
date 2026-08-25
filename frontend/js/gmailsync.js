/* Gmail sync status indicator + detail modal.

   This is a read-only display. The actual Gmail synchronization is
   performed by a Claude Desktop/Cowork session (see GMAIL_SYNC.md), which
   reads Gmail through its own connector and writes directly to this app's
   SQLite database and data/gmail_sync_state.json. This page never talks
   to Gmail and has no "Sync now" button, because a button here cannot
   actually invoke Claude. */

const GmailSync = (() => {
  function formatSyncDate(iso) {
    if (!iso) return null;
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
  }

  function updatePill(status) {
    const textEl = document.getElementById("gmail-status-text");
    const btn = document.getElementById("gmail-status-btn");
    const iconEl = document.getElementById("gmail-status-icon");
    iconEl.innerHTML = Icons.mail;

    if (!status.lastSuccessfulSync) {
      textEl.textContent = "Gmail not synced yet";
      btn.classList.remove("has-unresolved");
      return;
    }

    const r = status.lastSyncResult || {};
    const parts = [];
    if (r.applicationsCreated) parts.push(`${r.applicationsCreated} new`);
    if (r.applicationsUpdated) parts.push(`${r.applicationsUpdated} updated`);
    if (!parts.length) parts.push(`${r.emailsReviewed || 0} reviewed`);
    textEl.textContent = `Gmail: ${formatSyncDate(status.lastSuccessfulSync)} · ${parts.join(" · ")}`;
    btn.classList.toggle("has-unresolved", status.unresolvedCount > 0);
  }

  function statRow(label, value) {
    return Utils.el("div", { class: "gmail-stat-row" }, [
      Utils.el("span", { class: "gmail-stat-label" }, label),
      Utils.el("span", { class: "gmail-stat-value" }, String(value ?? 0)),
    ]);
  }

  async function renderModal() {
    const body = document.getElementById("gmail-sync-body");
    body.innerHTML = "";
    body.appendChild(Utils.el("div", { class: "empty-state" }, "Loading…"));

    let status, unresolved;
    try {
      [status, unresolved] = await Promise.all([Api.getGmailSyncStatus(), Api.getGmailUnresolved()]);
    } catch (err) {
      body.innerHTML = "";
      body.appendChild(Utils.el("div", { class: "empty-state" }, err.message));
      return;
    }

    body.innerHTML = "";

    body.appendChild(
      Utils.el("div", { class: "gmail-last-sync" },
        status.lastSuccessfulSync
          ? `Last sync: ${formatSyncDate(status.lastSuccessfulSync)}`
          : "Gmail not synced yet"
      )
    );

    const r = status.lastSyncResult || {};
    body.appendChild(
      Utils.el("div", { class: "gmail-stats-grid" }, [
        statRow("Emails reviewed", r.emailsReviewed),
        statRow("Recruitment-related", r.recruitmentRelated),
        statRow("Applications created", r.applicationsCreated),
        statRow("Applications updated", r.applicationsUpdated),
        statRow("Rejections detected", r.rejectionsDetected),
        statRow("Assessments detected", r.assessmentsDetected),
        statRow("Interviews detected", r.interviewsDetected),
        statRow("Offers detected", r.offersDetected),
        statRow("Ignored", r.emailsIgnored),
        statRow("Unresolved", status.unresolvedCount),
      ])
    );

    body.appendChild(
      Utils.el("div", { class: "detail-section-header" }, [Utils.el("h4", {}, "Unresolved items")])
    );

    if (!unresolved.items || unresolved.items.length === 0) {
      body.appendChild(Utils.el("div", { class: "empty-state" }, "No unresolved items."));
    } else {
      const list = Utils.el("div", { class: "gmail-unresolved-list" });
      for (const item of unresolved.items) {
        list.appendChild(
          Utils.el("div", { class: "gmail-unresolved-item" }, [
            Utils.el("div", { class: "gmail-unresolved-top" }, [
              Utils.el("span", { class: "gmail-unresolved-subject" }, item.subject || "(no subject)"),
              Utils.el("span", { class: "gmail-unresolved-date" }, item.emailDate || ""),
            ]),
            Utils.el("div", { class: "gmail-unresolved-meta" }, `${item.sender || "Unknown sender"}${item.possibleCompany ? ` · ${item.possibleCompany}` : ""}${item.possiblePosition ? ` — ${item.possiblePosition}` : ""}`),
            Utils.el("div", { class: "gmail-unresolved-reason" }, item.reason || ""),
          ])
        );
      }
      body.appendChild(list);
    }

    body.appendChild(
      Utils.el("p", { class: "gmail-sync-note" },
        "Gmail sync runs from Claude Desktop/Cowork, not from this page. Ask Claude to review your Gmail to update this."
      )
    );
  }

  async function loadStatus() {
    try {
      const status = await Api.getGmailSyncStatus();
      updatePill(status);
    } catch (err) {
      /* non-critical for page load */
    }
  }

  function bindEvents() {
    document.getElementById("gmail-status-btn").addEventListener("click", () => {
      Utils.openOverlay("gmail-sync-overlay");
      renderModal();
    });
    document.getElementById("gmail-sync-close").addEventListener("click", () => Utils.closeOverlay("gmail-sync-overlay"));
    document.getElementById("gmail-sync-ok").addEventListener("click", () => Utils.closeOverlay("gmail-sync-overlay"));
    document.getElementById("gmail-sync-overlay").addEventListener("click", (e) => {
      if (e.target.id === "gmail-sync-overlay") Utils.closeOverlay("gmail-sync-overlay");
    });
  }

  function init() {
    bindEvents();
    loadStatus();
  }

  return { init };
})();
