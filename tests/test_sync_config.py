"""backend/sync/config.py — merge, clamp, secret masking, prune-to-shape."""

import json
import unittest

from backend.sync import config as sync_config
from tests.helpers import SyncConfigTestCase


class SyncConfigTests(SyncConfigTestCase):
    def test_defaults_when_no_file(self):
        cfg = sync_config.load()
        self.assertEqual("manual", cfg["method"])
        self.assertNotIn("auto", cfg)  # no timer, no interval — dropped entirely

    def test_update_merges_and_persists(self):
        sync_config.update({"method": "cli", "cli": {"command": "codex"}})
        cfg = sync_config.load()
        self.assertEqual("cli", cfg["method"])
        self.assertEqual("codex", cfg["cli"]["command"])
        self.assertEqual(30, cfg["keys"]["lookback_days"])  # untouched default kept

    def test_invalid_method_falls_back_to_manual(self):
        sync_config.update({"method": "nonsense"})
        self.assertEqual("manual", sync_config.load()["method"])

    def test_a_stale_auto_block_in_the_file_is_pruned_on_next_write(self):
        # An install upgraded from the timer era has {"auto": {...}} on disk.
        with open(sync_config.CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"method": "keys", "auto": {"enabled": True, "interval_hours": 6}}, f)
        sync_config.update({"keys": {"model": "claude-x"}})
        with open(sync_config.CONFIG_PATH) as f:
            raw = json.load(f)
        self.assertNotIn("auto", raw)
        self.assertEqual("keys", raw["method"])

    def test_get_public_masks_secrets(self):
        sync_config.update({"keys": {"anthropic_api_key": "sk-ant-secret",
                                     "gmail_app_password": "abcd efgh ijkl mnop"}})
        pub = sync_config.get_public()
        self.assertNotIn("anthropic_api_key", pub["keys"])
        self.assertTrue(pub["keys"]["anthropic_api_key_set"])
        self.assertTrue(pub["keys"]["gmail_app_password_set"])

    def test_secret_left_unchanged_when_omitted_cleared_when_sentinel(self):
        sync_config.update({"keys": {"anthropic_api_key": "sk-ant-1"}})
        sync_config.update({"keys": {"model": "claude-x"}})  # no key field
        self.assertEqual("sk-ant-1", sync_config.load()["keys"]["anthropic_api_key"])
        sync_config.update({"keys": {"anthropic_api_key": "__clear__"}})
        self.assertEqual("", sync_config.load()["keys"]["anthropic_api_key"])

    def test_stray_display_flags_are_pruned_from_the_file(self):
        sync_config.update({"keys": {"anthropic_api_key_set": True, "model": "m"}})
        with open(sync_config.CONFIG_PATH) as f:
            raw = json.load(f)
        self.assertNotIn("anthropic_api_key_set", raw["keys"])
        self.assertIn("anthropic_api_key", raw["keys"])  # the real field survives


if __name__ == "__main__":
    unittest.main()
