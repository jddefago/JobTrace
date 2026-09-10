"""Gmail-sync runner + the dashboard-load trigger.

Earlier versions ran the sync on a schedule -- first an OS-level launchd /
Task Scheduler job, then an in-server timer. Neither survives real machine
use: people restart, sleep, and shut down. There is no schedule now. A sync
fires when the dashboard is opened, at most once per calendar day
(`autosync_due`), for whichever method is configured. The tracker is only
useful when you look at it, and that's exactly when it refreshes. Every
failure is surfaced in the dashboard instead of a logfile nobody opens.

Two execution paths, by config method:
  "cli"  -> shell out to the `claude` / `codex` CLI with GMAIL_SYNC_TASK_PROMPT.md
  "keys" -> run backend/sync/agent.py in-process (IMAP or Google API + your key)
"""

import datetime
import json
import os
import re
import subprocess
import sys
import threading

from .. import database
from . import config as sync_config, doctor as sync_doctor

BASE_DIR = database.BASE_DIR

# The server runs windowless (pythonw), but on Windows a child process
# spawned from it still gets its own console, which flashes on screen for
# the duration of the CLI sync run. Suppress it.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
TASK_PROMPT_PATH = os.path.join(BASE_DIR, "GMAIL_SYNC_TASK_PROMPT.md")
RUNS_PATH = os.path.join(database.DATA_DIR, "sync_runs.json")
SYNC_LOG_DIR = os.path.join(database.DATA_DIR, "sync_logs")

CLI_TIMEOUT_SECONDS = 1800
_CLAUDE_BASE_TOOLS = (
    "Read Write Edit Glob Grep Bash(python:*) Bash(python3:*) "
    "mcp__claude_ai_Gmail__search_threads mcp__claude_ai_Gmail__get_thread "
    "mcp__claude_ai_Gmail__get_message mcp__claude_ai_Gmail__list_labels"
)


def _claude_allowed_tools(cfg):
    # WebSearch drives GMAIL_SYNC.md's location/job_url/source enrichment. It's
    # no more powerful than the Bash(python:*) already granted for DB writes,
    # so it doesn't widen the prompt-injection surface — but it's still gated
    # on the same "enable_web_search" toggle the keys path uses.
    tools = _CLAUDE_BASE_TOOLS
    if cfg.get("keys", {}).get("enable_web_search", True):
        tools += " WebSearch"
    return tools


_AUTH_FAIL_RE = re.compile(
    r"OAuth (access )?token (has )?expired|authentication_error|Failed to authenticate"
    r"|401 .*(auth|unauthor)|Please run .*login|Not logged in|Invalid credentials",
    re.I,
)


# ---------------------------------------------------------------------------
# Run history (small ring buffer the dashboard reads)
# ---------------------------------------------------------------------------

def _load_runs():
    try:
        with open(RUNS_PATH, "r", encoding="utf-8") as f:
            return json.load(f) or []
    except (OSError, json.JSONDecodeError):
        return []


def _record_run(entry):
    runs = _load_runs()
    runs.append(entry)
    runs = runs[-20:]
    database.ensure_data_dirs()
    tmp = RUNS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(runs, f, indent=2, ensure_ascii=False)
    os.replace(tmp, RUNS_PATH)


def last_run():
    runs = _load_runs()
    return runs[-1] if runs else None


def synced_today(now=None):
    """True if the most recent run (any trigger, success or failure) started
    on today's local calendar date."""
    lr = last_run()
    if not lr:
        return False
    stamp = lr.get("startedAt") or lr.get("finishedAt")
    if not stamp:
        return False
    try:
        return datetime.date.fromisoformat(stamp[:10]) == (now or datetime.datetime.now()).date()
    except ValueError:
        return False


def autosync_due(cfg, now=None):
    """Should opening the dashboard kick off a sync? Only when a non-manual
    method is configured and nothing has run yet today -- so a broken
    sign-in gets one attempt a day, surfaced in the dashboard, not one per
    page load."""
    return cfg.get("method") in ("cli", "keys") and not synced_today(now=now)


# ---------------------------------------------------------------------------
# Execution paths
# ---------------------------------------------------------------------------

