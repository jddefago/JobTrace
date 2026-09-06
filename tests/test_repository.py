"""backend/repository.py — application/event CRUD, the Tracker, and stats."""

import unittest

from backend import repository as repo
from tests.helpers import TempDBTestCase


class ApplicationCRUD(TempDBTestCase):
    def test_create_seeds_submitted_event_and_max_stage(self):
        app = self.make_application(company="Acme Corp", position="Engineer")
        self.assertEqual("Acme Corp", app["company"])
        self.assertEqual("Applied", app["current_stage"])
        self.assertEqual("Applied", app["max_stage_reached"])
        self.assertEqual(["Application Submitted"], [e["event_type"] for e in app["events"]])

    def test_create_is_idempotent_by_client_request_id(self):
        a = repo.create_application(
            {"company": "A", "position": "B", "application_date": "2026-01-01"},
            client_request_id="req-1")
        b = repo.create_application(
            {"company": "A", "position": "B", "application_date": "2026-01-01"},
            client_request_id="req-1")
        self.assertEqual(a["id"], b["id"])
        self.assertEqual(1, repo.list_applications()["total"])

    def test_stage_change_logs_event_and_advances_max_stage(self):
        app = self.make_application()
        repo.update_application_stage(app["id"], "Interview 1", "Positive")
        repo.update_application_stage(app["id"], "Closed", "Negative")
        updated = repo.get_application(app["id"])
        self.assertEqual("Closed", updated["current_stage"])
        self.assertEqual("Interview 1", updated["max_stage_reached"])  # Closed never overwrites
        types = [e["event_type"] for e in updated["events"]]
        self.assertIn("Stage Update", types)
        self.assertIn("Outcome Update", types)

    def test_delete_removes_application_and_events(self):
        app = self.make_application()
        self.assertTrue(repo.delete_application(app["id"]))
        self.assertIsNone(repo.get_application(app["id"]))
        self.assertFalse(repo.delete_application(app["id"]))

    def test_list_filters_and_search(self):
        self.make_application(company="Alpha", position="Data")
        self.make_application(company="Beta", position="Design")
        self.assertEqual(1, repo.list_applications(search="Alph")["total"])
        self.assertEqual(1, repo.list_applications(company="Beta")["total"])
        self.assertEqual(2, repo.list_applications()["total"])


class Events(TempDBTestCase):
    def test_add_event_validates_and_returns_row(self):
        app = self.make_application()
        ev = repo.add_event(app["id"], "Assessment Invitation", "2026-02-01",
                            description="Numerical test", scheduled_for="2026-02-10")
        self.assertEqual("Assessment Invitation", ev["event_type"])
        self.assertEqual("2026-02-10", ev["scheduled_for"])

    def test_add_event_unknown_application_returns_none(self):
        self.assertIsNone(repo.add_event(999, "Rejection", "2026-02-01"))

    def test_gmail_message_dedup_guard(self):
        app = self.make_application()
        repo.add_event(app["id"], "Rejection", "2026-02-01", gmail_message_id="abc123")
        self.assertTrue(repo.has_processed_gmail_message("abc123"))
        self.assertFalse(repo.has_processed_gmail_message("never-seen"))


