/* Dashboard summary cards, and the "All applications" dataset table (which
   now lives in the Analytics tab — filter bar, sortable/paginated table).
   The table lazy-loads the first time the Analytics tab is opened, since
   it's no longer the default-visible view. */

const Dashboard = (() => {
  let tableLoaded = false;
  let tableStale = true;

  function renderSummaryCards(stats) {
    const grid = document.getElementById("summary-cards");
    grid.innerHTML = "";

    grid.appendChild(
      Utils.el("div", { class: "stat-card accent-brand" }, [
        Utils.el("div", { class: "stat-label" }, "Total Applications"),
        Utils.el("div", { class: "stat-value" }, String(stats.total_applications)),
      ])
    );

    grid.appendChild(
      Utils.el("div", { class: "stat-card stat-card-split" }, [
        Utils.el("div", {}, [
          Utils.el("div", { class: "stat-label" }, "Heard Back"),
          Utils.el("div", { class: "stat-value" }, String(stats.heard_back)),
        ]),
        Utils.el("div", { class: "stat-breakdown" }, [
          Utils.el("div", { class: "breakdown-pill breakdown-positive" }, [
            Utils.el("span", { class: "breakdown-icon-badge" }, [iconNode("checkFilled")]),
            Utils.el("span", { class: "breakdown-count" }, String(stats.positive_responses)),
            Utils.el("span", { class: "breakdown-text" }, "Positive"),
          ]),
          Utils.el("div", { class: "breakdown-pill breakdown-negative" }, [
            Utils.el("span", { class: "breakdown-icon-badge" }, [iconNode("close")]),
            Utils.el("span", { class: "breakdown-count" }, String(stats.negative_responses)),
            Utils.el("span", { class: "breakdown-text" }, "Negative"),
          ]),
        ]),
      ])
    );

    grid.appendChild(
      Utils.el("div", { class: "stat-card accent-interview" }, [
        Utils.el("div", { class: "stat-label" }, "Interviews"),
        Utils.el("div", { class: "stat-value" }, String(stats.interviews)),
      ])
    );

    grid.appendChild(
      Utils.el("div", { class: "stat-card accent-offer" }, [
        Utils.el("div", { class: "stat-label" }, "Offers"),
        Utils.el("div", { class: "stat-value" }, String(stats.offers)),
      ])
    );
  }

  function populateFilterSelects() {
    const stageSel = document.getElementById("filter-stage");
    stageSel.innerHTML = `<option value="">All stages</option>` + State.meta.stages.map((s) => `<option value="${s}">${s}</option>`).join("");
    const outcomeSel = document.getElementById("filter-outcome");
    outcomeSel.innerHTML = `<option value="">All outcomes</option>` + State.meta.outcomes.map((o) => `<option value="${o}">${o}</option>`).join("");
  }

  function populateDistinctFilters(distinct) {
    const companySel = document.getElementById("filter-company");
    const currentCompany = companySel.value;
    companySel.innerHTML = `<option value="">All companies</option>` + distinct.companies.map((c) => `<option value="${Utils.escapeHtml(c)}">${Utils.escapeHtml(c)}</option>`).join("");
    companySel.value = currentCompany;
  }

  function renderTable(result) {
    const tbody = document.getElementById("applications-tbody");
    tbody.innerHTML = "";
    const emptyState = document.getElementById("table-empty-state");

    if (result.items.length === 0) {
      emptyState.hidden = false;
    } else {
      emptyState.hidden = true;
    }

    for (const app of result.items) {
      const stageCell = Utils.el("td", {}, [
        Utils.el("div", { class: "stage-cell" }, [
          Utils.stageRail(app.current_stage, app.max_stage_reached, app.outcome),
          Utils.el("span", { class: "stage-cell-label" }, app.current_stage),
        ]),
      ]);
      const tr = Utils.el("tr", { onclick: () => Detail.open(app.id) }, [
        Utils.el("td", { class: "cell-primary" }, app.company),
        Utils.el("td", {}, app.position),
        Utils.el("td", { class: "cell-muted" }, app.location || "—"),
        Utils.el("td", { class: "cell-mono cell-muted" }, Utils.formatDate(app.application_date)),
        stageCell,
        Utils.el("td", {}, [Utils.el("span", { class: Utils.outcomeBadgeClass(app.outcome) }, app.outcome)]),
        Utils.el("td", { class: "cell-muted" }, app.source || "—"),
        Utils.el("td", { class: "cell-days cell-mono" }, String(app.days_since_application ?? "—")),
      ]);
      tbody.appendChild(tr);
    }

    const start = result.total === 0 ? 0 : (result.page - 1) * result.page_size + 1;
    const end = Math.min(result.total, result.page * result.page_size);
    document.getElementById("pagination-info").textContent = `${start}–${end} of ${result.total}`;
    document.getElementById("page-indicator").textContent = `Page ${result.page} of ${Math.max(1, Math.ceil(result.total / result.page_size))}`;
    document.getElementById("prev-page-btn").disabled = result.page <= 1;
    document.getElementById("next-page-btn").disabled = result.page * result.page_size >= result.total;

    updateSortHeaders();
  }

  function updateSortHeaders() {
    document.querySelectorAll("#applications-table thead th[data-sort]").forEach((th) => {
      th.classList.toggle("sorted", th.dataset.sort === State.dashboard.sort_by);
      th.classList.toggle("asc", th.dataset.sort === State.dashboard.sort_by && State.dashboard.sort_order === "asc");
    });
  }

  async function loadTable() {
    try {
      const d = State.dashboard;
      const result = await Api.listApplications({
        search: d.search, stage: d.stage, outcome: d.outcome, source: d.source,
        company: d.company, location: d.location, date_from: d.date_from, date_to: d.date_to,
        sort_by: d.sort_by, sort_order: d.sort_order, page: d.page, page_size: d.page_size,
      });
      renderTable(result);
    } catch (err) {
      Utils.toast(err.message, "error");
    }
  }

  async function loadSummary() {
    try {
      const stats = await Api.getSummary();
      renderSummaryCards(stats);
    } catch (err) {
      Utils.toast(err.message, "error");
    }
  }

  async function loadDistinct() {
    try {
      const distinct = await Api.getDistinct();
      populateDistinctFilters(distinct);
    } catch (err) {
      /* non-critical */
    }
  }

  function showTableIfActive() {
    const view = document.getElementById("view-analytics");
    if (view && view.classList.contains("active") && (!tableLoaded || tableStale)) {
      tableLoaded = true;
      tableStale = false;
      return Promise.all([loadTable(), loadDistinct()]);
    }
    return Promise.resolve();
  }

  async function refresh() {
    tableStale = true;
    const tasks = [loadSummary(), showTableIfActive()];
    if (typeof Analytics !== "undefined") tasks.push(Analytics.refresh());
    await Promise.all(tasks);
  }

  function resetToFirstPage() {
    State.dashboard.page = 1;
    loadTable();
  }

  function clearFilters() {
    State.dashboard.search = "";
    State.dashboard.stage = "";
    State.dashboard.outcome = "";
    State.dashboard.source = "";
    State.dashboard.company = "";
    State.dashboard.location = "";
    State.dashboard.date_from = "";
    State.dashboard.date_to = "";
    State.dashboard.page = 1;

    document.getElementById("search-input").value = "";
    document.getElementById("filter-stage").value = "";
    document.getElementById("filter-outcome").value = "";
    document.getElementById("filter-company").value = "";
    document.getElementById("filter-date-from").value = "";
    document.getElementById("filter-date-to").value = "";

    loadTable();
  }

  function bindEvents() {
    const debouncedSearch = Utils.debounce((value) => {
      State.dashboard.search = value;
      resetToFirstPage();
    }, 300);

    document.getElementById("search-input").addEventListener("input", (e) => debouncedSearch(e.target.value));

    const filterMap = {
      "filter-stage": "stage",
      "filter-outcome": "outcome",
      "filter-company": "company",
      "filter-date-from": "date_from",
      "filter-date-to": "date_to",
    };
    for (const [elId, key] of Object.entries(filterMap)) {
      document.getElementById(elId).addEventListener("change", (e) => {
        State.dashboard[key] = e.target.value;
        resetToFirstPage();
      });
    }

    document.getElementById("clear-filters-btn").addEventListener("click", clearFilters);

    document.querySelectorAll("#applications-table thead th[data-sort]").forEach((th) => {
      th.addEventListener("click", () => {
        const col = th.dataset.sort;
        if (State.dashboard.sort_by === col) {
          State.dashboard.sort_order = State.dashboard.sort_order === "asc" ? "desc" : "asc";
        } else {
          State.dashboard.sort_by = col;
          State.dashboard.sort_order = "desc";
        }
        loadTable();
      });
    });

    document.getElementById("prev-page-btn").addEventListener("click", () => {
      if (State.dashboard.page > 1) {
        State.dashboard.page -= 1;
        loadTable();
      }
    });
    document.getElementById("next-page-btn").addEventListener("click", () => {
      State.dashboard.page += 1;
      loadTable();
    });
  }

  function init() {
    populateFilterSelects();
    bindEvents();
    loadSummary();
  }

  return { init, refresh, loadTable, showTableIfActive };
})();