def _run_cli(cfg, log):
    name = cfg["cli"]["command"]
    binary = sync_doctor._find_cli(name)
    if not binary:
        return {"ok": False, "error": f"The {name} CLI was not found. Install it or add it to your PATH."}

    try:
        with open(TASK_PROMPT_PATH, "r", encoding="utf-8") as f:
            prompt = f.read()
    except OSError as e:
        return {"ok": False, "error": f"Couldn't read GMAIL_SYNC_TASK_PROMPT.md: {e}"}

    if name == "claude":
        argv = [binary, "-p", "--output-format", "text", "--allowedTools", _claude_allowed_tools(cfg)]
    else:  # codex
        argv = [binary, "exec"]

    os.makedirs(SYNC_LOG_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(SYNC_LOG_DIR, f"sync_{name}_{ts}.log")

    log(f"running: {name} (timeout {CLI_TIMEOUT_SECONDS}s)")
    try:
        proc = subprocess.run(
            argv, input=prompt, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            cwd=BASE_DIR, timeout=CLI_TIMEOUT_SECONDS,
            creationflags=_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"The {name} sync run timed out after {CLI_TIMEOUT_SECONDS//60} minutes.",
                "log_path": log_path}
    except OSError as e:
        return {"ok": False, "error": f"Could not start {name}: {e}"}

    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(output)
    except OSError:
        pass

    if _AUTH_FAIL_RE.search(output):
        return {"ok": False, "log_path": log_path,
                "error": f"The {name} CLI's sign-in has expired, or Gmail isn't connected to it. "
                         f"Run `{name}` in a terminal, sign in, and make sure a Gmail connector is added."}
    if proc.returncode != 0:
        tail = output.strip().splitlines()[-1] if output.strip() else "no output"
        return {"ok": False, "error": f"{name} exited with status {proc.returncode}: {tail}", "log_path": log_path}
    return {"ok": True, "log_path": log_path}


def _run_manual_fallback(cfg, log):
    """method == "manual" (no automation chosen in Settings yet, the default).
    A manual trigger -- the Update button, or "Sync now" -- should still do
    something rather than just refuse: prefer an AI-assistant CLI if one is
    on PATH (that's what "manual" is describing -- ask your assistant), else
    fall back to the keys path, which will pick up a saved Anthropic API key
    (or ANTHROPIC_API_KEY) plus Gmail credentials if those are configured."""
    for name in ("claude", "codex"):
        if sync_doctor._find_cli(name):
            log(f"no sync method configured in Settings — found the {name} CLI, using it")
            return _run_cli({**cfg, "cli": {"command": name}}, log)
    log("no sync method configured and no AI assistant CLI on PATH — trying a saved API key")
    return _run_keys(cfg, log)


def _run_keys(cfg, log):
    from . import agent as sync_agent
    keys = dict(cfg.get("keys", {}))
    try:
        merged = sync_agent.load_config()
    except sync_agent.SyncConfigError as e:
        return {"ok": False, "error": str(e)}
    merged.update({k: v for k, v in keys.items() if v not in (None, "")})
    res = sync_agent.run_job(config=merged, log=log)
    return {
        "ok": res["ok"],
        "error": res["error"],
        "log_path": res.get("log_path"),
        "report": res.get("report"),
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class SyncRunner:
    def __init__(self):
        self._run_lock = threading.Lock()
        self._running = False
        self._log_lines = []

    @property
    def is_running(self):
        return self._running

    # -- run one sync --------------------------------------------------
    def run_now(self, trigger="manual"):
        with self._run_lock:
            if self._running:
                return {"ok": False, "error": "A sync is already running.", "busy": True}
            self._running = True
        started = datetime.datetime.now()
        self._log_lines = []

        def log(msg):
            self._log_lines.append(f"{datetime.datetime.now().strftime('%H:%M:%S')} {msg}")

        cfg = sync_config.load()
        try:
            if cfg["method"] == "cli":
                outcome = _run_cli(cfg, log)
            elif cfg["method"] == "keys":
                outcome = _run_keys(cfg, log)
            else:
                outcome = _run_manual_fallback(cfg, log)
        except Exception as e:
            outcome = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        finally:
            self._running = False

        entry = {
            "trigger": trigger,
            "method": cfg["method"],
            "startedAt": started.isoformat(timespec="seconds"),
            "finishedAt": datetime.datetime.now().isoformat(timespec="seconds"),
            "ok": bool(outcome.get("ok")),
            "error": outcome.get("error"),
            "logPath": (os.path.relpath(outcome["log_path"], BASE_DIR)
                        if outcome.get("log_path") else None),
        }
        _record_run(entry)
        return {**entry, "busy": False}

    def run_now_async(self, trigger="manual"):
        with self._run_lock:
            if self._running:
                return {"started": False, "error": "A sync is already running."}
        threading.Thread(target=self.run_now, kwargs={"trigger": trigger},
                         name="jobtrace-sync-manual", daemon=True).start()
        return {"started": True}


runner = SyncRunner()
