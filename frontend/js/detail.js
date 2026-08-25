/* Application detail side panel: header, job description, notes, timeline. */

const Detail = (() => {
  let currentApp = null;

  function isShowing(id) {
    return !document.getElementById("detail-overlay").hidden && currentApp && currentApp.id === id;
  }

  async function open(id) {
    try {
      currentApp = await Api.getApplication(id);
    } catch (err) {
      Utils.toast(err.message, "error");
      return;
    }
    render();
    Utils.openOverlay("detail-overlay");
  }

  function close() {
    Utils.closeOverlay("detail-overlay");
    currentApp = null;
  }

  function render() {
    const app = currentApp;
    document.getElementById("detail-position").textContent = app.position;

    const body = document.getElementById("detail-body");
    body.innerHTML = "";

    body.appendChild(
      Utils.el("div", { class: "detail-header-meta" }, [
        Utils.el("span", { class: Utils.stageBadgeClass(app.current_stage) }, app.current_stage),
        Utils.el("span", { class: Utils.outcomeBadgeClass(app.outcome) }, app.outcome),
      ])
    );
    body.appendChild(Utils.el("div", { class: "detail-company" }, `${app.company}${app.location ? " · " + app.location : ""}`));
    body.appendChild(
      Utils.el("div", { class: "detail-rail-row" }, [
        Utils.stageRail(app.current_stage, app.max_stage_reached, app.outcome, { size: "lg" }),
      ])
    );

    const metaGrid = Utils.el("div", { class: "detail-meta-grid" }, [
      metaItem("Application date", Utils.formatDate(app.application_date)),
      metaItem("Days since application", `${app.days_since_application ?? "—"} days`),
      metaItem("Source", app.source || "—"),
      metaItem("Job URL", app.job_url ? linkNode(app.job_url) : "—"),
    ]);
    body.appendChild(metaGrid);

    body.appendChild(
      Utils.el("div", { style: "display:flex; gap:8px; margin-bottom: 20px;" }, [
        Utils.el("button", { class: "btn btn-ghost btn-sm", onclick: () => AppForm.openEdit(app) }, "Edit details"),
      ])
    );

    // Job description
    body.appendChild(section("Job Description", jobDescriptionBox(app)));

    // Notes
    body.appendChild(section("Notes", notesBox(app)));

    // Timeline
    body.appendChild(timelineSection(app));

    // Danger zone
    body.appendChild(
      Utils.el("div", { class: "danger-zone" }, [
        Utils.el("button", { class: "btn btn-danger btn-sm", onclick: onDeleteApplication }, "Delete application"),
      ])
    );
  }

  function metaItem(label, valueNode) {
    return Utils.el("div", { class: "detail-meta-item" }, [
      Utils.el("div", { class: "meta-label" }, label),
      Utils.el("div", { class: "meta-value" }, valueNode),
    ]);
  }

  function linkNode(url) {
    const safeUrl = /^https?:\/\//i.test(url) ? url : `https://${url}`;
    return Utils.el("a", { class: "text-link", href: safeUrl, target: "_blank", rel: "noopener noreferrer" }, "Open original vacancy ↗");
  }

  function section(title, contentNode) {
    return Utils.el("div", { class: "detail-section" }, [
      Utils.el("div", { class: "detail-section-header" }, [Utils.el("h4", {}, title)]),
      contentNode,
    ]);
  }

  function jobDescriptionBox(app) {
    if (!app.job_description) {
      return Utils.el("div", { class: "job-description-box" }, "No job description saved.");
    }
    return Utils.el("div", { class: "job-description-box" }, app.job_description);
  }

  function notesBox(app) {
    const textarea = Utils.el("textarea", { placeholder: "Add notes about this application…" });
    textarea.value = app.notes || "";
    const saveBtn = Utils.el("button", { class: "btn btn-primary btn-sm", style: "margin-top:8px; display:none;" }, "Save Notes");

    textarea.addEventListener("input", () => {
      saveBtn.style.display = textarea.value !== (app.notes || "") ? "inline-block" : "none";
    });
    saveBtn.addEventListener("click", async () => {
      saveBtn.disabled = true;
      try {
        const updated = await Api.updateApplication(app.id, { notes: textarea.value });
        currentApp = updated;
        app.notes = updated.notes;
        saveBtn.style.display = "none";
        Utils.toast("Notes saved", "success");
        if (typeof Dashboard !== "undefined") Dashboard.refresh();
      } catch (err) {
        Utils.toast(err.message, "error");
      } finally {
        saveBtn.disabled = false;
      }
    });

    return Utils.el("div", { class: "notes-box" }, [textarea, saveBtn]);
  }

  function timelineSection(app) {
    const header = Utils.el("div", { class: "detail-section-header" }, [
      Utils.el("h4", {}, "Timeline"),
      Utils.el("button", { class: "btn btn-ghost btn-sm", onclick: () => EventForm.openAdd(app.id) }, "+ Add Event"),
    ]);

    const list = Utils.el("ul", { class: "timeline" });
    const sorted = [...app.events].sort((a, b) => (a.event_date < b.event_date ? 1 : a.event_date > b.event_date ? -1 : b.id - a.id));

    if (sorted.length === 0) {
      list.appendChild(Utils.el("div", { class: "empty-state" }, "No events yet."));
    }

    for (const ev of sorted) {
      list.appendChild(
        Utils.el("li", { class: "timeline-item" }, [
          Utils.el("div", { class: "timeline-dot" }),
          Utils.el("div", { class: "timeline-content" }, [
            Utils.el("div", { class: "timeline-top" }, [
              Utils.el("span", { class: "timeline-type" }, ev.event_type),
              Utils.el("span", { class: "timeline-date" }, Utils.formatDate(ev.event_date)),
            ]),
            ev.description ? Utils.el("div", { class: "timeline-desc" }, ev.description) : null,
            Utils.el("div", { class: "timeline-actions" }, [
              Utils.el("button", { onclick: () => EventForm.openEdit(app.id, ev) }, "Edit"),
              Utils.el("button", { onclick: () => onDeleteEvent(ev.id) }, "Delete"),
            ]),
          ]),
        ])
      );
    }

    return Utils.el("div", { class: "detail-section" }, [header, list]);
  }

  async function onDeleteEvent(eventId) {
    const ok = await Utils.confirmDialog("Delete this event?", "This will permanently remove it from the timeline.");
    if (!ok) return;
    try {
      await Api.deleteEvent(eventId);
      Utils.toast("Event deleted", "success");
      await open(currentApp.id);
    } catch (err) {
      Utils.toast(err.message, "error");
    }
  }

  async function onDeleteApplication() {
    const ok = await Utils.confirmDialog(
      "Delete this application?",
      `This permanently deletes ${currentApp.company} — ${currentApp.position} and its full timeline. This cannot be undone.`
    );
    if (!ok) return;
    try {
      await Api.deleteApplication(currentApp.id);
      Utils.toast("Application deleted", "success");
      close();
      if (typeof Dashboard !== "undefined") Dashboard.refresh();
    } catch (err) {
      Utils.toast(err.message, "error");
    }
  }

  function init() {
    document.getElementById("detail-close").addEventListener("click", close);
    document.getElementById("detail-overlay").addEventListener("click", (e) => {
      if (e.target.id === "detail-overlay") close();
    });
    document.getElementById("confirm-cancel").addEventListener("click", () => Utils.resolveConfirm(false));
    document.getElementById("confirm-ok").addEventListener("click", () => Utils.resolveConfirm(true));
    document.getElementById("confirm-overlay").addEventListener("click", (e) => {
      if (e.target.id === "confirm-overlay") Utils.resolveConfirm(false);
    });
    EventForm.init();
  }

  return { init, open, close, isShowing, get currentApp() { return currentApp; } };
})();

