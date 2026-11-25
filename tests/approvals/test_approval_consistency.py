
import copy
import sqlite3
import unittest
from unittest.mock import patch

from resource_planning_agent.approvals.approval_consistency import (
    inspect_approval_consistency,
)
from resource_planning_agent.planning.plan_fingerprint import (
    calculate_plan_fingerprint,
)
from tests.planning.test_dated_plan_guard import (
    make_approved_plan,
)


MODULE = (
    "resource_planning_agent.approvals."
    "approval_consistency"
)


def make_registered_plan():
    plan = make_approved_plan()

    plan["approval_fingerprint"] = (
        calculate_plan_fingerprint(plan)
    )

    return plan


class TestApprovalConsistency(unittest.TestCase):

    @patch(f"{MODULE}.read_approval_fingerprint")
    @patch(f"{MODULE}.load_plan")
    def test_consistent_approval(
        self, load, read_registry
    ):
        plan = make_registered_plan()
        load.return_value = plan

        read_registry.return_value = {
            "plan_id": "PLAN-501",
            "fingerprint": plan["approval_fingerprint"],
            "recorded_at": "2026-11-17T10:00:00+00:00",
        }

        result = inspect_approval_consistency(
            "PLAN-501"
        )

        self.assertEqual(
            result["status"],
            "consistent",
        )
        self.assertTrue(result["consistent"])
        self.assertFalse(
            result["requires_manual_review"]
        )

    @patch(f"{MODULE}.read_approval_fingerprint")
    @patch(f"{MODULE}.load_plan")
    def test_missing_registry_detected(
        self, load, read_registry
    ):
        plan = make_registered_plan()
        load.return_value = plan
        read_registry.return_value = None

        result = inspect_approval_consistency(
            "PLAN-501"
        )

        self.assertEqual(
            result["status"],
            "missing_registry",
        )
        self.assertFalse(result["consistent"])
        self.assertTrue(
            result["requires_manual_review"]
        )

    @patch(f"{MODULE}.read_approval_fingerprint")
    @patch(f"{MODULE}.load_plan")
    def test_registry_mismatch_detected(
        self, load, read_registry
    ):
        plan = make_registered_plan()
        load.return_value = plan

        read_registry.return_value = {
            "plan_id": "PLAN-501",
            "fingerprint": "a" * 64,
        }

        result = inspect_approval_consistency(
            "PLAN-501"
        )

        self.assertEqual(
            result["status"],
            "fingerprint_mismatch",
        )
        self.assertTrue(
            result["requires_manual_review"]
        )

    @patch(f"{MODULE}.read_approval_fingerprint")
    @patch(f"{MODULE}.load_plan")
    def test_modified_plan_detected(
        self, load, read_registry
    ):
        plan = copy.deepcopy(
            make_registered_plan()
        )

        plan["proposal"]["dated_reservations"][0][
            "reserved_hours"
        ] = 5

        load.return_value = plan

        result = inspect_approval_consistency(
            "PLAN-501"
        )

        self.assertEqual(
            result["status"],
            "fingerprint_mismatch",
        )
        read_registry.assert_not_called()

    @patch(f"{MODULE}.read_approval_fingerprint")
    @patch(f"{MODULE}.load_plan")
    def test_unapproved_plan_detected(
        self, load, read_registry
    ):
        plan = make_registered_plan()
        plan["status"] = "pending_approval"

        load.return_value = plan

        result = inspect_approval_consistency(
            "PLAN-501"
        )

        self.assertEqual(
            result["status"],
            "not_approved",
        )
        read_registry.assert_not_called()

    @patch(f"{MODULE}.read_approval_fingerprint")
    @patch(f"{MODULE}.load_plan")
    def test_database_error_is_not_missing_record(
        self, load, read_registry
    ):
        load.return_value = make_registered_plan()

        read_registry.side_effect = (
            sqlite3.OperationalError(
                "database unavailable"
            )
        )

        with self.assertRaises(
            sqlite3.OperationalError
        ):
            inspect_approval_consistency(
                "PLAN-501"
            )


if __name__ == "__main__":
    unittest.main()
