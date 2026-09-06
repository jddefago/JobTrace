/* Add / Edit application side panel. */

const AppForm = (() => {
  let mode = "create"; // 'create' | 'edit'
  let clientRequestId = null;
  let editingId = null;
  let savedCallback = null; // run once after a successful create/save

  function populateSelects() {
    const stageSel = document.getElementById("f-stage");
    const outcomeSel = document.getElementById("f-outcome");
    const sourceSel = document.getElementById("f-source");

    stageSel.innerHTML = State.meta.stages.map((s) => `<option value="${s}">${s}</option>`).join("");
    outcomeSel.innerHTML = State.meta.outcomes.map((o) => `<option value="${o}">${o}</option>`).join("");
    sourceSel.innerHTML =
      State.meta.default_sources.map((s) => `<option value="${s}">${s}</option>`).join("") +
      `<option value="__custom__">Custom…</option>`;
  }

  function onSourceChange() {
    const sourceSel = document.getElementById("f-source");
    const customRow = document.getElementById("f-source-custom-row");
    customRow.hidden = sourceSel.value !== "__custom__";
  }

  function resetForm() {
    document.getElementById("app-form").reset();
    document.getElementById("f-date").value = Utils.todayIso();
    document.getElementById("f-stage").value = State.meta.stage_progression[0];
    document.getElementById("f-outcome").value = State.meta.outcomes[0];
    document.getElementById("f-source").value = State.meta.default_sources[0];
    document.getElementById("f-source-custom-row").hidden = true;
  }

  function fillForm(app) {
    document.getElementById("f-company").value = app.company || "";
    document.getElementById("f-position").value = app.position || "";
    document.getElementById("f-location").value = app.location || "";
    document.getElementById("f-date").value = app.application_date || Utils.todayIso();
    document.getElementById("f-job-url").value = app.job_url || "";
    document.getElementById("f-job-description").value = app.job_description || "";
    document.getElementById("f-notes").value = app.notes || "";
    document.getElementById("f-stage").value = app.current_stage;
    document.getElementById("f-outcome").value = app.outcome;

    const sourceSel = document.getElementById("f-source");
    const knownSource = State.meta.default_sources.includes(app.source);
    if (knownSource || !app.source) {
      sourceSel.value = app.source || State.meta.default_sources[0];
      document.getElementById("f-source-custom-row").hidden = true;
    } else {
      sourceSel.value = "__custom__";
      document.getElementById("f-source-custom-row").hidden = false;
      document.getElementById("f-source-custom").value = app.source;
    }
  }

  /* Set only the fields present (and non-empty) in `p`; leaves the rest of
     the form as it was. `source` handles the custom-source row. */
  function applyPrefill(p) {
    if (!p) return;
    const setVal = (id, v) => { if (v !== undefined && v !== null && v !== "") document.getElementById(id).value = v; };
    setVal("f-company", p.company);
    setVal("f-position", p.position);
    setVal("f-location", p.location);
    setVal("f-date", p.application_date);
    setVal("f-job-url", p.job_url);
    setVal("f-notes", p.notes);
    if (p.source) {
      const sel = document.getElementById("f-source");
      if (State.meta.default_sources.includes(p.source)) {
        sel.value = p.source;
        document.getElementById("f-source-custom-row").hidden = true;
      } else {
        sel.value = "__custom__";
        document.getElementById("f-source-custom-row").hidden = false;
        document.getElementById("f-source-custom").value = p.source;
      }
    }
  }

  function openCreate(opts = {}) {
    mode = "create";
    editingId = null;
    savedCallback = opts.onSaved || null;
    clientRequestId = Utils.uuid();
    document.getElementById("app-form-title").textContent = "Add Application";
    document.getElementById("app-form-submit").textContent = "Add Application";
    resetForm();
    applyPrefill(opts.prefill);
    Utils.openOverlay("app-form-overlay");
    document.getElementById("f-company").focus();
  }

  function openEdit(app, opts = {}) {
    mode = "edit";
    editingId = app.id;
    savedCallback = opts.onSaved || null;
    document.getElementById("app-form-title").textContent = "Edit Application";
    document.getElementById("app-form-submit").textContent = "Save Changes";
    fillForm(app);
    if (opts.prefill) {
      // Only fill fields the application doesn't already have a value for.
      const blankOnly = {};
      for (const [k, v] of Object.entries(opts.prefill)) {
        if (!app[k]) blankOnly[k] = v;
      }
      applyPrefill(blankOnly);
    }
    Utils.openOverlay("app-form-overlay");
  }

  function close() {
    Utils.closeOverlay("app-form-overlay");
    savedCallback = null;
  }

  function gatherPayload() {
    const sourceSel = document.getElementById("f-source");
    const source = sourceSel.value === "__custom__" ? document.getElementById("f-source-custom").value.trim() : sourceSel.value;

    return {
      company: document.getElementById("f-company").value.trim(),
      position: document.getElementById("f-position").value.trim(),
      location: document.getElementById("f-location").value.trim(),
      application_date: document.getElementById("f-date").value,
      source,
      job_url: document.getElementById("f-job-url").value.trim(),
      job_description: document.getElementById("f-job-description").value,
      notes: document.getElementById("f-notes").value,
      current_stage: document.getElementById("f-stage").value,
      outcome: document.getElementById("f-outcome").value,
    };
  }

  async function handleSubmit(evt) {
    evt.preventDefault();
    const submitBtn = document.getElementById("app-form-submit");
    if (submitBtn.disabled) return; // guards against double-click / double-submit
    submitBtn.disabled = true;

    const payload = gatherPayload();

    try {
      if (mode === "create") {
        payload.client_request_id = clientRequestId;
        const created = await Api.createApplication(payload);
        Utils.toast(`Added ${created.company} — ${created.position}`, "success");
      } else {
        const updated = await Api.updateApplication(editingId, payload);
        Utils.toast(`Saved changes to ${updated.company}`, "success");
        if (typeof Detail !== "undefined" && Detail.isShowing(editingId)) {
          Detail.open(editingId);
        }
      }
      const cb = savedCallback;
      close();
      if (cb) { try { await cb(); } catch (e) {} }
      if (typeof Dashboard !== "undefined") Dashboard.refresh();
    } catch (err) {
      Utils.toast(err.message, "error");
    } finally {
      submitBtn.disabled = false;
    }
  }

  function init() {
    populateSelects();
    document.getElementById("f-source").addEventListener("change", onSourceChange);
    document.getElementById("add-application-btn").innerHTML = Icons.plus;
    document.getElementById("add-application-btn").addEventListener("click", openCreate);
    document.getElementById("app-form-close").addEventListener("click", close);
    document.getElementById("app-form-cancel").addEventListener("click", close);
    document.getElementById("app-form").addEventListener("submit", handleSubmit);
    document.getElementById("app-form-overlay").addEventListener("click", (e) => {
      if (e.target.id === "app-form-overlay") close();
    });
  }

  return { init, openCreate, openEdit, close };
})();

