
import copy
import unittest

from resource_planning_agent.planning.dated_plan_guard import validate_approved_dated_plan


RESERVATIONS = [
    {
        "reservation_id": "RES-501",
        "employee_id": "EMP-001",
        "capacity_date": "2026-11-16",
        "reserved_hours": 3,
    },
    {
        "reservation_id": "RES-502",
        "employee_id": "EMP-002",
        "capacity_date": "2026-11-17",
        "reserved_hours": 2,
    },
]


def make_approved_plan():
    return {
        "plan_id": "PLAN-501",
        "project_id": "PROJECT-501",
        "planning_period": "prototype_fixed_period",
        "status": "approved",
        "proposal": {
            "allocations": [
                {
                    "employee_id": "EMP-001",
                    "team": "Core",
                },
                {
                    "employee_id": "EMP-002",
                    "team": "Core",
                },
            ],
            "dated_reservations": copy.deepcopy(
                RESERVATIONS
            ),
        },
        "required_approvals": [
            {
                "role": "project_manager",
                "scope": "PROJECT-501",
                "status": "approved",
            },
            {
                "role": "team_manager",
                "scope": "Core",
                "status": "approved",
            },
        ],
    }


class TestDatedPlanGuard(unittest.TestCase):

    def test_valid_approved_plan_passes(self):
        plan = make_approved_plan()

        result = validate_approved_dated_plan(
            plan,
            copy.deepcopy(RESERVATIONS),
        )

        self.assertTrue(result["checks_passed"])
        self.assertEqual(result["reservation_count"], 2)

    def test_unapproved_plan_rejected(self):
        plan = make_approved_plan()
        plan["status"] = "pending_approval"

        with self.assertRaises(ValueError):
            validate_approved_dated_plan(
                plan,
                RESERVATIONS,
            )

    def test_missing_team_approval_rejected(self):
        plan = make_approved_plan()
        plan["required_approvals"].pop()

        with self.assertRaises(ValueError):
            validate_approved_dated_plan(
                plan,
                RESERVATIONS,
            )

    def test_modified_reservation_rejected(self):
        plan = make_approved_plan()
        changed = copy.deepcopy(RESERVATIONS)
        changed[0]["reserved_hours"] = 4

        with self.assertRaises(ValueError):
            validate_approved_dated_plan(
                plan,
                changed,
            )


if __name__ == "__main__":
    unittest.main()
