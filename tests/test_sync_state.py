"""backend/sync/state.py — the local JSON bookkeeping every sync path shares.
Pure file I/O, so these tests just exercise the round-trips and the small
in-memory helpers."""

import os
import shutil
import tempfile
import unittest

from backend.sync import state as sync_state
from tests.helpers import redirect_sync_state, restore_sync_state


class SyncStateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="jobtrace-state-")
        self._token = redirect_sync_state(self._tmp)
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.addCleanup(restore_sync_state, self._token)

    def test_load_returns_defaults_when_no_file(self):
        state = sync_state.load_sync_state()
        self.assertIsNone(state["lastSuccessfulSync"])
        self.assertEqual([], state["processedMessageIds"])
        self.assertEqual(0, state["lastSyncResult"]["emailsReviewed"])

    def test_mark_and_check_message_processed_round_trips_through_disk(self):
        state = sync_state.load_sync_state()
        sync_state.mark_message_processed(state, "abc123")
        sync_state.mark_message_processed(state, "abc123")  # idempotent
        sync_state.save_sync_state(state)

        reloaded = sync_state.load_sync_state()
        self.assertEqual(["abc123"], reloaded["processedMessageIds"])
        self.assertTrue(sync_state.is_message_processed(reloaded, "abc123"))
        self.assertFalse(sync_state.is_message_processed(reloaded, "nope"))

    def test_record_sync_result_fills_missing_counters_and_stamps_time(self):
        state = sync_state.load_sync_state()
        sync_state.record_sync_result(state, {"emailsReviewed": 5, "applicationsCreated": 2})
        self.assertEqual(5, state["lastSyncResult"]["emailsReviewed"])
        self.assertEqual(0, state["lastSyncResult"]["rejectionsDetected"])  # defaulted
        self.assertIsNotNone(state["lastSuccessfulSync"])

    def test_unresolved_stores_and_truncates_body(self):
        items = sync_state.load_unresolved()
        short = sync_state.add_unresolved_item(items, {"gmailMessageId": "m1", "reason": "r", "body": "hi"})
        self.assertEqual("hi", short["body"])
        none_body = sync_state.add_unresolved_item(items, {"gmailMessageId": "m2", "reason": "r"})
        self.assertIsNone(none_body["body"])
        big = sync_state.add_unresolved_item(items, {"gmailMessageId": "m3", "reason": "r", "body": "x" * 20000})
        self.assertEqual(sync_state._MAX_STORED_BODY, len(big["body"]))

    def test_unresolved_add_assigns_id_then_remove(self):
        items = sync_state.load_unresolved()
        row = sync_state.add_unresolved_item(items, {"gmailMessageId": "m1", "reason": "ambiguous"})
        self.assertEqual(1, row["id"])
        second = sync_state.add_unresolved_item(items, {"gmailMessageId": "m2", "reason": "no match"})
        self.assertEqual(2, second["id"])
        sync_state.save_unresolved(items)

        items = sync_state.load_unresolved()
        self.assertEqual(2, len(items))
        self.assertTrue(sync_state.remove_unresolved_item(items, 1))
        self.assertFalse(sync_state.remove_unresolved_item(items, 999))
        self.assertEqual([2], [it["id"] for it in items])

    def test_atomic_write_leaves_no_tmp_file_behind(self):
        state = sync_state.load_sync_state()
        sync_state.save_sync_state(state)
        self.assertTrue(os.path.exists(sync_state.SYNC_STATE_PATH))
        self.assertFalse(os.path.exists(sync_state.SYNC_STATE_PATH + ".tmp"))


if __name__ == "__main__":
    unittest.main()
