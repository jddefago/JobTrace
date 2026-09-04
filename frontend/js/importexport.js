/* Export dropdown, database backup, and CSV import. */

const ImportExport = (() => {
  function toggleMenu(force) {
    const menu = document.getElementById("export-menu");
    menu.classList.toggle("open", force !== undefined ? force : !menu.classList.contains("open"));
  }

  async function onBackup() {
    toggleMenu(false);
    try {
      const result = await Api.backupDatabase();
      Utils.toast(`Backup saved: backups/${result.filename}`, "success");
    } catch (err) {
      Utils.toast(err.message, "error");
    }
  }

  function showImportResult(html) {
    document.getElementById("import-result-body").innerHTML = html;
    Utils.openOverlay("import-result-overlay");
  }

  async function onImportFile(evt) {
    toggleMenu(false);
    const file = evt.target.files[0];
    evt.target.value = "";
    if (!file) return;

    const text = await file.text();
    try {
      const result = await Api.importCsv(text);
      showImportResult(`<p><strong>${result.inserted}</strong> application(s) imported successfully.</p>`);
      if (typeof Dashboard !== "undefined") Dashboard.refresh();
    } catch (err) {
      if (err.payload && err.payload.row_errors) {
        const rows = err.payload.row_errors
          .map((e) => `<li>Row ${e.row}: ${Utils.escapeHtml(e.message)}</li>`)
          .join("");
        showImportResult(
          `<p>Import cancelled — fix the following and try again. No rows were inserted.</p><ul>${rows}</ul>`
        );
      } else {
        Utils.toast(err.message, "error");
      }
    }
  }

  function bindEvents() {
    document.getElementById("export-btn").innerHTML = Icons.download;
    document.getElementById("export-btn").addEventListener("click", () => toggleMenu());
    document.addEventListener("click", (e) => {
      if (!document.getElementById("export-dropdown").contains(e.target)) toggleMenu(false);
    });
    document.getElementById("export-csv").addEventListener("click", () => toggleMenu(false));
    document.getElementById("export-json").addEventListener("click", () => toggleMenu(false));
    document.getElementById("backup-db").addEventListener("click", onBackup);
    document.getElementById("import-csv-input").addEventListener("change", onImportFile);

    document.getElementById("import-result-close").addEventListener("click", () => Utils.closeOverlay("import-result-overlay"));
    document.getElementById("import-result-ok").addEventListener("click", () => Utils.closeOverlay("import-result-overlay"));
    document.getElementById("import-result-overlay").addEventListener("click", (e) => {
      if (e.target.id === "import-result-overlay") Utils.closeOverlay("import-result-overlay");
    });
  }

  function init() {
    bindEvents();
  }

  return { init };
})();
