
import copy
import unittest
from unittest.mock import patch

from resource_planning_agent.planning.dated_plan_snapshot import (
    revalidate_dated_plan_snapshot,
)


MODULE = (
    "resource_planning_agent.planning."
    "dated_plan_snapshot"
)

FINGERPRINT = "a" * 64


def make_preflight():
    reservations = [
        {
            "reservation_id": "RES-801",
            "employee_id": "EMP-001",
            "capacity_date": "2026-11-16",
            "reserved_hours": 3,
        },
        {
            "reservation_id": "RES-802",
            "employee_id": "EMP-001",
            "capacity_date": "2026-11-17",
            "reserved_hours": 2,
        },
    ]

    return {
        "status": "preflight_passed",
        "plan_id": "PLAN-801",
        "project_id": "DEMO-PROJECT-001",
        "reservation_count": len(reservations),
        "reservations": reservations,
        "approval_fingerprint": FINGERPRINT,
        "ready_for_capacity_revalidation": True,
        "applied": False,
    }


class TestDatedPlanSnapshot(unittest.TestCase):

    @patch(f"{MODULE}.preflight_dated_plan")
    def test_unchanged_snapshot_passes(self, preflight):
        initial = make_preflight()

        preflight.return_value = copy.deepcopy(initial)

        result = revalidate_dated_plan_snapshot(
            initial
        )

        self.assertEqual(
            result["status"],
            "snapshot_revalidated",
        )
        self.assertTrue(result["snapshot_matches"])
        self.assertFalse(result["applied"])

        self.assertEqual(
            result["approval_fingerprint"],
            FINGERPRINT,
        )

        preflight.assert_called_once_with("PLAN-801")

    @patch(f"{MODULE}.preflight_dated_plan")
    def test_changed_reservation_rejected(self, preflight):
        initial = make_preflight()
        changed = copy.deepcopy(initial)

        changed["reservations"][0]["reserved_hours"] = 4

        preflight.return_value = changed

        with self.assertRaises(ValueError):
            revalidate_dated_plan_snapshot(initial)

    @patch(f"{MODULE}.preflight_dated_plan")
    def test_changed_fingerprint_rejected(self, preflight):
        initial = make_preflight()
        changed = copy.deepcopy(initial)

        changed["approval_fingerprint"] = "b" * 64

        preflight.return_value = changed

        with self.assertRaises(ValueError):
            revalidate_dated_plan_snapshot(initial)

    @patch(f"{MODULE}.preflight_dated_plan")
    def test_changed_project_rejected(self, preflight):
        initial = make_preflight()
        changed = copy.deepcopy(initial)

        changed["project_id"] = "OTHER-PROJECT"

        preflight.return_value = changed

        with self.assertRaises(ValueError):
            revalidate_dated_plan_snapshot(initial)

    @patch(f"{MODULE}.preflight_dated_plan")
    def test_invalid_initial_snapshot_rejected(
        self, preflight
    ):
        initial = make_preflight()
        initial["reservation_count"] = 999

        with self.assertRaises(ValueError):
            revalidate_dated_plan_snapshot(initial)

        preflight.assert_not_called()

    @patch(f"{MODULE}.preflight_dated_plan")
    def test_second_preflight_failure_propagates(
        self, preflight
    ):
        initial = make_preflight()

        preflight.side_effect = ValueError(
            "Approval registry mismatch."
        )

        with self.assertRaises(ValueError):
            revalidate_dated_plan_snapshot(initial)

        preflight.assert_called_once_with("PLAN-801")


if __name__ == "__main__":
    unittest.main()
