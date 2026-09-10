"""backend/sync/runner.py — the dashboard-load trigger's decision logic.

We don't start real threads or shell out here; we test the two pure-ish
pieces: `autosync_due` (should opening the dashboard kick off a sync?) and
the "already running" guard on manual triggers.
"""

import datetime
import json
import os
import shutil
import tempfile
import unittest

from backend.sync import runner as runner_mod
from tests.helpers import redirect_sync_state, restore_sync_state


def _iso(dt):
    return dt.isoformat(timespec="seconds")


class AutosyncDueTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="jobtrace-runner-")
        self._token = redirect_sync_state(self._tmp)
        self._runs_token = runner_mod.RUNS_PATH
        runner_mod.RUNS_PATH = os.path.join(self._tmp, "sync_runs.json")
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.addCleanup(restore_sync_state, self._token)
        self.addCleanup(setattr, runner_mod, "RUNS_PATH", self._runs_token)

    def _write_runs(self, runs):
        os.makedirs(os.path.dirname(runner_mod.RUNS_PATH), exist_ok=True)
        with open(runner_mod.RUNS_PATH, "w", encoding="utf-8") as f:
            json.dump(runs, f)

    def _run_at(self, dt, **extra):
        entry = {"trigger": "dashboard", "ok": True, "startedAt": _iso(dt),
                 "finishedAt": _iso(dt)}
        entry.update(extra)
        self._write_runs([entry])

    # -- method gating ---------------------------------------------------
    def test_manual_method_never_triggers_on_load(self):
        self.assertFalse(runner_mod.autosync_due({"method": "manual"}))

    def test_cli_method_triggers_when_nothing_has_run(self):
        self.assertTrue(runner_mod.autosync_due({"method": "cli"}))

    def test_keys_method_triggers_when_nothing_has_run(self):
        self.assertTrue(runner_mod.autosync_due({"method": "keys"}))

    # -- the once-a-day gate -------------------------------------------
    def test_not_due_when_a_run_already_happened_today(self):
        self._run_at(datetime.datetime.now().replace(hour=0, minute=1))
        self.assertFalse(runner_mod.autosync_due({"method": "keys"}))

    def test_due_again_when_the_last_run_was_yesterday(self):
        self._run_at(datetime.datetime.now() - datetime.timedelta(days=1))
        self.assertTrue(runner_mod.autosync_due({"method": "keys"}))

    def test_a_failed_run_today_still_counts_no_retry_loop_all_day(self):
        self._run_at(datetime.datetime.now().replace(hour=8), ok=False,
                     error="sign-in expired")
        self.assertFalse(runner_mod.autosync_due({"method": "cli"}))

    def test_a_manual_run_today_also_satisfies_the_gate(self):
        self._run_at(datetime.datetime.now().replace(hour=9), trigger="manual")
        self.assertFalse(runner_mod.autosync_due({"method": "cli"}))


class ManualTriggerGuardTests(unittest.TestCase):
    def test_run_now_async_refuses_while_a_sync_is_running(self):
        runner = runner_mod.SyncRunner()
        runner._running = True
        result = runner.run_now_async(trigger="manual")
        self.assertFalse(result["started"])
        self.assertIn("already running", result["error"])


if __name__ == "__main__":
    unittest.main()
