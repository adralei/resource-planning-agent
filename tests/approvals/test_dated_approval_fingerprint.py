import copy
import unittest
from unittest.mock import patch

from resource_planning_agent.approvals.approve_plan import (
    approve_plan,
)
from resource_planning_agent.planning.plan_fingerprint import (
    verify_plan_fingerprint,
)


def make_pending_plan(dated=True):
    proposal = {
        "allocations": [
            {
                "employee_id": "EMP-001",
                "team": "Platform",
                "proposed_hours": 3,
            }
        ],
    }

    if dated:
        proposal["dated_reservations"] = [
            {
                "reservation_id": "RES-901",
                "employee_id": "EMP-001",
                "capacity_date": "2026-11-16",
                "reserved_hours": 3,
            }
        ]

    return {
        "plan_id": "PLAN-901",
        "project_id": "DEMO-PROJECT-001",
        "planning_period": "prototype_fixed_period",
        "status": "pending_approval",
        "proposal": proposal,
        "required_approvals": [
            {
                "role": "project_manager",
                "scope": "DEMO-PROJECT-001",
                "status": "pending",
            },
            {
                "role": "team_manager",
                "scope": "Platform",
                "status": "pending",
            },
        ],
    }


class TestDatedApprovalFingerprint(unittest.TestCase):

    @patch(
        "resource_planning_agent.approvals."
        "approve_plan.update_plan"
    )
    @patch(
        "resource_planning_agent.approvals."
        "approve_plan.load_plan"
    )
    def test_fingerprint_only_after_final_approval(
        self, load, update
    ):
        plan = make_pending_plan()
        load.return_value = plan

        first = approve_plan(
            "PLAN-901",
            "manager_project",
            "project_manager",
            "DEMO-PROJECT-001",
        )

        self.assertEqual(
            first["status"],
            "pending_approval",
        )
        self.assertNotIn(
            "approval_fingerprint",
            first,
        )

        final = approve_plan(
            "PLAN-901",
            "manager_platform",
            "team_manager",
            "Platform",
        )

        self.assertEqual(final["status"], "approved")
        self.assertTrue(
            verify_plan_fingerprint(
                final,
                final["approval_fingerprint"],
            )
        )
        self.assertEqual(update.call_count, 2)

    @patch(
        "resource_planning_agent.approvals."
        "approve_plan.update_plan"
    )
    @patch(
        "resource_planning_agent.approvals."
        "approve_plan.load_plan"
    )
    def test_modified_plan_fails_fingerprint_check(
        self, load, update
    ):
        plan = make_pending_plan()
        plan["required_approvals"][0]["status"] = "approved"
        load.return_value = plan

        approved = approve_plan(
            "PLAN-901",
            "manager_platform",
            "team_manager",
            "Platform",
        )

        modified = copy.deepcopy(approved)

        modified["proposal"]["dated_reservations"][0][
            "reserved_hours"
        ] = 5

        self.assertFalse(
            verify_plan_fingerprint(
                modified,
                approved["approval_fingerprint"],
            )
        )

    @patch(
        "resource_planning_agent.approvals."
        "approve_plan.update_plan"
    )
    @patch(
        "resource_planning_agent.approvals."
        "approve_plan.load_plan"
    )
    def test_fixed_period_plan_is_unchanged(
        self, load, update
    ):
        plan = make_pending_plan(dated=False)
        plan["required_approvals"][0]["status"] = "approved"
        load.return_value = plan

        approved = approve_plan(
            "PLAN-901",
            "manager_platform",
            "team_manager",
            "Platform",
        )

        self.assertEqual(approved["status"], "approved")
        self.assertNotIn("approval_fingerprint", approved)


if __name__ == "__main__":
    unittest.main()