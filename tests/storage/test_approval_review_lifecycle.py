
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from resource_planning_agent.storage.approval_review_store import (
    initialize_review_case_store,
    save_approval_review_case,
    load_approval_review_case,
    get_open_review_case_for_plan,
    complete_approval_review_case,
)


def make_review_case():
    return {
        "case_id": "CASE-701",
        "plan_id": "PLAN-701",
        "created_at": "2026-11-25T10:00:00+00:00",
        "case_status": "awaiting_manual_review",
        "consistency_status": "missing_registry",
        "recommended_action": "investigate_approval_evidence",
        "reason": "Independent approval record missing.",
        "required_evidence": [
            "Original approval records"
        ],
        "review_steps": [
            "Investigate inconsistency"
        ],
        "manual_review_required": True,
        "automatic_recovery_allowed": False,
        "can_proceed_to_preflight": False,
        "approval_granted": False,
        "registry_modified": False,
        "reservations_created": False,
    }


class TestApprovalReviewLifecycle(unittest.TestCase):

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        db_patch = patch(
            "resource_planning_agent.storage.database.DB_PATH",
            Path(temporary.name) / "review_lifecycle.db",
        )

        db_patch.start()
        self.addCleanup(db_patch.stop)

        initialize_review_case_store()

        self.review_case = make_review_case()
        save_approval_review_case(self.review_case)

    def test_complete_review_case_success(self):
        result = complete_approval_review_case(
            "CASE-701",
            "manager_project",
            "Evidence reviewed; further approval required.",
        )

        self.assertEqual(
            result["case_status"],
            "reviewed",
        )
        self.assertEqual(
            result["reviewed_by"],
            "manager_project",
        )
        self.assertIn("reviewed_at", result)

        stored = load_approval_review_case("CASE-701")
        self.assertEqual(stored, result)

        self.assertIsNone(
            get_open_review_case_for_plan("PLAN-701")
        )

    def test_review_does_not_grant_approval(self):
        result = complete_approval_review_case(
            "CASE-701",
            "manager_project",
            "Approval evidence unavailable.",
        )

        self.assertFalse(result["approval_granted"])
        self.assertFalse(result["registry_modified"])
        self.assertFalse(result["reservations_created"])
        self.assertFalse(
            result["can_proceed_to_preflight"]
        )

    def test_second_completion_rejected(self):
        complete_approval_review_case(
            "CASE-701",
            "manager_project",
            "First review completed.",
        )

        with self.assertRaises(ValueError):
            complete_approval_review_case(
                "CASE-701",
                "manager_platform",
                "Second review attempt.",
            )

        stored = load_approval_review_case("CASE-701")
        self.assertEqual(
            stored["reviewed_by"],
            "manager_project",
        )

    def test_unknown_case_rejected(self):
        with self.assertRaises(ValueError):
            complete_approval_review_case(
                "CASE-NOT-FOUND",
                "manager_project",
                "Review note.",
            )

    def test_empty_review_note_rejected(self):
        with self.assertRaises(ValueError):
            complete_approval_review_case(
                "CASE-701",
                "manager_project",
                "   ",
            )

        stored = load_approval_review_case("CASE-701")
        self.assertEqual(
            stored["case_status"],
            "awaiting_manual_review",
        )


if __name__ == "__main__":
    unittest.main()
