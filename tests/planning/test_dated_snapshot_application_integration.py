
"""Integration tests for dated-plan snapshot revalidation before application."""

import copy
import unittest
from unittest.mock import patch

from resource_planning_agent.planning.dated_plan_application import (
    apply_approved_dated_plan,
)


APPLICATION_MODULE = (
    "resource_planning_agent.planning."
    "dated_plan_application"
)

SNAPSHOT_MODULE = (
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


class TestDatedSnapshotApplicationIntegration(
    unittest.TestCase
):

    def setUp(self):
        self.initial = make_preflight()

        patches = {
            "initial_preflight": patch(
                f"{APPLICATION_MODULE}.preflight_dated_plan",
                return_value=self.initial,
            ),
            "current_preflight": patch(
                f"{SNAPSHOT_MODULE}.preflight_dated_plan",
                return_value=copy.deepcopy(self.initial),
            ),
            "initialize_reservations": patch(
                f"{APPLICATION_MODULE}.initialize_reservation_schema"
            ),
            "initialize_applications": patch(
                f"{APPLICATION_MODULE}.initialize_dated_application_registry"
            ),
            "reserve_batch": patch(
                f"{APPLICATION_MODULE}.reserve_daily_batch"
            ),
        }

        self.mocks = {}

        for name, patcher in patches.items():
            self.mocks[name] = patcher.start()
            self.addCleanup(patcher.stop)

        self.mocks["reserve_batch"].return_value = {
            "success": True,
            "plan_id": "PLAN-801",
            "reservation_count": 2,
            "total_reserved_hours": 5,
            "reservation_ids": [
                "RES-801",
                "RES-802",
            ],
        }

    def assert_no_application_started(self):
        self.mocks[
            "initialize_reservations"
        ].assert_not_called()

        self.mocks[
            "initialize_applications"
        ].assert_not_called()

        self.mocks[
            "reserve_batch"
        ].assert_not_called()

    def test_unchanged_snapshot_allows_application(self):
        result = apply_approved_dated_plan(
            "PLAN-801"
        )

        self.assertTrue(
            result["snapshot_revalidated"]
        )
        self.assertTrue(
            result["reservations_committed"]
        )

        self.mocks[
            "current_preflight"
        ].assert_called_once_with("PLAN-801")

        self.mocks[
            "reserve_batch"
        ].assert_called_once()

        arguments = self.mocks[
            "reserve_batch"
        ].call_args.kwargs

        self.assertEqual(
            arguments["approval_fingerprint"],
            FINGERPRINT,
        )
        self.assertEqual(
            arguments["reservations"],
            self.initial["reservations"],
        )

    def test_changed_reservation_blocks_application(self):
        changed = copy.deepcopy(self.initial)

        changed["reservations"][0][
            "reserved_hours"
        ] = 4

        self.mocks[
            "current_preflight"
        ].return_value = changed

        with self.assertRaises(ValueError):
            apply_approved_dated_plan(
                "PLAN-801"
            )

        self.assert_no_application_started()

    def test_second_preflight_failure_blocks_application(
        self
    ):
        self.mocks[
            "current_preflight"
        ].side_effect = ValueError(
            "Approval registry mismatch."
        )

        with self.assertRaisesRegex(
            ValueError,
            "Approval registry mismatch",
        ):
            apply_approved_dated_plan(
                "PLAN-801"
            )

        self.assert_no_application_started()


if __name__ == "__main__":
    unittest.main()
