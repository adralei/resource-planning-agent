
import unittest
from unittest.mock import patch
from uuid import UUID

from resource_planning_agent.approvals.approval_review_case import (
    prepare_approval_review_case,
)


MODULE = (
    "resource_planning_agent.approvals."
    "approval_review_case"
)


def make_assessment(status):
    return {
        "plan_id": "PLAN-501",
        "consistency_status": status,
        "recommended_action": "investigate_approval_evidence",
        "reason": "Approval record requires review.",
        "manual_review_required": True,
        "automatic_recovery_allowed": False,
        "can_proceed_to_preflight": False,
    }


class TestApprovalReviewCase(unittest.TestCase):

    @patch(f"{MODULE}.assess_approval_recovery")
    def test_missing_registry_creates_review_case(
        self, assess
    ):
        assess.return_value = make_assessment(
            "missing_registry"
        )

        result = prepare_approval_review_case("PLAN-501")

        self.assertEqual(
            result["case_status"],
            "awaiting_manual_review",
        )

        self.assertEqual(
            result["consistency_status"],
            "missing_registry",
        )

        self.assertEqual(result["plan_id"], "PLAN-501")

        UUID(result["case_id"])

        self.assertFalse(result["approval_granted"])
        self.assertFalse(result["registry_modified"])
        self.assertFalse(result["reservations_created"])

        assess.assert_called_once_with("PLAN-501")

    @patch(f"{MODULE}.assess_approval_recovery")
    def test_fingerprint_mismatch_requires_review(
        self, assess
    ):
        assess.return_value = make_assessment(
            "fingerprint_mismatch"
        )

        result = prepare_approval_review_case("PLAN-501")

        self.assertTrue(
            result["manual_review_required"]
        )
        self.assertFalse(
            result["can_proceed_to_preflight"]
        )
        self.assertFalse(
            result["automatic_recovery_allowed"]
        )

    @patch(f"{MODULE}.assess_approval_recovery")
    def test_consistent_plan_cannot_open_recovery(
        self, assess
    ):
        assess.return_value = make_assessment(
            "consistent"
        )

        with self.assertRaises(ValueError):
            prepare_approval_review_case("PLAN-501")

    @patch(f"{MODULE}.assess_approval_recovery")
    def test_unapproved_plan_uses_normal_workflow(
        self, assess
    ):
        assess.return_value = make_assessment(
            "not_approved"
        )

        with self.assertRaises(ValueError):
            prepare_approval_review_case("PLAN-501")

    @patch(f"{MODULE}.assess_approval_recovery")
    def test_inconsistent_assessment_rejected(
        self, assess
    ):
        assessment = make_assessment(
            "missing_registry"
        )

        # Tehlikeli bir recovery raporu simule ediyoruz.
        assessment["can_proceed_to_preflight"] = True

        assess.return_value = assessment

        with self.assertRaises(ValueError):
            prepare_approval_review_case("PLAN-501")

    @patch(f"{MODULE}.assess_approval_recovery")
    def test_missing_fingerprint_creates_review_case(
        self, assess
    ):
        assess.return_value = make_assessment(
            "missing_fingerprint"
        )

        result = prepare_approval_review_case("PLAN-501")

        self.assertEqual(
            result["case_status"],
            "awaiting_manual_review",
        )
        self.assertGreater(
            len(result["required_evidence"]),
            0,
        )


if __name__ == "__main__":
    unittest.main()
