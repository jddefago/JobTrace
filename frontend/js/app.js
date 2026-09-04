/* App bootstrap: shared state, tab navigation, initial data load. */

const State = {
  meta: null,
  dashboard: {
    search: "", stage: "", outcome: "", source: "", company: "", location: "",
    date_from: "", date_to: "",
    sort_by: "application_date", sort_order: "desc",
    page: 1, page_size: 50,
  },
};

function switchView(viewName) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === viewName));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${viewName}`));
  if (viewName === "analytics") Dashboard.showTableIfActive();
  if (viewName === "tracker" && typeof Tracker !== "undefined") Tracker.refresh();
}

function bindTabs() {
  document.querySelectorAll("#main-tabs .tab").forEach((tab) => {
    tab.addEventListener("click", () => switchView(tab.dataset.view));
  });
}

async function bootstrap() {
  try {
    State.meta = await Api.getMeta();
  } catch (err) {
    Utils.toast("Could not reach the JobTrace server at http://localhost:8766 — start it with start.command (macOS) or start.bat (Windows).", "error");
    return;
  }

  bindTabs();
  AppForm.init();
  Detail.init();
  Dashboard.init();
  Tracker.init();
  Analytics.init();
  ImportExport.init();
  GmailSync.init();
}

document.addEventListener("DOMContentLoaded", bootstrap);
