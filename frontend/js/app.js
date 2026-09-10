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

/* "Update" runs whatever sync method is configured (email sync), waits for
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

function syncResultMessage(status) {
  const r = (status && status.lastSyncResult) || {};
  const parts = [];
  if (r.applicationsCreated) parts.push(`${r.applicationsCreated} new`);
  if (r.applicationsUpdated) parts.push(`${r.applicationsUpdated} updated`);
  return parts.length ? `Dashboard updated — ${parts.join(", ")}` : "Dashboard updated";
}

/* Shared by the top-bar Update button, the "Sync now" button in the Email
   status modal, and the once-a-day trigger on dashboard load. Kick off a
   sync, keep a sticky progress toast up while it runs, then refresh every
   view and resolve the toast.

   ifStale: the on-load trigger. The server decides whether to run (a method
   is configured and nothing synced today); if it declines, this is a silent
   no-op — no toast, no error. */
async function runSyncWithProgress({ onRefreshed, ifStale = false } = {}) {
  let res;
  try {
    res = await Api.runSyncNow(ifStale ? { ifStale: true } : {});
  } catch (err) {
    if (!ifStale) Utils.progressToast("Checking for updates").fail(err.message || "Update failed");
    return;
  }
  if (!res.started) {
    if (ifStale) return;   // already synced today, or manual method — nothing to show
    Utils.progressToast("Checking for updates").fail(res.error || "Could not start the update");
    return;
  }

  let firstSync = false;
  try {
    const summary = await Api.getSummary();
    firstSync = !!summary && summary.total_applications === 0;
  } catch (e) { /* non-critical — assume not the first run */ }

  const prog = Utils.progressToast(firstSync ? "Running initial data pull" : "Checking for updates");
  try {
    const status = await waitForSyncToFinish();
    await Dashboard.refresh();
    if (typeof Tracker !== "undefined") Tracker.refresh();
    GmailSync.loadStatus();
    if (onRefreshed) { try { onRefreshed(); } catch (e) {} }

    const lr = status.lastRun;
    if (lr && !lr.ok) prog.fail(lr.error || "Update finished with an error");
    else prog.finish(syncResultMessage(status), "success");
  } catch (err) {
    prog.fail(err.message || "Update failed");
  }
}

async function runDashboardUpdate() {
  const btn = document.getElementById("update-dashboard-btn");
  if (btn.disabled) return;
  btn.disabled = true;
  btn.classList.add("is-running");
  try {
    await runSyncWithProgress();
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
  AppPicker.init();
  Detail.init();
  Dashboard.init();
  Tracker.init();
  Analytics.init();
  ImportExport.init();
  GmailSync.init();

  // Once-a-day email sync, triggered by opening the dashboard. Server-gated
  // and a silent no-op unless it's actually due — see runSyncWithProgress.
  runSyncWithProgress({ ifStale: true }).catch(() => {});
}

document.addEventListener("DOMContentLoaded", bootstrap);
