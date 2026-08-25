/* Analytics view: a 3-way chart switcher (Daily Activity / Stage Distribution /
   Progress) plus the Source performance table. The three tabs share one fetch
   of summary stats + daily counts, cached client-side, so switching tabs or
   the date range is instant with no extra network round-trip. */

const Analytics = (() => {
  const TAB_META = {
    daily: {
      title: "Applications per day",
      subtitle: "Number of job applications submitted each day",
    },
    donut: {
      title: "Stage Distribution",
      subtitle: "Where every application currently stands, at a glance",
    },
    journey: {
      title: "Progress Toward Offers",
      subtitle: "Track how applications move through your pipeline",
    },
  };

  let currentTab = "daily";
  let currentRange = 14;
  let cachedStats = null;
  let cachedDayBuckets = null;
  let cachedStageSummary = null;

  // Current-state buckets shown in the Stage Distribution donut. Unlike the
  // funnel below, these are mutually exclusive (every application lands in
  // exactly one), so the counts always sum to the total.
  const STAGE_SUMMARY_META = {
    Interview: { color: "var(--interview)", hex: "#a48de0" },
    Offer: { color: "var(--brass)", hex: "#d9a441" },
    Assessment: { color: "var(--info)", hex: "#5b9fe0" },
    Negative: { color: "var(--negative)", hex: "#e2694f" },
    Pending: { color: "var(--pending)", hex: "#8b93a8" },
  };

  function isoLocal(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }

  function shortLabel(iso) {
    const d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }

  function buildDailyRange(dayBuckets, rangeDays) {
    const map = {};
    for (const b of dayBuckets) map[b.period] = b.count;
    const today = new Date();
    const points = [];
    for (let i = rangeDays - 1; i >= 0; i--) {
      const d = new Date(today.getFullYear(), today.getMonth(), today.getDate() - i);
      const iso = isoLocal(d);
      points.push({ date: iso, label: shortLabel(iso), count: map[iso] || 0 });
    }
    return points;
  }

  function funnelSteps(stats) {
    const total = stats.total_applications || 0;
    const raw = [
      { key: "applied", label: "Applied", icon: "send", color: "var(--brass)", hex: "#d9a441", count: total },
      { key: "heard_back", label: "Heard back", icon: "chat", color: "var(--info)", hex: "#5b9fe0", count: stats.heard_back },
      { key: "positive", label: "Positive", icon: "check", color: "var(--positive)", hex: "#4fbf9f", count: stats.positive_responses },
      { key: "interview", label: "Interview", icon: "calendar", color: "var(--interview)", hex: "#a48de0", count: stats.interviews },
      { key: "offer", label: "Offer", icon: "star", color: "var(--brass)", hex: "#d9a441", count: stats.offers },
    ];
    return raw.map((s, i) => ({
      ...s,
      pct: total > 0 ? s.count / total : 0,
      filled: s.count > 0,
      dashedIn: i === raw.length - 1, // the stretch toward Offer always reads as the goal, not a "done" step
    }));
  }

  // ---------------------------------------------------------------------
  // Tab: Daily Activity
  // ---------------------------------------------------------------------
  function renderDailyTab() {
    const points = buildDailyRange(cachedDayBuckets, currentRange);
    const total = points.reduce((s, p) => s + p.count, 0);
    const avg = points.length ? total / points.length : 0;
    const best = points.reduce((max, p) => Math.max(max, p.count), 0);

    const statsRow = document.getElementById("daily-mini-stats");
    statsRow.innerHTML = "";
    const miniStats = [
      { icon: "doc", label: "Total this period", value: String(total) },
      { icon: "trending", label: "Daily avg", value: (Math.round(avg * 10) / 10).toString() },
      { icon: "trophy", label: "Best day", value: `${best} app${best === 1 ? "" : "s"}` },
    ];
    for (const m of miniStats) {
      statsRow.appendChild(
        Utils.el("div", { class: "mini-stat" }, [
          Utils.el("div", { class: "mini-stat-icon" }, [iconNode(m.icon)]),
          Utils.el("div", {}, [
            Utils.el("div", { class: "mini-stat-label" }, m.label),
            Utils.el("div", { class: "mini-stat-value" }, m.value),
          ]),
        ])
      );
    }

    Charts.renderDailyBars(document.getElementById("chart-daily-bars"), points);
  }

  // ---------------------------------------------------------------------
  // Tab: Stage Distribution (donut)
  // ---------------------------------------------------------------------
  function renderDonutTab() {
    const total = cachedStats.total_applications || 0;
    const rows = cachedStageSummary || [];

    // These buckets are already mutually exclusive by construction (each
    // application's *current* stage/outcome puts it in exactly one), so the
    // arc share and the legend percentage are the same number here -- no
    // separate normalization needed, unlike a cumulative funnel.
    const segments = rows.map((r) => {
      const meta = STAGE_SUMMARY_META[r.stage] || { hex: "#8b93a8" };
      return {
        label: r.stage,
        count: r.count,
        pct: total > 0 ? r.count / total : 0,
        color: meta.hex,
        arcValue: r.count,
      };
    });

    Charts.renderDonut(
      document.getElementById("chart-donut"),
      document.getElementById("donut-legend"),
      segments,
      { label: "Total", value: total, sub: "Applications" }
    );

    const insight = document.getElementById("donut-insight");
    insight.innerHTML = "";
    const interviewRow = rows.find((r) => r.stage === "Interview");
    const interviewPct = total > 0 && interviewRow ? interviewRow.count / total : 0;
    insight.appendChild(iconNode("bulb", "insight-icon"));
    insight.appendChild(
      Utils.el("span", {}, [
        Utils.el("strong", {}, Utils.formatPercent(interviewPct)),
        " of your applications are currently at the interview stage.",
      ])
    );
  }

  // ---------------------------------------------------------------------
  // Tab: Progress journey
  // ---------------------------------------------------------------------
  function renderJourneyTab() {
    const steps = funnelSteps(cachedStats);
    Charts.renderJourney(document.getElementById("chart-journey"), steps);
  }

  function renderActiveTab() {
    if (currentTab === "daily") renderDailyTab();
    else if (currentTab === "donut") renderDonutTab();
    else if (currentTab === "journey") renderJourneyTab();
  }

  function switchTab(tab) {
    currentTab = tab;
    document.querySelectorAll(".chart-tab").forEach((btn) => btn.classList.toggle("active", btn.dataset.chart === tab));
    document.querySelectorAll(".chart-view").forEach((view) => view.classList.toggle("active", view.id === `chart-view-${tab}`));
    document.getElementById("chart-switcher-title").textContent = TAB_META[tab].title;
    document.getElementById("chart-switcher-subtitle").textContent = TAB_META[tab].subtitle;
    renderActiveTab();
  }

  function switchRange(range) {
    currentRange = range;
    document.querySelectorAll("#range-toggle button").forEach((btn) => btn.classList.toggle("active", Number(btn.dataset.range) === range));
    renderDailyTab();
  }

  function renderSourceTable(rows) {
    const tbody = document.getElementById("source-performance-tbody");
    tbody.innerHTML = "";
    if (rows.length === 0) {
      tbody.appendChild(Utils.el("tr", {}, [Utils.el("td", { colspan: "5" }, "No data yet.")]));
      return;
    }
    for (const r of rows) {
      tbody.appendChild(
        Utils.el("tr", {}, [
          Utils.el("td", { class: "cell-primary" }, r.source),
          Utils.el("td", {}, String(r.total)),
          Utils.el("td", {}, Utils.formatPercent(r.response_rate)),
          Utils.el("td", {}, Utils.formatPercent(r.positive_response_rate)),
          Utils.el("td", {}, Utils.formatPercent(r.interview_rate)),
        ])
      );
    }
  }

  async function refresh() {
    try {
      const [stats, analytics] = await Promise.all([Api.getSummary(), Api.getAnalytics("day")]);
      cachedStats = stats;
      cachedDayBuckets = analytics.applications_over_time;
      cachedStageSummary = analytics.stage_summary;
      renderSourceTable(analytics.source_performance);
      renderActiveTab();
    } catch (err) {
      Utils.toast(err.message, "error");
    }
  }

  function bindEvents() {
    document.querySelectorAll(".chart-tab").forEach((btn) => {
      btn.addEventListener("click", () => switchTab(btn.dataset.chart));
    });
    document.querySelectorAll("#range-toggle button").forEach((btn) => {
      btn.addEventListener("click", () => switchRange(Number(btn.dataset.range)));
    });
  }

  function init() {
    bindEvents();
    refresh();
  }

  return { init, refresh };
})();
