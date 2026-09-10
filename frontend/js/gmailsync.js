/* Gmail sync: status pill + a modal that both shows the last sync and,
   under "Settings", configures how sync runs.

   Three choices in Settings, each deciding *when* and *what runs*:
     - Only when I press Update : nothing automatic; the Update button (or
                                 asking an AI assistant) runs a sync
     - When I open JobTrace,
       via the CLI            : on dashboard load (once/day), the server
                                shells out to `claude` / `codex`
     - When I open JobTrace,
       with my API keys       : on dashboard load (once/day), the server
                                runs it in-process (Gmail app password or
                                Google OAuth, plus your Anthropic API key)
   The tracker works fully without any of this. */

const GmailSync = (() => {
  let view = "status"; // "status" | "settings"
  let cfg = null;
  let doctor = null;

  function fmt(iso) {
    if (!iso) return null;
    const d = new Date(iso);
    return isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
  }

  const STALE_MS = 36 * 3600 * 1000;
  const VERY_STALE_MS = 5 * 24 * 3600 * 1000;

  function updatePill(status) {
    const btn = document.getElementById("gmail-status-btn");
    document.getElementById("gmail-status-icon").innerHTML = Icons.mail;
    btn.classList.remove("is-stale", "is-very-stale", "has-unresolved");

    if (status.running) {
      btn.title = "Email: checking…";
      return;
    }
    if (!status.lastSuccessfulSync) {
      btn.title = status.autoEnabled ? "Email: waiting for first check" : "Email not checked yet";
      return;
    }
    const r = status.lastSyncResult || {};
    const parts = [];
    if (r.applicationsCreated) parts.push(`${r.applicationsCreated} new`);
    if (r.applicationsUpdated) parts.push(`${r.applicationsUpdated} updated`);
    if (!parts.length) parts.push(`${r.emailsReviewed || 0} reviewed`);
    let title = `Email: ${fmt(status.lastSuccessfulSync)} · ${parts.join(" · ")}`;
    btn.classList.toggle("has-unresolved", status.unresolvedCount > 0);

    const age = Date.now() - Date.parse(status.lastSuccessfulSync);
    if (status.autoEnabled && age >= VERY_STALE_MS) {
      btn.classList.add("is-very-stale");
      title += " — no successful automatic check in days, open Email settings.";
    } else if (status.autoEnabled && age >= STALE_MS) {
      btn.classList.add("is-stale");
      title += " — the automatic check hasn't succeeded in a while.";
    }
    btn.title = title;
  }

  // ---- status view --------------------------------------------------
  function statRow(label, value) {
    return Utils.el("div", { class: "gmail-stat-row" }, [
      Utils.el("span", { class: "gmail-stat-label" }, label),
      Utils.el("span", { class: "gmail-stat-value" }, String(value ?? 0)),
    ]);
  }

  // ---- unresolved items: open / add / attach / discard ----------------
  function inferSource(sender) {
    const s = (sender || "").toLowerCase();
    if (s.includes("linkedin.com")) return "LinkedIn";
    if (s.includes("indeed.com")) return "Indeed";
    if (s.includes("glassdoor")) return "Glassdoor";
    return "";
  }

  function itemNote(item) {
    const subj = item.subject || "(no subject)";
    return `From email: "${subj}"${item.reason ? " — " + item.reason : ""}`;
  }

  function newAppPrefill(item) {
    const p = {
      company: item.possibleCompany || "",
      position: item.possiblePosition || "",
      source: inferSource(item.sender),
      notes: itemNote(item),
    };
    if (/^\d{4}-\d{2}-\d{2}$/.test(item.emailDate || "")) p.application_date = item.emailDate;
    return p;
  }

  async function resolveItem(id) {
    try { await Api.deleteUnresolved(id); } catch (e) { /* already gone is fine */ }
    loadStatus();
    if (typeof Dashboard !== "undefined") Dashboard.refresh();
    if (!document.getElementById("gmail-sync-overlay").hidden && view === "status") renderModal();
  }

  function openEmailView(item) {
    document.getElementById("email-view-title").textContent = item.subject || "Email";
    const meta = document.getElementById("email-view-meta");
    meta.innerHTML = "";
    meta.appendChild(Utils.el("div", {}, [Utils.el("strong", {}, "From: "), document.createTextNode(item.sender || "Unknown sender")]));
    if (item.emailDate) meta.appendChild(Utils.el("div", {}, [Utils.el("strong", {}, "Date: "), document.createTextNode(item.emailDate)]));
    if (item.reason) meta.appendChild(Utils.el("div", {}, [Utils.el("strong", {}, "Why it's unresolved: "), document.createTextNode(item.reason)]));
    const bodyEl = document.getElementById("email-view-body");
    bodyEl.textContent = item.body
      || "The email body wasn't captured for this item — it was synced before this feature, or the sync didn't save it. Open it in Gmail to read the full message.";
    Utils.openOverlay("email-view-overlay");
  }

  function unresolvedItemRow(item) {
    const openBtn = Utils.el("button", { class: "btn btn-ghost btn-sm", type: "button", onclick: () => openEmailView(item) }, "Open email");
    const newBtn = Utils.el("button", {
      class: "btn btn-ghost btn-sm", type: "button",
      onclick: () => AppForm.openCreate({ prefill: newAppPrefill(item), onSaved: () => resolveItem(item.id) }),
    }, "+ New application");

    const attachBtn = Utils.el("button", {
      class: "btn btn-ghost btn-sm", type: "button",
      onclick: () => AppPicker.open({
        onPick: (app) => AppForm.openEdit(app, {
          prefill: { source: inferSource(item.sender) },
          onSaved: () => resolveItem(item.id),
        }),
      }),
    }, "Attach to existing…");

    const discardBtn = Utils.el("button", {
      class: "btn btn-danger btn-sm", type: "button",
      onclick: async () => {
        const ok = await Utils.confirmDialog("Discard this email?",
          "It's removed from the unresolved list. No application is touched.");
        if (!ok) return;
        await resolveItem(item.id);
        Utils.toast("Discarded", "success");
      },
    }, "Discard");

    return Utils.el("div", { class: "gmail-unresolved-item" }, [
      Utils.el("div", { class: "gmail-unresolved-top" }, [
        Utils.el("span", { class: "gmail-unresolved-subject" }, item.subject || "(no subject)"),
        Utils.el("span", { class: "gmail-unresolved-date" }, item.emailDate || ""),
      ]),
      Utils.el("div", { class: "gmail-unresolved-meta" }, `${item.sender || "Unknown sender"}${item.possibleCompany ? ` · ${item.possibleCompany}` : ""}${item.possiblePosition ? ` — ${item.possiblePosition}` : ""}`),
      Utils.el("div", { class: "gmail-unresolved-reason" }, item.reason || ""),
      Utils.el("div", { class: "gmail-unresolved-actions" }, [openBtn, newBtn, attachBtn, discardBtn]),
    ]);
  }

  async function renderStatus(body) {
    let status, unresolved;
    try {
      [status, unresolved] = await Promise.all([Api.getGmailSyncStatus(), Api.getGmailUnresolved()]);
    } catch (err) {
      body.appendChild(Utils.el("div", { class: "empty-state" }, err.message));
      return;
    }

    body.appendChild(Utils.el("div", { class: "gmail-last-sync" },
      status.lastSuccessfulSync ? `Last checked: ${fmt(status.lastSuccessfulSync)}` : "Email not checked yet"));

    body.appendChild(Utils.el("div", { class: "gmail-account-line" },
      status.connectedAccount
        ? [Utils.el("span", {}, "Connected mailbox: "), Utils.el("strong", {}, status.connectedAccount)]
        : [Utils.el("span", { class: "gmail-account-unknown" }, "Connected mailbox: not recorded yet — the next sync will show which inbox it reads.")]));

    const lr = status.lastRun;
    if (lr) {
      body.appendChild(Utils.el("div", { class: `gmail-runline ${lr.ok ? "ok" : "bad"}` },
        `Last automatic run (${lr.trigger}, ${lr.method}): ${lr.ok ? "success" : "failed"}${lr.error ? " — " + lr.error : ""}`));
    }

    const r = status.lastSyncResult || {};
    body.appendChild(Utils.el("div", { class: "gmail-stats-grid" }, [
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
    ]));

    body.appendChild(Utils.el("div", { class: "detail-section-header" }, [Utils.el("h4", {}, "Unresolved items")]));
    if (!unresolved.items || unresolved.items.length === 0) {
      body.appendChild(Utils.el("div", { class: "empty-state" }, "No unresolved items."));
    } else {
      const list = Utils.el("div", { class: "gmail-unresolved-list" });
      for (const item of unresolved.items) {
        list.appendChild(unresolvedItemRow(item));
      }
      body.appendChild(list);
    }

    body.appendChild(Utils.el("p", { class: "gmail-sync-note" },
      status.method === "manual"
        ? "Email is checked only when you press Update (or ask your AI assistant to \"sync my Gmail\"). Switch to an automatic method under Settings."
        : `Email is checked automatically when you open JobTrace, at most once a day (${status.method}). Change this under Settings.`));
  }

  // ---- settings view ----------------------------------------------
  function checklistRow(ok, text) {
    return Utils.el("div", { class: `sync-check ${ok === true ? "ok" : ok === false ? "bad" : "unknown"}` }, [
      Utils.el("span", { class: "sync-check-mark" }, ok === true ? "✓" : ok === false ? "✕" : "•"),
      Utils.el("span", {}, text),
    ]);
  }

  function methodRadios() {
    const wrap = Utils.el("div", { class: "sync-method-radios" });
    for (const [val, label, hint] of [
      ["manual", "Only when I press Update", "No automatic sync. Press Update (top bar) to check on demand, or ask your AI assistant to “sync my Gmail”. No setup."],
      ["cli", "Sync when I open JobTrace — via the CLI", "On open (once a day), the server runs the claude / codex CLI, signed in with a Gmail connector."],
      ["keys", "Sync when I open JobTrace — with my API keys", "On open (once a day), the server runs it in-process with your Gmail access + Anthropic API key. No assistant app."],
    ]) {
      const id = `sync-method-${val}`;
      const radio = Utils.el("input", { type: "radio", name: "sync-method", id, value: val });
      if (cfg.method === val) radio.checked = true;
      radio.addEventListener("change", () => saveConfig({ method: val }));
      wrap.appendChild(Utils.el("label", { class: "sync-method-option", for: id }, [
        radio,
        Utils.el("div", {}, [
          Utils.el("div", { class: "sync-method-name" }, label),
          Utils.el("div", { class: "sync-method-hint" }, hint),
        ]),
      ]));
    }
    return wrap;
  }

  function syncOptionsBlock() {
    const wrap = Utils.el("div", { class: "sync-auto-block" });

    const ws = Utils.el("input", { type: "checkbox", id: "sync-websearch" });
    ws.checked = cfg.keys.enable_web_search !== false;
    ws.addEventListener("change", () => saveConfig({ keys: { enable_web_search: ws.checked } }));
    wrap.appendChild(Utils.el("label", { class: "sync-inline" }, [ws, Utils.el("span", {}, "Let the sync look up job location / link on the web")]));

    wrap.appendChild(Utils.el("p", { class: "sync-fineprint" }, "Runs once when you open JobTrace, at most once a day. No background timer — nothing needs to stay running. Use “Check now” below any time."));
    return wrap;
  }

  function cliBlock() {
    const wrap = Utils.el("div", { class: "sync-config-block" });
    const sel = Utils.el("select", { id: "sync-cli-command" });
    for (const c of ["claude", "codex"]) {
      const o = Utils.el("option", { value: c }, c);
      if (cfg.cli.command === c) o.selected = true;
      sel.appendChild(o);
    }
    sel.addEventListener("change", () => saveConfig({ cli: { command: sel.value } }));
    wrap.appendChild(Utils.el("label", { class: "sync-inline" }, [Utils.el("span", {}, "Command"), sel]));

    const d = doctor && doctor.cli && doctor.cli[cfg.cli.command];
    if (d) {
      wrap.appendChild(checklistRow(d.found, d.found ? `Found: ${d.path}` : "Command not found on PATH"));
      if (d.found) wrap.appendChild(checklistRow(d.gmail_connector, d.gmail_connector ? "Gmail connector present" : "No Gmail connector on the CLI"));
      if (d.fix) wrap.appendChild(Utils.el("p", { class: "sync-fix" }, d.fix));
      if (d.note) wrap.appendChild(Utils.el("p", { class: "sync-fineprint" }, d.note));
    }
    wrap.appendChild(syncOptionsBlock());
    return wrap;
  }

  function keysBlock() {
    const wrap = Utils.el("div", { class: "sync-config-block" });
    const k = cfg.keys;

    wrap.appendChild(Utils.el("div", { class: "sync-field-label" }, "Gmail access"));
    const transport = Utils.el("div", { class: "sync-subradios" });
    for (const [val, label, hint] of [
      ["api", "Google sign-in (OAuth)", "Read-only scope, revocable per-app. Needs a one-time Google Cloud client — see GMAIL_SYNC_SETUP.md."],
      ["imap", "Gmail app password", "Two minutes to set up, but a static password with full mailbox access (read + send). Only for a machine you control."],
    ]) {
      const id = `sync-transport-${val}`;
      const radio = Utils.el("input", { type: "radio", name: "sync-transport", id, value: val });
      if (k.gmail_transport === val) radio.checked = true;
      radio.addEventListener("change", () => saveConfig({ keys: { gmail_transport: val } }));
      transport.appendChild(Utils.el("label", { class: "sync-radio-stack", for: id }, [
        Utils.el("div", { class: "sync-inline" }, [radio, Utils.el("span", {}, label)]),
        Utils.el("div", { class: "sync-fineprint" }, hint),
      ]));
    }
    wrap.appendChild(transport);

    if (k.gmail_transport === "imap") {
      wrap.appendChild(Utils.el("p", { class: "sync-warn" },
        "⚠ A Gmail app password can't be limited to read-only and lets anyone with the file send mail as you. " +
        "It's stored locally (chmod 600) and you can revoke it any time at myaccount.google.com → Security → App passwords. " +
        "Prefer Google sign-in if you can."));
      wrap.appendChild(field("Gmail address", "sync-gmail-address", "email", k.gmail_address || "", "you@gmail.com"));
      wrap.appendChild(secretField("Gmail app password", "sync-gmail-apppw", k.gmail_app_password_set,
        "16 characters from myaccount.google.com → Security → App passwords"));
      const testBtn = Utils.el("button", { class: "btn btn-ghost btn-sm", type: "button" }, "Test Gmail connection");
      const testOut = Utils.el("span", { class: "sync-test-result" });
      testBtn.addEventListener("click", async () => {
        testBtn.disabled = true; testOut.textContent = "testing…"; testOut.className = "sync-test-result";
        try {
          const res = await Api.testImap();
          testOut.textContent = res.ok ? "✓ connected" : "✕ " + res.error;
          testOut.className = "sync-test-result " + (res.ok ? "ok" : "bad");
        } catch (e) { testOut.textContent = "✕ " + e.message; testOut.className = "sync-test-result bad"; }
        finally { testBtn.disabled = false; }
      });
      wrap.appendChild(Utils.el("div", { class: "sync-inline" }, [testBtn, testOut]));
    } else {
      wrap.appendChild(Utils.el("p", { class: "sync-fineprint" },
        "1. pip install google-api-python-client google-auth-oauthlib\n" +
        "2. Save your OAuth client JSON as data/gmail_api_credentials.json\n" +
        "3. Run the one-time consent:  python3 backend/sync/agent.py --dry-run\n" +
        "Full walkthrough in GMAIL_SYNC_SETUP.md."));
    }

    wrap.appendChild(secretField("Anthropic API key", "sync-anthropic-key", k.anthropic_api_key_set, "sk-ant-…  (console.anthropic.com)"));
    wrap.appendChild(field("Model", "sync-model", "text", k.model || "claude-sonnet-5", ""));

    const d = doctor && doctor.keys;
    if (d) {
      wrap.appendChild(checklistRow(d.anthropic_library, "Anthropic Python library installed"));
      wrap.appendChild(checklistRow(d.anthropic_api_key_set, "Anthropic API key saved"));
      wrap.appendChild(checklistRow(d.gmail_configured, "Gmail access configured"));
      (d.fixes || []).forEach((f) => wrap.appendChild(Utils.el("p", { class: "sync-fix" }, f)));
    }

    wrap.appendChild(Utils.el("div", { class: "sync-secret-actions" }, [
      Utils.el("button", { class: "btn btn-primary btn-sm", type: "button", onclick: saveSecrets }, "Save keys"),
    ]));
    wrap.appendChild(syncOptionsBlock());
    return wrap;
  }

  function field(label, id, type, value, placeholder) {
    const input = Utils.el("input", { type, id, value: value || "", placeholder: placeholder || "" });
    return Utils.el("label", { class: "sync-field" }, [Utils.el("span", {}, label), input]);
  }
  function secretField(label, id, isSet, placeholder) {
    const input = Utils.el("input", { type: "password", id, placeholder: isSet ? "•••••••• (saved — leave blank to keep)" : (placeholder || "") });
    return Utils.el("label", { class: "sync-field" }, [Utils.el("span", {}, label), input]);
  }

  async function saveConfig(patch) {
    try {
      cfg = await Api.updateSyncConfig(patch);
      renderModal();                        // reflect the change immediately
      loadStatus();
      Api.getSyncDoctor().then((d) => {     // capability re-check in the background
        doctor = d;
        if (view === "settings" && !document.getElementById("gmail-sync-overlay").hidden) renderModal();
      }).catch(() => {});
    } catch (err) { Utils.toast(err.message, "error"); }
  }

  async function saveSecrets() {
    const patch = { keys: {} };
    const addr = document.getElementById("sync-gmail-address");
    const apppw = document.getElementById("sync-gmail-apppw");
    const akey = document.getElementById("sync-anthropic-key");
    const model = document.getElementById("sync-model");
    if (addr) patch.keys.gmail_address = addr.value.trim();
    if (apppw && apppw.value.trim()) patch.keys.gmail_app_password = apppw.value.trim();
    if (akey && akey.value.trim()) patch.keys.anthropic_api_key = akey.value.trim();
    if (model) patch.keys.model = model.value.trim() || "claude-sonnet-5";
    await saveConfig(patch);
    Utils.toast("Saved", "success");
  }

  async function renderSettings(body) {
    if (!cfg) {
      try { cfg = await Api.getSyncConfig(); doctor = await Api.getSyncDoctor(); }
      catch (err) { body.appendChild(Utils.el("div", { class: "empty-state" }, err.message)); return; }
    }

    body.appendChild(Utils.el("h4", { class: "sync-h4" }, "How should Gmail sync run?"));
    body.appendChild(methodRadios());

    if (cfg.method === "manual") {
      body.appendChild(Utils.el("p", { class: "sync-fineprint" },
        "Nothing runs on its own. Press Update in the top bar whenever you want a check — or open this folder with an AI assistant (Claude Desktop, Code, or Cowork) and say “sync my Gmail”; it reads GMAIL_SYNC.md and updates the tracker. Nothing to install."));
    } else if (cfg.method === "cli") {
      body.appendChild(cliBlock());
    } else {
      body.appendChild(keysBlock());
    }

    if (cfg.method !== "manual") {
      const runBtn = Utils.el("button", { class: "btn btn-primary btn-sm", type: "button" }, "Check now");
      runBtn.addEventListener("click", async () => {
        runBtn.disabled = true;
        try {
          await runSyncWithProgress({
            onRefreshed: () => {
              loadStatus();
              if (!document.getElementById("gmail-sync-overlay").hidden) renderModal();
            },
          });
        } finally {
          runBtn.disabled = false;
        }
      });
      body.appendChild(Utils.el("div", { class: "sync-run-row" }, [runBtn]));
    }
  }

  // ---- modal shell ---------------------------------------------------
  function renderModal() {
    const body = document.getElementById("gmail-sync-body");
    body.innerHTML = "";

    const tabs = Utils.el("div", { class: "sync-tabs" });
    for (const [v, label] of [["status", "Status"], ["settings", "Settings"]]) {
      const b = Utils.el("button", { class: `sync-tab ${view === v ? "active" : ""}`, type: "button" }, label);
      b.addEventListener("click", () => { view = v; renderModal(); });
      tabs.appendChild(b);
    }
    body.appendChild(tabs);

    const pane = Utils.el("div", { class: "sync-pane" });
    body.appendChild(pane);
    const loading = Utils.el("div", { class: "empty-state" }, "Loading…");
    pane.appendChild(loading);

    (view === "status" ? renderStatus : renderSettings)(pane).then(() => {
      loading.remove();
    }).catch((err) => {
      loading.textContent = err.message || "Something went wrong.";
    });
  }

  async function loadStatus() {
    try { updatePill(await Api.getGmailSyncStatus()); } catch (e) { /* non-critical */ }
  }

  function openModal(startView) {
    cfg = null; doctor = null; view = startView;
    Utils.openOverlay("gmail-sync-overlay");
    renderModal();
  }

  function bindEvents() {
    document.getElementById("gmail-status-btn").addEventListener("click", () => openModal("status"));
    const settingsBtn = document.getElementById("gmail-settings-btn");
    settingsBtn.innerHTML = Icons.gear;
    settingsBtn.addEventListener("click", () => openModal("settings"));
    const close = () => Utils.closeOverlay("gmail-sync-overlay");
    document.getElementById("gmail-sync-close").addEventListener("click", close);
    document.getElementById("gmail-sync-ok").addEventListener("click", close);
    document.getElementById("gmail-sync-overlay").addEventListener("click", (e) => {
      if (e.target.id === "gmail-sync-overlay") close();
    });

    const closeEmail = () => Utils.closeOverlay("email-view-overlay");
    document.getElementById("email-view-close").addEventListener("click", closeEmail);
    document.getElementById("email-view-ok").addEventListener("click", closeEmail);
    document.getElementById("email-view-overlay").addEventListener("click", (e) => {
      if (e.target.id === "email-view-overlay") closeEmail();
    });
  }

  function init() {
    bindEvents();
    loadStatus();
    setInterval(loadStatus, 60000);
  }

  return { init, loadStatus };
})();
