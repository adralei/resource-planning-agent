
import sqlite3
import unittest
from unittest.mock import patch

from resource_planning_agent.approvals.approval_recovery import (
    assess_approval_recovery,
)


MODULE = (
    "resource_planning_agent.approvals."
    "approval_recovery"
)


def make_inspection(status):
    return {
        "plan_id": "PLAN-501",
        "status": status,
        "consistent": status == "consistent",
        "requires_manual_review": status not in (
            "consistent",
            "not_approved",
        ),
        "message": "Test inspection result",
    }


class TestApprovalRecovery(unittest.TestCase):

    @patch(f"{MODULE}.inspect_approval_consistency")
    def test_consistent_plan_can_continue(self, inspect):
        inspect.return_value = make_inspection(
            "consistent"
        )

        result = assess_approval_recovery("PLAN-501")

        self.assertTrue(
            result["can_proceed_to_preflight"]
        )
        self.assertFalse(result["recovered"])
        self.assertFalse(
            result["automatic_recovery_allowed"]
        )

        inspect.assert_called_once_with("PLAN-501")

    @patch(f"{MODULE}.inspect_approval_consistency")
    def test_missing_registry_requires_review(self, inspect):
        inspect.return_value = make_inspection(
            "missing_registry"
        )

        result = assess_approval_recovery("PLAN-501")

        self.assertEqual(
            result["recommended_action"],
            "investigate_approval_evidence",
        )
        self.assertTrue(
            result["manual_review_required"]
        )
        self.assertFalse(
            result["can_proceed_to_preflight"]
        )

    @patch(f"{MODULE}.inspect_approval_consistency")
    def test_fingerprint_mismatch_blocks_plan(self, inspect):
        inspect.return_value = make_inspection(
            "fingerprint_mismatch"
        )

        result = assess_approval_recovery("PLAN-501")

        self.assertEqual(
            result["recommended_action"],
            "investigate_integrity_violation",
        )
        self.assertFalse(
            result["can_proceed_to_preflight"]
        )

    @patch(f"{MODULE}.inspect_approval_consistency")
    def test_missing_fingerprint_blocks_plan(self, inspect):
        inspect.return_value = make_inspection(
            "missing_fingerprint"
        )

        result = assess_approval_recovery("PLAN-501")

        self.assertTrue(
            result["manual_review_required"]
        )
        self.assertFalse(result["recovered"])

    @patch(f"{MODULE}.inspect_approval_consistency")
    def test_unapproved_plan_uses_normal_workflow(
        self, inspect
    ):
        inspect.return_value = make_inspection(
            "not_approved"
        )

        result = assess_approval_recovery("PLAN-501")

        self.assertEqual(
            result["recommended_action"],
            "complete_normal_approval_workflow",
        )
        self.assertFalse(
            result["can_proceed_to_preflight"]
        )

    @patch(f"{MODULE}.inspect_approval_consistency")
    def test_invalid_plan_requires_review(self, inspect):
        inspect.return_value = make_inspection(
            "invalid_plan"
        )

        result = assess_approval_recovery("PLAN-501")

        self.assertEqual(
            result["recommended_action"],
            "investigate_invalid_plan",
        )
        self.assertTrue(
            result["manual_review_required"]
        )

    @patch(f"{MODULE}.inspect_approval_consistency")
    def test_database_error_propagates(self, inspect):
        inspect.side_effect = sqlite3.OperationalError(
            "database unavailable"
        )

        with self.assertRaises(
            sqlite3.OperationalError
        ):
            assess_approval_recovery("PLAN-501")


if __name__ == "__main__":
    unittest.main()
