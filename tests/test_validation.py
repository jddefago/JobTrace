"""backend/validation.py — the rules every write goes through."""

import unittest

from backend import validation as v


class TextRules(unittest.TestCase):
    def test_required_text_rejects_empty(self):
        with self.assertRaises(v.ValidationError):
            v.require_text("  ", "company")

    def test_required_text_trims(self):
        self.assertEqual("Acme Corp", v.require_text("  Acme Corp ", "company"))

    def test_length_cap(self):
        with self.assertRaises(v.ValidationError):
            v.require_text("x" * 5, "company", max_len=4)


class DateRules(unittest.TestCase):
    def test_valid_date(self):
        self.assertEqual("2026-08-24", v.require_date("2026-08-24", "d"))

    def test_bad_date(self):
        with self.assertRaises(v.ValidationError):
            v.require_date("24/08/2026", "d")

    def test_optional_datetime_accepts_date_time_and_blank(self):
        self.assertEqual("", v.optional_datetime("", "when"))
        self.assertEqual("2026-08-24", v.optional_datetime("2026-08-24", "when"))
        self.assertEqual("2026-08-24T13:45", v.optional_datetime("2026-08-24T13:45", "when"))
        with self.assertRaises(v.ValidationError):
            v.optional_datetime("not-a-date", "when")


class EnumRules(unittest.TestCase):
    def test_stage_membership(self):
        v.require_stage("Assessment")
        with self.assertRaises(v.ValidationError):
            v.require_stage("Coffee Chat")

    def test_outcome_membership(self):
        v.require_outcome("Positive")
        with self.assertRaises(v.ValidationError):
            v.require_outcome("Maybe")


class PayloadRules(unittest.TestCase):
    def test_application_payload_partial_skips_absent_fields(self):
        out = v.validate_application_payload({"notes": "hi"}, partial=True)
        self.assertEqual({"notes": "hi"}, out)

    def test_application_payload_full_requires_core_fields(self):
        with self.assertRaises(v.ValidationError):
            v.validate_application_payload({"company": "X"}, partial=False)

    def test_event_payload_item_status_whitelist(self):
        v.validate_event_payload({"item_status": "passed"}, partial=True)
        with self.assertRaises(v.ValidationError):
            v.validate_event_payload({"item_status": "bogus"}, partial=True)


if __name__ == "__main__":
    unittest.main()
