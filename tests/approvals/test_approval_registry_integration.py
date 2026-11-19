
import sqlite3
import unittest
from unittest.mock import patch

from resource_planning_agent.approvals.approve_plan import (
    approve_plan,
)
from tests.approvals.test_dated_approval_fingerprint import (
    make_pending_plan,
)


MODULE = "resource_planning_agent.approvals.approve_plan"


class TestApprovalRegistryIntegration(unittest.TestCase):

    @patch(f"{MODULE}.record_approval_fingerprint")
    @patch(f"{MODULE}.initialize_approval_registry")
    @patch(f"{MODULE}.update_plan")
    @patch(f"{MODULE}.load_plan")
    def test_final_approval_registers_fingerprint(
        self, load, update, initialize, record
    ):
        plan = make_pending_plan()
        plan["required_approvals"][0]["status"] = "approved"
        load.return_value = plan

        result = approve_plan(
            "PLAN-901",
            "manager_platform",
            "team_manager",
            "Platform",
        )

        self.assertEqual(result["status"], "approved")
        self.assertIn("approval_fingerprint", result)

        update.assert_called_once_with(result)
        initialize.assert_called_once_with()
        record.assert_called_once_with(result)

    @patch(f"{MODULE}.record_approval_fingerprint")
    @patch(f"{MODULE}.initialize_approval_registry")
    @patch(f"{MODULE}.update_plan")
    @patch(f"{MODULE}.load_plan")
    def test_partial_approval_does_not_register(
        self, load, update, initialize, record
    ):
        plan = make_pending_plan()
        load.return_value = plan

        result = approve_plan(
            "PLAN-901",
            "manager_project",
            "project_manager",
            "DEMO-PROJECT-001",
        )

        self.assertEqual(
            result["status"],
            "pending_approval",
        )
        self.assertNotIn("approval_fingerprint", result)

        update.assert_called_once()
        initialize.assert_not_called()
        record.assert_not_called()

    @patch(f"{MODULE}.record_approval_fingerprint")
    @patch(f"{MODULE}.initialize_approval_registry")
    @patch(f"{MODULE}.update_plan")
    @patch(f"{MODULE}.load_plan")
    def test_registry_failure_does_not_return_success(
        self, load, update, initialize, record
    ):
        plan = make_pending_plan()
        plan["required_approvals"][0]["status"] = "approved"
        load.return_value = plan

        record.side_effect = sqlite3.OperationalError(
            "simulated registry failure"
        )

        with self.assertRaises(sqlite3.OperationalError):
            approve_plan(
                "PLAN-901",
                "manager_platform",
                "team_manager",
                "Platform",
            )

        update.assert_called_once()
        initialize.assert_called_once()
        record.assert_called_once()


if __name__ == "__main__":
    unittest.main()
    