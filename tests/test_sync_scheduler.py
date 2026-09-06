"""backend/sync/scheduler.py — the in-process timer's decision logic.

We don't start real threads or shell out here; we test the two pure-ish
pieces: `_is_due` (when the next scheduled run should fire) and the
"already running" guard on manual triggers.
"""

import datetime
import json
import os
import shutil
import tempfile
import unittest

from backend.sync import scheduler as scheduler_mod
from backend.sync import state as sync_state
from tests.helpers import redirect_sync_state, restore_sync_state

CFG = {"auto": {"interval_hours": 6}}


def _iso(dt):
    return dt.isoformat(timespec="seconds")


class IsDueTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="jobtrace-sched-")
        self._token = redirect_sync_state(self._tmp)
        self._runs_token = scheduler_mod.RUNS_PATH
        scheduler_mod.RUNS_PATH = os.path.join(self._tmp, "sync_runs.json")
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.addCleanup(restore_sync_state, self._token)
        self.addCleanup(setattr, scheduler_mod, "RUNS_PATH", self._runs_token)
        self.sched = scheduler_mod.SyncScheduler()

    def _write_runs(self, runs):
        os.makedirs(os.path.dirname(scheduler_mod.RUNS_PATH), exist_ok=True)
        with open(scheduler_mod.RUNS_PATH, "w", encoding="utf-8") as f:
            json.dump(runs, f)

    def _set_last_success(self, dt):
        state = sync_state.load_sync_state()
        state["lastSuccessfulSync"] = _iso(dt)
        sync_state.save_sync_state(state)

    def test_due_when_nothing_has_ever_run(self):
        self.assertTrue(self.sched._is_due(CFG))

    def test_not_due_right_after_a_successful_sync(self):
        self._set_last_success(datetime.datetime.now() - datetime.timedelta(hours=1))
        self.assertFalse(self.sched._is_due(CFG))

    def test_due_once_the_interval_has_elapsed(self):
        self._set_last_success(datetime.datetime.now() - datetime.timedelta(hours=7))
        self.assertTrue(self.sched._is_due(CFG))

    def test_a_failed_scheduled_run_pushes_the_next_attempt_out_a_full_interval(self):
        # Last success was long ago, but a scheduled run (which failed) just
        # finished — no fast-retry loop; wait a full interval from that.
        self._set_last_success(datetime.datetime.now() - datetime.timedelta(days=2))
        self._write_runs([{
            "trigger": "schedule", "ok": False,
            "finishedAt": _iso(datetime.datetime.now() - datetime.timedelta(minutes=10)),
        }])
        self.assertFalse(self.sched._is_due(CFG))

    def test_manual_runs_do_not_count_as_the_scheduled_marker(self):
        self._set_last_success(datetime.datetime.now() - datetime.timedelta(hours=7))
        self._write_runs([{
            "trigger": "manual", "ok": True,
            "finishedAt": _iso(datetime.datetime.now() - datetime.timedelta(minutes=1)),
        }])
        # Falls back to lastSuccessfulSync (7h ago) -> due.
        self.assertTrue(self.sched._is_due(CFG))


class ManualTriggerGuardTests(unittest.TestCase):
    def test_run_now_async_refuses_while_a_sync_is_running(self):
        sched = scheduler_mod.SyncScheduler()
        sched._running = True
        result = sched.run_now_async(trigger="manual")
        self.assertFalse(result["started"])
        self.assertIn("already running", result["error"])


if __name__ == "__main__":
    unittest.main()
