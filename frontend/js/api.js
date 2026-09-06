/* Thin fetch wrapper around the local JobTrace backend. */

const Api = (() => {
  const BASE = "";

  async function request(method, path, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    let res;
    try {
      res = await fetch(BASE + path, opts);
    } catch (err) {
      throw new Error("Could not reach the local server. Is it running?");
    }
    let data = null;
    const text = await res.text();
    if (text) {
      try {
        data = JSON.parse(text);
      } catch (err) {
        data = null;
      }
    }
    if (!res.ok) {
      const message = (data && data.error) || `Request failed (${res.status})`;
      const error = new Error(message);
      error.status = res.status;
      error.payload = data;
      throw error;
    }
    return data;
  }

  function qs(params) {
    const parts = [];
    for (const [k, v] of Object.entries(params || {})) {
      if (v === undefined || v === null || v === "") continue;
      parts.push(`${encodeURIComponent(k)}=${encodeURIComponent(v)}`);
    }
    return parts.length ? `?${parts.join("&")}` : "";
  }

  return {
    getMeta: () => request("GET", "/api/meta"),
    getDistinct: () => request("GET", "/api/meta/distinct"),

    listApplications: (params) => request("GET", "/api/applications" + qs(params)),
    createApplication: (data) => request("POST", "/api/applications", data),
    getApplication: (id) => request("GET", `/api/applications/${id}`),
    updateApplication: (id, data) => request("PUT", `/api/applications/${id}`, data),
    deleteApplication: (id) => request("DELETE", `/api/applications/${id}`),

    addEvent: (applicationId, data) => request("POST", `/api/applications/${applicationId}/events`, data),
    updateEvent: (eventId, data) => request("PUT", `/api/events/${eventId}`, data),
    deleteEvent: (eventId) => request("DELETE", `/api/events/${eventId}`),

    getSummary: () => request("GET", "/api/stats/summary"),
    getAnalytics: (granularity) => request("GET", "/api/stats/analytics" + qs({ granularity })),

    getTracker: () => request("GET", "/api/tracker"),
    setEventSchedule: (eventId, scheduledFor) => request("PUT", `/api/events/${eventId}/schedule`, { scheduled_for: scheduledFor }),
    completeAssessment: (applicationId, completed) => request("POST", `/api/applications/${applicationId}/assessment-complete`, { completed }),
    setInterviewResult: (eventId, result) => request("POST", `/api/events/${eventId}/interview-result`, { result }),
    addTrackerInterview: (data) => request("POST", "/api/tracker/interviews", data),
    addTrackerAssessment: (data) => request("POST", "/api/tracker/assessments", data),

    backupDatabase: () => request("POST", "/api/backup"),

    getGmailSyncStatus: () => request("GET", "/api/gmail/sync-status"),
    getGmailUnresolved: () => request("GET", "/api/gmail/unresolved"),
    deleteUnresolved: (id) => request("DELETE", `/api/gmail/unresolved/${id}`),

    getSyncConfig: () => request("GET", "/api/sync/config"),
    updateSyncConfig: (patch) => request("PUT", "/api/sync/config", patch),
    getSyncDoctor: (force) => request("GET", "/api/sync/doctor" + (force ? "?force=1" : "")),
    testImap: () => request("POST", "/api/sync/test-imap", {}),
    runSyncNow: () => request("POST", "/api/sync/run", {}),

    importCsv: async (csvText) => {
      const res = await fetch("/api/import/csv", {
        method: "POST",
        headers: { "Content-Type": "text/csv" },
        body: csvText,
      });
      const data = await res.json();
      if (!res.ok) {
        const error = new Error(data.error || "Import failed");
        error.payload = data;
        throw error;
      }
      return data;
    },
  };
})();