/* Add / edit a single timeline event (modal). */
const EventForm = (() => {
  let applicationId = null;
  let editingEventId = null;

  function populateTypes() {
    const sel = document.getElementById("ev-type");
    sel.innerHTML =
      State.meta.default_event_types.map((t) => `<option value="${t}">${t}</option>`).join("") +
      `<option value="__custom__">Custom…</option>`;
  }

  function onTypeChange() {
    const sel = document.getElementById("ev-type");
    document.getElementById("ev-type-custom-row").hidden = sel.value !== "__custom__";
  }

  function openAdd(appId) {
    editingEventId = null;
    applicationId = appId;
    document.getElementById("event-form-title").textContent = "Add Event";
    document.getElementById("event-form-submit").textContent = "Save Event";
    document.getElementById("event-form").reset();
    document.getElementById("ev-date").value = Utils.todayIso();
    document.getElementById("ev-type").value = State.meta.default_event_types[0];
    document.getElementById("ev-type-custom-row").hidden = true;
    Utils.openOverlay("event-form-overlay");
  }

  function openEdit(appId, event) {
    editingEventId = event.id;
    applicationId = appId;
    document.getElementById("event-form-title").textContent = "Edit Event";
    document.getElementById("event-form-submit").textContent = "Save Event";
    document.getElementById("ev-date").value = event.event_date;
    document.getElementById("ev-description").value = event.description || "";

    const knownType = State.meta.default_event_types.includes(event.event_type);
    if (knownType) {
      document.getElementById("ev-type").value = event.event_type;
      document.getElementById("ev-type-custom-row").hidden = true;
    } else {
      document.getElementById("ev-type").value = "__custom__";
      document.getElementById("ev-type-custom-row").hidden = false;
      document.getElementById("ev-type-custom").value = event.event_type;
    }
    Utils.openOverlay("event-form-overlay");
  }

  function close() {
    Utils.closeOverlay("event-form-overlay");
  }

  async function handleSubmit(evt) {
    evt.preventDefault();
    const submitBtn = document.getElementById("event-form-submit");
    if (submitBtn.disabled) return;
    submitBtn.disabled = true;

    const typeSel = document.getElementById("ev-type");
    const eventType = typeSel.value === "__custom__" ? document.getElementById("ev-type-custom").value.trim() : typeSel.value;
    const payload = {
      event_type: eventType,
      event_date: document.getElementById("ev-date").value,
      description: document.getElementById("ev-description").value,
    };

    try {
      if (editingEventId) {
        await Api.updateEvent(editingEventId, payload);
        Utils.toast("Event updated", "success");
      } else {
        await Api.addEvent(applicationId, payload);
        Utils.toast("Event added", "success");
      }
      close();
      await Detail.open(applicationId);
    } catch (err) {
      Utils.toast(err.message, "error");
    } finally {
      submitBtn.disabled = false;
    }
  }

  function init() {
    populateTypes();
    document.getElementById("ev-type").addEventListener("change", onTypeChange);
    document.getElementById("event-form-close").addEventListener("click", close);
    document.getElementById("event-form-cancel").addEventListener("click", close);
    document.getElementById("event-form").addEventListener("submit", handleSubmit);
    document.getElementById("event-form-overlay").addEventListener("click", (e) => {
      if (e.target.id === "event-form-overlay") close();
    });
  }

  return { init, openAdd, openEdit, close };
})();
