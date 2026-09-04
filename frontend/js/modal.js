/* Add / Edit application side panel. */

const AppForm = (() => {
  let mode = "create"; // 'create' | 'edit'
  let clientRequestId = null;
  let editingId = null;

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

  function openCreate() {
    mode = "create";
    editingId = null;
    clientRequestId = Utils.uuid();
    document.getElementById("app-form-title").textContent = "Add Application";
    document.getElementById("app-form-submit").textContent = "Add Application";
    resetForm();
    Utils.openOverlay("app-form-overlay");
    document.getElementById("f-company").focus();
  }

  function openEdit(app) {
    mode = "edit";
    editingId = app.id;
    document.getElementById("app-form-title").textContent = "Edit Application";
    document.getElementById("app-form-submit").textContent = "Save Changes";
    fillForm(app);
    Utils.openOverlay("app-form-overlay");
  }

  function close() {
    Utils.closeOverlay("app-form-overlay");
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
      close();
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
