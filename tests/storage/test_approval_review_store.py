
import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from resource_planning_agent.approvals.approval_review_case import (
    prepare_approval_review_case,
)

from resource_planning_agent.storage.approval_review_store import (
    initialize_review_case_store,
    save_approval_review_case,
    load_approval_review_case,
)


def make_assessment():
    return {
        "plan_id": "PLAN-501",
        "consistency_status": "missing_registry",
        "recommended_action": "investigate_approval_evidence",
        "reason": "Independent approval record missing.",
        "manual_review_required": True,
        "automatic_recovery_allowed": False,
        "can_proceed_to_preflight": False,
    }


class TestApprovalReviewStore(unittest.TestCase):

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        db_patch = patch(
            "resource_planning_agent.storage.database.DB_PATH",
            Path(temporary.name) / "review_cases.db",
        )

        db_patch.start()
        self.addCleanup(db_patch.stop)

        initialize_review_case_store()

        with patch(
            "resource_planning_agent.approvals."
            "approval_review_case.assess_approval_recovery",
            return_value=make_assessment(),
        ):
            self.review_case = (
                prepare_approval_review_case("PLAN-501")
            )

    def test_save_and_load_review_case(self):
        result = save_approval_review_case(
            self.review_case
        )

        self.assertTrue(result["saved"])

        stored = load_approval_review_case(
            self.review_case["case_id"]
        )

        self.assertEqual(stored, self.review_case)
        self.assertFalse(stored["approval_granted"])
        self.assertFalse(stored["reservations_created"])

    def test_duplicate_case_rejected(self):
        save_approval_review_case(self.review_case)

        with self.assertRaises(sqlite3.IntegrityError):
            save_approval_review_case(
                self.review_case
            )

        stored = load_approval_review_case(
            self.review_case["case_id"]
        )

        self.assertEqual(stored, self.review_case)

    def test_unsafe_case_rejected(self):
        unsafe = copy.deepcopy(self.review_case)

        unsafe["approval_granted"] = True

        with self.assertRaises(ValueError):
            save_approval_review_case(unsafe)

        self.assertIsNone(
            load_approval_review_case(
                unsafe["case_id"]
            )
        )

    def test_missing_case_returns_none(self):
        result = load_approval_review_case(
            "CASE-NOT-FOUND"
        )

        self.assertIsNone(result)

    def test_schema_initialization_is_idempotent(self):
        initialize_review_case_store()
        initialize_review_case_store()

        save_approval_review_case(self.review_case)

        stored = load_approval_review_case(
            self.review_case["case_id"]
        )

        self.assertIsNotNone(stored)


if __name__ == "__main__":
    unittest.main()