class Tracker(TempDBTestCase):
    def _assessment_app(self):
        app = self.make_application(company="OC&C", position="Consultant")
        repo.add_event(app["id"], "Assessment Invitation", "2026-02-01")
        repo.update_application_stage(app["id"], "Assessment", "Positive")
        return app

    def test_get_tracker_lists_outstanding_assessment(self):
        self._assessment_app()
        t = repo.get_tracker()
        self.assertEqual(1, len(t["assessments"]))
        self.assertFalse(t["assessments"][0]["completed"])

    def test_complete_assessment_drops_it_and_logs_event(self):
        app = self._assessment_app()
        repo.complete_assessment(app["id"], completed=True)
        t = repo.get_tracker()
        self.assertTrue(t["assessments"][0]["completed"])
        types = [e["event_type"] for e in repo.get_application(app["id"])["events"]]
        self.assertIn("Assessment Completed", types)

    def test_add_tracker_interview_advances_stage_and_appears(self):
        app = self.make_application()
        repo.add_tracker_interview(app["id"], "2026-03-01T10:00", "Interview 1", "Panel")
        t = repo.get_tracker()
        self.assertEqual(1, len(t["interviews"]))
        self.assertEqual("Interview 1", repo.get_application(app["id"])["current_stage"])

    def test_interview_result_offer_moves_to_offer(self):
        app = self.make_application()
        iv = repo.add_tracker_interview(app["id"], "2026-03-01T10:00", "Interview 1")["interviews"][0]
        repo.set_interview_result(iv["event_id"], "offer")
        self.assertEqual("Offer", repo.get_application(app["id"])["current_stage"])

    def test_interview_result_not_selected_closes_negative(self):
        app = self.make_application()
        iv = repo.add_tracker_interview(app["id"], "2026-03-01T10:00", "Interview 1")["interviews"][0]
        repo.set_interview_result(iv["event_id"], "not_selected")
        updated = repo.get_application(app["id"])
        self.assertEqual("Closed", updated["current_stage"])
        self.assertEqual("Negative", updated["outcome"])

    def test_interview_result_next_round_creates_a_new_interview(self):
        app = self.make_application()
        iv = repo.add_tracker_interview(app["id"], "2026-03-01T10:00", "Interview 1")["interviews"][0]
        t = repo.set_interview_result(iv["event_id"], "next_round")
        self.assertEqual("Interview 2", repo.get_application(app["id"])["current_stage"])
        self.assertEqual(2, len(t["interviews"]))

    def test_next_round_past_final_is_rejected(self):
        from backend import validation
        app = self.make_application()
        repo.update_application_stage(app["id"], "Final Interview", "Positive")
        iv = repo.add_event(app["id"], "Interview Invitation", "2026-03-01")
        with self.assertRaises(validation.ValidationError):
            repo.set_interview_result(iv["id"], "next_round")


class Stats(TempDBTestCase):
    def test_summary_math(self):
        self.make_application()  # pending
        a2 = self.make_application()
        repo.update_application_stage(a2["id"], "Interview 1", "Positive")
        a3 = self.make_application()
        repo.update_application_stage(a3["id"], "Closed", "Negative")

        s = repo.get_summary_stats()
        self.assertEqual(3, s["total_applications"])
        self.assertEqual(2, s["heard_back"])          # interview + rejection
        self.assertEqual(1, s["pending"])
        self.assertEqual(1, s["negative_responses"])
        self.assertEqual(1, s["interviews"])

    def test_analytics_runs_without_error(self):
        self.make_application()
        data = repo.get_analytics("day")
        self.assertIn("funnel", data)
        self.assertIn("stage_distribution", data)

    def test_analytics_stage_summary_is_mutually_exclusive(self):
        self.make_application()                                  # -> Pending
        a2 = self.make_application()
        repo.update_application_stage(a2["id"], "Assessment", "Positive")
        a3 = self.make_application()
        repo.update_application_stage(a3["id"], "Interview 1", "Positive")
        a4 = self.make_application()
        repo.update_application_stage(a4["id"], "Interview 2", "Negative")  # rejected after interview
        a5 = self.make_application()
        repo.update_application_stage(a5["id"], "Offer", "Positive")

        summary = {row["stage"]: row["count"] for row in repo.get_analytics("day")["stage_summary"]}
        self.assertEqual({"Interview": 1, "Offer": 1, "Assessment": 1, "Negative": 1, "Pending": 1}, summary)
        self.assertEqual(5, sum(summary.values()))               # every app in exactly one bucket


class CsvRoundTrip(TempDBTestCase):
    def test_import_then_export(self):
        csv_text = (
            "company,position,location,application_date,source,job_url,"
            "job_description,stage,outcome,notes\n"
            "Acme Corp,Engineer,Amsterdam,2026-01-05,LinkedIn,,,Applied,Pending,hi\n"
        )
        rows, errors = repo.parse_and_validate_csv_import(csv_text)
        self.assertEqual([], errors)
        ids = repo.import_applications(rows)
        self.assertEqual(1, len(ids))
        out = repo.export_all_csv()
        self.assertIn("Acme Corp", out)

    def test_import_reports_bad_rows_and_inserts_nothing(self):
        bad = ("company,position,application_date\n"
               ",Trainee,2026-01-05\n")            # missing company
        rows, errors = repo.parse_and_validate_csv_import(bad)
        self.assertEqual([], rows)
        self.assertEqual(1, len(errors))


if __name__ == "__main__":
    unittest.main()
