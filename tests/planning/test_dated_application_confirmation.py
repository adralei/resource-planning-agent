
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from resource_planning_agent.storage.database import (
    connect_db,
    PLANNING_PERIOD,
)

from resource_planning_agent.storage.approval_registry import (
    initialize_approval_registry,
)

from resource_planning_agent.storage.dated_application_registry import (
    initialize_dated_application_registry,
)

from resource_planning_agent.planning.dated_capacity import (
    set_daily_capacity,
)

from resource_planning_agent.planning.dated_reservations import (
    initialize_reservation_schema,
    reserve_daily_batch,
)

from resource_planning_agent.planning.dated_application_confirmation import (
    confirm_dated_plan_application,
)


MODULE = (
    "resource_planning_agent.planning."
    "dated_application_confirmation"
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
        "reservation_count": 2,
        "reservations": reservations,
        "approval_fingerprint": FINGERPRINT,
        "ready_for_capacity_revalidation": True,
        "applied": False,
    }


class TestDatedApplicationConfirmation(unittest.TestCase):

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        db_patch = patch(
            "resource_planning_agent.storage.database.DB_PATH",
            Path(temporary.name) / "confirmation.db",
        )
        db_patch.start()
        self.addCleanup(db_patch.stop)

        initialize_reservation_schema()
        initialize_approval_registry()
        initialize_dated_application_registry()

        set_daily_capacity("EMP-001", "2026-11-16", 4)
        set_daily_capacity("EMP-001", "2026-11-17", 4)

        self.preflight_data = make_preflight()

        preflight_patch = patch(
            f"{MODULE}.preflight_dated_plan",
            return_value=self.preflight_data,
        )
        preflight_patch.start()
        self.addCleanup(preflight_patch.stop)

        with closing(connect_db()) as connection:
            connection.execute("BEGIN IMMEDIATE")

            connection.execute("""
                INSERT INTO approval_fingerprints (
                    plan_id, fingerprint, recorded_at
                )
                VALUES (?, ?, ?)
            """, (
                "PLAN-801",
                FINGERPRINT,
                "2026-11-26T10:00:00+00:00",
            ))

            connection.commit()

    def apply_plan(self):
        return reserve_daily_batch(
            plan_id="PLAN-801",
            reservations=self.preflight_data[
                "reservations"
            ],
            planning_period=PLANNING_PERIOD,
            approval_fingerprint=FINGERPRINT,
        )

    def test_not_applied_returns_retry_candidate(self):
        result = confirm_dated_plan_application(
            "PLAN-801"
        )

        self.assertEqual(
            result["status"],
            "not_applied",
        )
        self.assertFalse(result["confirmed"])
        self.assertTrue(result["safe_to_retry"])

    def test_committed_application_confirmed(self):
        self.apply_plan()

        result = confirm_dated_plan_application(
            "PLAN-801"
        )

        self.assertEqual(
            result["status"],
            "confirmed_applied",
        )
        self.assertTrue(result["confirmed"])
        self.assertFalse(result["safe_to_retry"])
        self.assertEqual(
            result["reservation_count"],
            2,
        )

    def test_missing_reservation_rejected(self):
        self.apply_plan()

        with closing(connect_db()) as connection:
            connection.execute("BEGIN IMMEDIATE")

            connection.execute("""
                DELETE FROM daily_reservations
                WHERE reservation_id = ?
            """, ("RES-802",))

            connection.commit()

        with self.assertRaises(ValueError):
            confirm_dated_plan_application(
                "PLAN-801"
            )

    def test_registry_missing_with_reservations_rejected(
        self
    ):
        self.apply_plan()

        with closing(connect_db()) as connection:
            connection.execute("BEGIN IMMEDIATE")

            connection.execute("""
                DELETE FROM dated_plan_applications
                WHERE plan_id = ?
            """, ("PLAN-801",))

            connection.commit()

        with self.assertRaises(ValueError):
            confirm_dated_plan_application(
                "PLAN-801"
            )

    def test_wrong_fingerprint_rejected(self):
        self.apply_plan()

        with closing(connect_db()) as connection:
            connection.execute("BEGIN IMMEDIATE")

            connection.execute("""
                UPDATE dated_plan_applications
                SET approval_fingerprint = ?
                WHERE plan_id = ?
            """, ("b" * 64, "PLAN-801"))

            connection.commit()

        with self.assertRaises(ValueError):
            confirm_dated_plan_application(
                "PLAN-801"
            )

    def test_unverified_preflight_rejected(self):
        with patch(
            f"{MODULE}.preflight_dated_plan",
            side_effect=ValueError(
                "Approval registry missing."
            ),
        ):
            with self.assertRaises(ValueError):
                confirm_dated_plan_application(
                    "PLAN-801"
                )


if __name__ == "__main__":
    unittest.main()