/* Searchable "pick one of my applications" modal. Used to attach an
   unresolved email to an existing application. */
const AppPicker = (() => {
  let onPick = null;
  let apps = [];

  function close() {
    Utils.closeOverlay("app-picker-overlay");
    onPick = null;
  }

  function choose(app) {
    const cb = onPick;
    close();
    if (cb) cb(app);
  }

  function render(filter) {
    const list = document.getElementById("app-picker-list");
    list.innerHTML = "";
    const q = (filter || "").trim().toLowerCase();
    const rows = q
      ? apps.filter((a) => `${a.company} ${a.position}`.toLowerCase().includes(q))
      : apps;
    if (!rows.length) {
      list.appendChild(Utils.el("div", { class: "empty-state" }, apps.length ? "No matches." : "No open applications."));
      return;
    }
    for (const a of rows) {
      list.appendChild(Utils.el("button", { class: "app-picker-row", type: "button", onclick: () => choose(a) }, [
        Utils.el("span", { class: "app-picker-company" }, a.company),
        Utils.el("span", { class: "app-picker-position" }, a.position),
        Utils.el("span", { class: Utils.stageBadgeClass(a.current_stage) }, a.current_stage),
      ]));
    }
  }

  async function open(opts = {}) {
    onPick = opts.onPick || null;
    const search = document.getElementById("app-picker-search");
    const list = document.getElementById("app-picker-list");
    search.value = "";
    list.innerHTML = "";
    list.appendChild(Utils.el("div", { class: "empty-state" }, "Loading…"));
    Utils.openOverlay("app-picker-overlay");
    search.focus();
    try {
      const res = await Api.listApplications({ page_size: 500, sort_by: "company", sort_order: "asc" });
      apps = (res.items || []).filter((a) => a.current_stage !== "Closed");
      render("");
    } catch (err) {
      list.innerHTML = "";
      list.appendChild(Utils.el("div", { class: "empty-state" }, err.message));
    }
  }

  function init() {
    document.getElementById("app-picker-close").addEventListener("click", close);
    document.getElementById("app-picker-overlay").addEventListener("click", (e) => {
      if (e.target.id === "app-picker-overlay") close();
    });
    document.getElementById("app-picker-search").addEventListener("input", (e) => render(e.target.value));
  }

  return { init, open };
})();
