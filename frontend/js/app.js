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

/* "Update" runs whatever sync method is configured (Gmail sync), waits for
   it to finish, then reloads every view so the tracker reflects it. */
async function waitForSyncToFinish(maxMs = 120000) {
  const start = Date.now();
  while (Date.now() - start < maxMs) {
    const status = await Api.getGmailSyncStatus();
    if (!status.running) return status;
    await new Promise((resolve) => setTimeout(resolve, 1500));
  }
  return Api.getGmailSyncStatus();
}

async function runDashboardUpdate() {
  const btn = document.getElementById("update-dashboard-btn");
  if (btn.disabled) return;
  btn.disabled = true;
  btn.classList.add("is-running");
  try {
    const res = await Api.runSyncNow();
    if (!res.started) {
      Utils.toast(res.error || "Could not start the update", "error");
      return;
    }
    const status = await waitForSyncToFinish();
    await Dashboard.refresh();
    if (typeof Tracker !== "undefined") Tracker.refresh();
    GmailSync.loadStatus();

    const lr = status.lastRun;
    if (lr && !lr.ok) Utils.toast(lr.error || "Update finished with an error", "error");
    else Utils.toast("Dashboard updated", "success");
  } catch (err) {
    Utils.toast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.classList.remove("is-running");
  }
}

function bindUpdateButton() {
  document.getElementById("update-dashboard-icon").innerHTML = Icons.refresh;
  document.getElementById("update-dashboard-btn").addEventListener("click", runDashboardUpdate);
}

/* Dark is the default; light is an explicit, remembered per-browser choice
   (see the inline script in <head> that applies it before first paint). */
function applyTheme(theme) {
  const btn = document.getElementById("theme-toggle-btn");
  if (theme === "light") {
    document.documentElement.setAttribute("data-theme", "light");
    btn.innerHTML = Icons.sun;
    btn.title = btn.ariaLabel = "Switch to dark mode";
  } else {
    document.documentElement.removeAttribute("data-theme");
    btn.innerHTML = Icons.moon;
    btn.title = btn.ariaLabel = "Switch to light mode";
  }
}

function bindThemeToggle() {
  const current = document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
  applyTheme(current);
  document.getElementById("theme-toggle-btn").addEventListener("click", () => {
    const next = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
    try {
      localStorage.setItem("jobtrace-theme", next);
    } catch (e) {}
    applyTheme(next);
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
  bindThemeToggle();
  bindUpdateButton();
  AppForm.init();
  Detail.init();
  Dashboard.init();
  Tracker.init();
  Analytics.init();
  ImportExport.init();
  GmailSync.init();
}

document.addEventListener("DOMContentLoaded", bootstrap);
