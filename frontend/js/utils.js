/* Shared formatting / DOM helpers used across the app. */

const Utils = (() => {
  function todayIso() {
    const d = new Date();
    const tz = d.getTimezoneOffset() * 60000;
    return new Date(d - tz).toISOString().slice(0, 10);
  }

  function formatDate(isoStr) {
    if (!isoStr) return "—";
    const d = new Date(isoStr + "T00:00:00");
    if (isNaN(d.getTime())) return isoStr;
    return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  }

  function formatDateTime(isoStr) {
    if (!isoStr) return "—";
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return isoStr;
    return d.toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
  }

  function formatPercent(fraction) {
    if (fraction === null || fraction === undefined) return "—";
    return `${Math.round(fraction * 1000) / 10}%`;
  }

  function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") node.className = v;
      else if (k === "html") node.innerHTML = v;
      else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v);
    }
    for (const child of [].concat(children)) {
      if (child === null || child === undefined) continue;
      node.append(typeof child === "string" ? document.createTextNode(child) : child);
    }
    return node;
  }

  function debounce(fn, delay) {
    let timer = null;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), delay);
    };
  }

  function uuid() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  function stageBadgeClass(stage) {
    if (stage === "Offer") return "badge badge-stage badge-stage-offer";
    if (stage === "Closed") return "badge badge-stage badge-stage-closed";
    if (stage && stage.startsWith("Interview")) return "badge badge-stage badge-stage-interview";
    if (stage === "Final Interview") return "badge badge-stage badge-stage-interview";
    return "badge badge-stage";
  }

  function outcomeBadgeClass(outcome) {
    const map = {
      Pending: "badge-outcome-pending",
      Positive: "badge-outcome-positive",
      Negative: "badge-outcome-negative",
      Accepted: "badge-outcome-accepted",
      Withdrawn: "badge-outcome-withdrawn",
    };
    return `badge ${map[outcome] || "badge-outcome-pending"}`;
  }

  /* The "stage rail": a compact tick-progress bar showing how far an
     application has moved through the pipeline. Reads max_stage_reached
     when the application is Closed, so rejecting after Interview 2 still
     shows a rail that reached Interview 2 — not a blank one. */
  function stageRail(currentStage, maxStageReached, outcome, opts = {}) {
    const progression = (State.meta && State.meta.stage_progression) || [
      "Applied", "Screening", "Assessment", "Interview 1", "Interview 2", "Final Interview", "Offer",
    ];
    const isClosed = currentStage === "Closed";
    const effectiveStage = isClosed ? (maxStageReached && progression.includes(maxStageReached) ? maxStageReached : progression[0]) : currentStage;
    const filledIndex = Math.max(0, progression.indexOf(effectiveStage));

    let closedTone = "neutral";
    if (isClosed) {
      if (outcome === "Negative") closedTone = "negative";
      else if (outcome === "Accepted" || outcome === "Positive") closedTone = "positive";
    }

    const rail = el("div", {
      class: `stage-rail ${opts.size === "lg" ? "stage-rail-lg" : ""}`,
      title: currentStage,
    });

    progression.forEach((stageName, i) => {
      const filled = i <= filledIndex;
      const isCurrent = i === filledIndex;
      let cls = "stage-rail-tick";
      if (filled) cls += " filled";
      if (filled && isCurrent && !isClosed) cls += " current";
      if (!isClosed && isCurrent && stageName === "Offer") cls += " offer";
      if (isClosed && isCurrent) cls += ` capped-${closedTone}`;
      rail.appendChild(el("span", { class: cls }));
    });

    return rail;
  }

  function toast(message, type = "info") {
    const container = document.getElementById("toast-container");
    const node = el("div", { class: `toast ${type === "error" ? "toast-error" : type === "success" ? "toast-success" : ""}` }, message);
    container.appendChild(node);
    setTimeout(() => node.remove(), 3800);
  }

  /* A toast that stays put (animated dots, no auto-dismiss) until the caller
     resolves it. Use for a running sync: progressToast("Checking for
     updates") -> later p.finish("Dashboard updated") or p.fail(err). */
  function progressToast(label) {
    const container = document.getElementById("toast-container");
    const dots = el("span", { class: "toast-dots" }, [el("span"), el("span"), el("span")]);
    const node = el("div", { class: "toast toast-progress" }, [
      el("span", { class: "toast-progress-label" }, label),
      dots,
    ]);
    container.appendChild(node);

    let removed = false;
    const remove = () => { if (!removed) { removed = true; node.remove(); } };
    const finish = (msg, type = "success") => {
      node.className = `toast toast-${type === "error" ? "error" : "success"}`;
      node.textContent = msg;
      setTimeout(remove, 3800);
    };
    return { finish, fail: (msg) => finish(msg, "error"), remove };
  }

  function openOverlay(id) {
    document.getElementById(id).hidden = false;
  }
  function closeOverlay(id) {
    document.getElementById(id).hidden = true;
  }

  let confirmResolver = null;
  function confirmDialog(title, message) {
    document.getElementById("confirm-title").textContent = title;
    document.getElementById("confirm-message").textContent = message;
    openOverlay("confirm-overlay");
    return new Promise((resolve) => {
      confirmResolver = resolve;
    });
  }
  function resolveConfirm(result) {
    closeOverlay("confirm-overlay");
    if (confirmResolver) {
      confirmResolver(result);
      confirmResolver = null;
    }
  }

  return {
    todayIso, formatDate, formatDateTime, formatPercent, escapeHtml, el, debounce, uuid,
    stageBadgeClass, outcomeBadgeClass, stageRail, toast, progressToast, openOverlay, closeOverlay, confirmDialog, resolveConfirm,
  };
})();
