/* Tracker view: outstanding assessments (to-do list) and interviews
   (list + month calendar), with the manual controls the pipeline can't
   infer from email — "mark assessment completed" and per-interview
   positive / negative outcomes. */

const Tracker = (() => {
  let data = { assessments: [], interviews: [] };
  let intMode = "list";                 // "list" | "calendar"
  let showDoneAssessments = false;
  let calCursor = null;                 // Date pinned to the 1st of the shown month
  let formMode = "interview";           // "interview" | "assessment"

  // ---- date helpers -------------------------------------------------------
  function parseWhen(s) {
    if (!s) return null;
    const str = s.length === 10 ? s + "T00:00:00" : s;
    const d = new Date(str);
    return isNaN(d.getTime()) ? null : d;
  }
  function hasTime(s) {
    return !!s && s.length > 10;
  }
  function startOfToday() {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }
  function sameDay(a, b) {
    return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  }
  function relLabel(d) {
    const target = new Date(d);
    target.setHours(0, 0, 0, 0);
    const n = Math.round((target.getTime() - startOfToday().getTime()) / 86400000);
    if (n === 0) return "today";
    if (n === 1) return "tomorrow";
    if (n === -1) return "yesterday";
    if (n > 1) return `in ${n} days`;
    return `${-n} days ago`;
  }
  function fmtWhen(s) {
    const d = parseWhen(s);
    if (!d) return "Date not set";
    const opts = hasTime(s)
      ? { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }
      : { weekday: "short", day: "numeric", month: "short", year: "numeric" };
    return d.toLocaleString(undefined, opts);
  }
  function toInputValue(s) {
    if (!s) return "";
    return s.length > 16 ? s.slice(0, 16) : s;
  }

  // Whether an interview's actual moment has already happened. A dated-only
  // value (e.g. an assessment due date) is "past" once its calendar day is
  // over; a full date+time value (every interview has one) is past the
  // instant its clock time is reached -- being scheduled "today" doesn't
  // keep it upcoming past, say, 10am just because it's still today.
  function isPastMoment(d, whenStr) {
    if (hasTime(whenStr)) return d.getTime() <= Date.now();
    const day = new Date(d); day.setHours(0, 0, 0, 0);
    return day.getTime() < startOfToday().getTime();
  }

  // "Up next" ordering: soonest upcoming interview first, then once there
  // are no more ahead, fall back to the most recently past one first
  // (whatever its outcome) and work backwards. "Past" here means the
  // interview's actual moment has passed, not just that it isn't tomorrow
  // or later -- a 10am interview earlier today is already past by evening.
  function interviewSortKey(iv) {
    const d = parseWhen(iv.when);
    if (!d) return [2, 0];
    const t = d.getTime();
    if (!isPastMoment(d, iv.when)) return [0, t];
    return [1, -t];
  }
  function sortedByUpNext(list) {
    return [...list].sort((a, b) => {
      const ka = interviewSortKey(a), kb = interviewSortKey(b);
      return ka[0] - kb[0] || ka[1] - kb[1];
    });
  }

  const INTERVIEW_ROUNDS = ["Interview 1", "Interview 2", "Final Interview"];
  function nextRoundOf(stage) {
    const i = INTERVIEW_ROUNDS.indexOf(stage);
    if (i === -1) return "Interview 1";
    return i + 1 < INTERVIEW_ROUNDS.length ? INTERVIEW_ROUNDS[i + 1] : null;
  }

  // ---- status derivation ------------------------------------------------
  // The interview list is per-*interview*, not per-application: several
  // rows can belong to the same position (one per round). Each row's status
  // must describe what happened at that specific round, not the
  // application's current overall state -- otherwise an early round that
  // was passed reads as whatever the application eventually became (e.g.
  // "Advanced → Closed" if a later round was the one that got rejected).
  // Only the most recent round for a given application can have reached an
  // offer; every earlier "passed" round just means it moved the applicant
  // on to the next round.
  function annotateInterviews(d) {
    const lastEventIdByApp = new Map();
    for (const iv of d.interviews) lastEventIdByApp.set(iv.application_id, iv.event_id);
    for (const iv of d.interviews) {
      iv.isLastForApp = iv.event_id === lastEventIdByApp.get(iv.application_id);
    }
    return d;
  }

  function interviewStatus(iv) {
    if (iv.item_status === "passed") {
      const reachedOffer = iv.isLastForApp && iv.current_stage === "Offer";
      const label = reachedOffer ? "Offer" : "Moved to next round";
      return { key: "passed", label, cls: "ts-positive" };
    }
    if (iv.item_status === "failed") return { key: "failed", label: "Not selected", cls: "ts-negative" };
    if (iv.application_dead) return { key: "closed", label: "Application closed", cls: "ts-muted" };
    const d = parseWhen(iv.when);
    if (!d) return { key: "nodate", label: "Date not set", cls: "ts-warn" };
    const today = startOfToday();
    const day = new Date(d); day.setHours(0, 0, 0, 0);
    if (day.getTime() > today.getTime()) return { key: "upcoming", label: "Upcoming", cls: "ts-upcoming", rel: relLabel(new Date(d)) };
    if (day.getTime() === today.getTime() && !isPastMoment(d, iv.when)) {
      return { key: "today", label: "Today", cls: "ts-upcoming" };
    }
    return { key: "awaiting", label: "Awaiting result", cls: "ts-awaiting", rel: relLabel(new Date(d)) };
  }

  function assessmentIsOverdue(a) {
    const d = parseWhen(a.scheduled_for);
    if (!d) return false;
    const day = new Date(d); day.setHours(0, 0, 0, 0);
    return day.getTime() < startOfToday().getTime();
  }

  // ---- assessments panel ----------------------------------------------
  function renderAssessments() {
    const host = document.getElementById("assess-list");
    host.innerHTML = "";
    const all = data.assessments;
    const outstanding = all.filter((a) => !a.completed);
    const done = all.filter((a) => a.completed);

    document.getElementById("assess-subtitle").textContent =
      outstanding.length === 0
        ? "Nothing outstanding — you're all caught up"
        : `${outstanding.length} to complete`;

    const rows = showDoneAssessments ? [...outstanding, ...done] : outstanding;
    if (rows.length === 0) {
      host.appendChild(Utils.el("div", { class: "empty-state" }, "No assessments to do."));
    }

    for (const a of rows) {
      const overdue = !a.completed && assessmentIsOverdue(a);
      const chip = a.completed
        ? Utils.el("span", { class: "tracker-status ts-positive" }, "Completed")
        : Utils.el("span", { class: `tracker-status ${overdue ? "ts-negative" : "ts-todo"}` }, overdue ? "Overdue" : "To do");

      const dueInput = Utils.el("input", {
        type: "date",
        class: "tracker-date-input",
        title: "Assessment deadline",
        value: a.scheduled_for ? a.scheduled_for.slice(0, 10) : "",
      });
      dueInput.addEventListener("change", () => onSetAssessmentDue(a, dueInput.value));

      const actions = Utils.el("div", { class: "tracker-item-actions" }, [
        Utils.el("label", { class: "tracker-date-field" }, [
          Utils.el("span", {}, "Due"), dueInput,
        ]),
        a.completed
          ? Utils.el("button", { class: "btn btn-ghost btn-sm", onclick: () => onCompleteAssessment(a, false) }, "Reopen")
          : Utils.el("button", { class: "btn btn-primary btn-sm", onclick: () => onCompleteAssessment(a, true) }, "Mark completed"),
      ]);

      host.appendChild(
        Utils.el("div", { class: `tracker-item${a.completed ? " is-done" : ""}` }, [
          Utils.el("div", { class: "tracker-item-main", onclick: () => Detail.open(a.application_id) }, [
            Utils.el("div", { class: "tracker-item-title" }, [
              Utils.el("span", { class: "tracker-company" }, a.company),
              Utils.el("span", { class: "tracker-position" }, a.position),
            ]),
            Utils.el("div", { class: "tracker-item-sub" }, [
              chip,
              a.invited_date ? Utils.el("span", { class: "tracker-meta" }, `Invited ${Utils.formatDate(a.invited_date)}`) : null,
            ]),
          ]),
          actions,
        ])
      );
    }
  }

  // ---- interviews panel: list ----------------------------------------
  function renderInterviewList() {
    const host = document.getElementById("int-list");
    host.innerHTML = "";
    const list = sortedByUpNext(data.interviews);

    const live = list.filter((i) => !["passed", "failed"].includes(i.item_status) && !i.application_dead);
    document.getElementById("int-subtitle").textContent =
      list.length === 0 ? "No interviews scheduled yet" : `${live.length} active · ${list.length} total`;

    if (list.length === 0) {
      host.appendChild(Utils.el("div", { class: "empty-state" }, "No interviews yet. Use “+ Add” when one is scheduled."));
      return;
    }

    for (const iv of list) {
      const st = interviewStatus(iv);
      const whenInput = Utils.el("input", {
        type: "datetime-local",
        class: "tracker-date-input tracker-dt-input",
        title: "Interview date & time",
        value: toInputValue(iv.scheduled_for),
      });
      whenInput.addEventListener("change", () => onSetInterviewWhen(iv, whenInput.value));

      const deleteBtn = Utils.el(
        "button",
        { class: "btn btn-danger btn-sm", title: "Remove this interview entry", onclick: () => onDeleteInterview(iv) },
        "Delete"
      );

      let resultButtons;
      if (["passed", "failed"].includes(iv.item_status)) {
        resultButtons = [
          Utils.el("button", { class: "btn btn-ghost btn-sm", onclick: () => onInterviewResult(iv, "pending") }, "Clear result"),
          deleteBtn,
        ];
      } else {
        const next = nextRoundOf(iv.current_stage);
        resultButtons = [
          Utils.el("button", { class: "btn btn-sm btn-outcome-pos", onclick: () => onInterviewResult(iv, "offer") }, "Got offer"),
          next ? Utils.el("button", { class: "btn btn-sm btn-outcome-next", onclick: () => onInterviewResult(iv, "next_round") }, `→ ${next}`) : null,
          Utils.el("button", { class: "btn btn-sm btn-outcome-neg", onclick: () => onInterviewResult(iv, "not_selected") }, "Not selected"),
          deleteBtn,
        ].filter(Boolean);
      }

      host.appendChild(
        Utils.el("div", { class: "tracker-item" }, [
          Utils.el("div", { class: "tracker-item-main", onclick: () => Detail.open(iv.application_id) }, [
            Utils.el("div", { class: "tracker-item-title" }, [
              Utils.el("span", { class: "tracker-company" }, iv.company),
              Utils.el("span", { class: "tracker-position" }, iv.position),
            ]),
            Utils.el("div", { class: "tracker-item-sub" }, [
              Utils.el("span", { class: `tracker-status ${st.cls}` }, st.label),
              Utils.el("span", { class: "tracker-meta" }, fmtWhen(iv.when)),
              st.rel ? Utils.el("span", { class: "tracker-meta tracker-rel" }, st.rel) : null,
            ]),
          ]),
          Utils.el("div", { class: "tracker-item-actions" }, [
            Utils.el("label", { class: "tracker-date-field" }, [
              Utils.el("span", {}, "When"), whenInput,
            ]),
            Utils.el("div", { class: "tracker-result-btns" }, resultButtons),
          ]),
        ])
      );
    }
  }

  // ---- interviews panel: calendar ----------------------------------
  function monthKey(d) { return `${d.getFullYear()}-${d.getMonth()}`; }

  function renderCalendar() {
    const host = document.getElementById("int-calendar");
    host.innerHTML = "";

    if (!calCursor) {
      const upcoming = data.interviews
        .map((i) => parseWhen(i.when))
        .filter((d) => d && d.getTime() >= startOfToday().getTime())
        .sort((a, b) => a - b)[0];
      const base = upcoming || new Date();
      calCursor = new Date(base.getFullYear(), base.getMonth(), 1);
    }

    const year = calCursor.getFullYear();
    const month = calCursor.getMonth();

    // events for this month, keyed by day-of-month
    const byDay = {};
    const addTo = (d, node) => {
      if (!d || d.getFullYear() !== year || d.getMonth() !== month) return;
      (byDay[d.getDate()] = byDay[d.getDate()] || []).push(node);
    };
    for (const iv of data.interviews) {
      const d = parseWhen(iv.when);
      const st = interviewStatus(iv);
      addTo(d, Utils.el("div", {
        class: `cal-chip cal-chip-interview ${st.key === "failed" ? "is-neg" : st.key === "passed" ? "is-pos" : ""}`,
        title: `${iv.company} — ${iv.position} (${st.label})`,
        onclick: (e) => { e.stopPropagation(); Detail.open(iv.application_id); },
      }, `${hasTime(iv.when) ? parseWhen(iv.when).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }) + " " : ""}${iv.company}`));
    }
    for (const a of data.assessments) {
      if (a.completed || !a.scheduled_for) continue;
      const d = parseWhen(a.scheduled_for);
      addTo(d, Utils.el("div", {
        class: "cal-chip cal-chip-assessment",
        title: `${a.company} — assessment due`,
        onclick: (e) => { e.stopPropagation(); Detail.open(a.application_id); },
      }, `${a.company} (assmt)`));
    }

    const header = Utils.el("div", { class: "cal-header" }, [
      Utils.el("button", { class: "btn btn-ghost btn-sm", onclick: () => { calCursor = new Date(year, month - 1, 1); renderCalendar(); } }, "←"),
      Utils.el("span", { class: "cal-title" }, calCursor.toLocaleDateString(undefined, { month: "long", year: "numeric" })),
      Utils.el("button", { class: "btn btn-ghost btn-sm", onclick: () => { calCursor = new Date(year, month + 1, 1); renderCalendar(); } }, "→"),
    ]);

    const grid = Utils.el("div", { class: "cal-grid" });
    for (const dow of ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]) {
      grid.appendChild(Utils.el("div", { class: "cal-dow" }, dow));
    }
    const first = new Date(year, month, 1);
    const lead = (first.getDay() + 6) % 7; // Monday-first
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    for (let i = 0; i < lead; i++) grid.appendChild(Utils.el("div", { class: "cal-cell cal-cell-empty" }));
    const today = new Date();
    for (let day = 1; day <= daysInMonth; day++) {
      const isToday = sameDay(new Date(year, month, day), today);
      grid.appendChild(
        Utils.el("div", { class: `cal-cell${isToday ? " cal-cell-today" : ""}` }, [
          Utils.el("div", { class: "cal-daynum" }, String(day)),
          ...(byDay[day] || []),
        ])
      );
    }

    host.appendChild(header);
    host.appendChild(grid);
  }

  function renderInterviews() {
    const listEl = document.getElementById("int-list");
    const calEl = document.getElementById("int-calendar");
    listEl.hidden = intMode !== "list";
    calEl.hidden = intMode !== "calendar";
    document.querySelectorAll("#int-view-toggle button").forEach((b) => b.classList.toggle("active", b.dataset.mode === intMode));
    if (intMode === "list") renderInterviewList();
    else renderCalendar();
  }

  // ---- actions --------------------------------------------------------
  async function apply(promise, okMsg) {
    try {
      data = annotateInterviews(await promise);
      renderAssessments();
      renderInterviews();
      if (okMsg) Utils.toast(okMsg, "success");
      if (typeof Dashboard !== "undefined") Dashboard.refresh();
    } catch (err) {
      Utils.toast(err.message, "error");
      refresh();
    }
  }
  function onCompleteAssessment(a, completed) {
    apply(Api.completeAssessment(a.application_id, completed), completed ? "Assessment marked completed" : "Assessment reopened");
  }
  function onSetAssessmentDue(a, value) {
    if (a.event_id) {
      apply(Api.setEventSchedule(a.event_id, value), null);
    } else {
      apply(Api.addTrackerAssessment({ application_id: a.application_id, scheduled_for: value }), "Assessment deadline set");
    }
  }
  function onSetInterviewWhen(iv, value) {
    apply(Api.setEventSchedule(iv.event_id, value), null);
  }
  function onInterviewResult(iv, result) {
    const msg = {
      offer: "Recorded: offer received",
      next_round: "Advanced to the next round",
      not_selected: "Recorded: not selected",
      pending: "Result cleared",
    }[result] || "Updated";
    apply(Api.setInterviewResult(iv.event_id, result), msg);
  }
  async function onDeleteInterview(iv) {
    const ok = await Utils.confirmDialog(
      "Delete this interview?",
      `This removes the ${iv.company} — ${iv.position} interview entry from the Tracker. This won't change the application's stage or outcome. This cannot be undone.`
    );
    if (!ok) return;
    try {
      await Api.deleteEvent(iv.event_id);
      Utils.toast("Interview removed", "success");
      await refresh();
    } catch (err) {
      Utils.toast(err.message, "error");
    }
  }

  // ---- add modal -----------------------------------------------------
  async function populateAppSelect() {
    const sel = document.getElementById("tf-app");
    sel.innerHTML = `<option value="">Loading…</option>`;
    try {
      const res = await Api.listApplications({ page_size: 200, sort_by: "company", sort_order: "asc" });
      const open = res.items.filter((a) => a.current_stage !== "Closed");
      sel.innerHTML = open
        .map((a) => `<option value="${a.id}">${Utils.escapeHtml(a.company)} — ${Utils.escapeHtml(a.position)}</option>`)
        .join("");
    } catch (err) {
      sel.innerHTML = `<option value="">Could not load applications</option>`;
    }
  }
  function openForm(mode) {
    formMode = mode;
    document.getElementById("tracker-form-title").textContent = mode === "interview" ? "Add interview" : "Add assessment";
    document.getElementById("tf-round-row").hidden = mode !== "interview";
    document.getElementById("tf-when-label").textContent = mode === "interview" ? "Date & time" : "Deadline (optional)";
    const when = document.getElementById("tf-when");
    when.type = mode === "interview" ? "datetime-local" : "date";
    when.value = "";
    document.getElementById("tf-desc").value = "";
    document.getElementById("tf-round").value = "Interview 1";
    populateAppSelect();
    Utils.openOverlay("tracker-form-overlay");
  }
  function closeForm() { Utils.closeOverlay("tracker-form-overlay"); }

  async function submitForm(e) {
    e.preventDefault();
    const btn = document.getElementById("tracker-form-submit");
    if (btn.disabled) return;
    const appId = document.getElementById("tf-app").value;
    if (!appId) { Utils.toast("Pick an application", "error"); return; }
    btn.disabled = true;
    const when = document.getElementById("tf-when").value;
    const desc = document.getElementById("tf-desc").value;
    try {
      if (formMode === "interview") {
        data = annotateInterviews(await Api.addTrackerInterview({
          application_id: Number(appId), scheduled_for: when,
          round: document.getElementById("tf-round").value, description: desc,
        }));
        Utils.toast("Interview added", "success");
      } else {
        data = annotateInterviews(await Api.addTrackerAssessment({ application_id: Number(appId), scheduled_for: when, description: desc }));
        Utils.toast("Assessment added", "success");
      }
      closeForm();
      renderAssessments();
      renderInterviews();
      if (typeof Dashboard !== "undefined") Dashboard.refresh();
    } catch (err) {
      Utils.toast(err.message, "error");
    } finally {
      btn.disabled = false;
    }
  }

  // ---- lifecycle -----------------------------------------------------
  async function refresh() {
    try {
      data = annotateInterviews(await Api.getTracker());
    } catch (err) {
      Utils.toast(err.message, "error");
      return;
    }
    renderAssessments();
    renderInterviews();
  }

  function init() {
    document.getElementById("assess-show-done").addEventListener("change", (e) => {
      showDoneAssessments = e.target.checked;
      renderAssessments();
    });
    document.querySelectorAll("#int-view-toggle button").forEach((b) => {
      b.addEventListener("click", () => { intMode = b.dataset.mode; renderInterviews(); });
    });
    document.getElementById("add-interview-btn").addEventListener("click", () => openForm("interview"));
    document.getElementById("add-assessment-btn").addEventListener("click", () => openForm("assessment"));
    document.getElementById("tracker-form-close").addEventListener("click", closeForm);
    document.getElementById("tracker-form-cancel").addEventListener("click", closeForm);
    document.getElementById("tracker-form").addEventListener("submit", submitForm);
    document.getElementById("tracker-form-overlay").addEventListener("click", (e) => {
      if (e.target.id === "tracker-form-overlay") closeForm();
    });
  }

  return { init, refresh };
})();
