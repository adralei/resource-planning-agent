
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from resource_planning_agent.planning.dated_plan_application import (
    apply_approved_dated_plan,
)

from resource_planning_agent.planning.dated_capacity import (
    set_daily_capacity,
)

from resource_planning_agent.planning.dated_reservations import (
    initialize_reservation_schema,
    get_daily_reservations,
)


MODULE = (
    "resource_planning_agent.planning."
    "dated_plan_application"
)


def make_preflight(reservations=None):
    if reservations is None:
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
        "ready_for_capacity_revalidation": True,
        "applied": False,
    }


class TestDatedPlanApplication(unittest.TestCase):

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        db_patch = patch(
            "resource_planning_agent.storage.database.DB_PATH",
            Path(temporary.name) / "dated_application.db",
        )

        db_patch.start()
        self.addCleanup(db_patch.stop)

        initialize_reservation_schema()

        set_daily_capacity("EMP-001", "2026-11-16", 4)
        set_daily_capacity("EMP-001", "2026-11-17", 4)

    def reservations_for(self, day):
        return get_daily_reservations(
            "EMP-001",
            day,
            "prototype_fixed_period",
        )

    @patch(f"{MODULE}.preflight_dated_plan")
    def test_approved_plan_reserves_capacity(
        self, preflight
    ):
        preflight.return_value = make_preflight()

        result = apply_approved_dated_plan("PLAN-801")

        self.assertEqual(
            result["status"],
            "reservations_applied",
        )
        self.assertTrue(
            result["reservations_committed"]
        )
        self.assertEqual(
            result["reservation_count"],
            2,
        )
        self.assertEqual(
            result["total_reserved_hours"],
            5,
        )

        self.assertEqual(
            len(self.reservations_for("2026-11-16")),
            1,
        )
        self.assertEqual(
            len(self.reservations_for("2026-11-17")),
            1,
        )

    @patch(f"{MODULE}.preflight_dated_plan")
    def test_preflight_failure_creates_no_reservations(
        self, preflight
    ):
        preflight.side_effect = ValueError(
            "Independent approval registry missing."
        )

        with self.assertRaises(ValueError):
            apply_approved_dated_plan("PLAN-801")

        self.assertEqual(
            self.reservations_for("2026-11-16"),
            [],
        )
        self.assertEqual(
            self.reservations_for("2026-11-17"),
            [],
        )

    @patch(f"{MODULE}.preflight_dated_plan")
    def test_insufficient_capacity_rolls_back_batch(
        self, preflight
    ):
        preflight.return_value = make_preflight([
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
                "reserved_hours": 5,
            },
        ])

        with self.assertRaises(ValueError):
            apply_approved_dated_plan("PLAN-801")

        self.assertEqual(
            self.reservations_for("2026-11-16"),
            [],
        )
        self.assertEqual(
            self.reservations_for("2026-11-17"),
            [],
        )

    @patch(f"{MODULE}.preflight_dated_plan")
    def test_second_application_is_rejected(
        self, preflight
    ):
        preflight.return_value = make_preflight()

        first = apply_approved_dated_plan("PLAN-801")

        self.assertTrue(
            first["reservations_committed"]
        )

        with self.assertRaises(ValueError):
            apply_approved_dated_plan("PLAN-801")

        self.assertEqual(
            len(self.reservations_for("2026-11-16")),
            1,
        )
        self.assertEqual(
            len(self.reservations_for("2026-11-17")),
            1,
        )

    @patch(f"{MODULE}.reserve_daily_batch")
    @patch(f"{MODULE}.preflight_dated_plan")
    def test_invalid_preflight_result_is_rejected(
        self, preflight, reserve_batch
    ):
        invalid = make_preflight()
        invalid["reservation_count"] = 999

        preflight.return_value = invalid

        with self.assertRaises(ValueError):
            apply_approved_dated_plan("PLAN-801")

        reserve_batch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
