
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
    read_dated_application_record,
)

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

FINGERPRINT = "a" * 64


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
        "approval_fingerprint": FINGERPRINT,
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
        initialize_approval_registry()

        set_daily_capacity(
            "EMP-001", "2026-11-16", 4
        )
        set_daily_capacity(
            "EMP-001", "2026-11-17", 4
        )

        # Test fixture: bagimsiz approval kaydi.
        # Gercek bir yonetici onayi degildir.
        with closing(connect_db()) as connection:
            connection.execute("BEGIN IMMEDIATE")

            connection.execute("""
                INSERT INTO approval_fingerprints (
                    plan_id,
                    fingerprint,
                    recorded_at
                )
                VALUES (?, ?, ?)
            """, (
                "PLAN-801",
                FINGERPRINT,
                "2026-11-26T10:00:00+00:00",
            ))

            connection.commit()


        # Bu testlerin odagi atomik uygulama servisidir.
        # Snapshot modulu ayri test dosyasinda
        # ve yeni entegrasyon testlerinde sinanir.
        snapshot_patch = patch(
            f"{MODULE}.revalidate_dated_plan_snapshot",
            side_effect=lambda initial: {
                **initial,
                "status": "snapshot_revalidated",
                "snapshot_matches": True,
            },
        )

        snapshot_patch.start()
        self.addCleanup(snapshot_patch.stop)

    def reservations_for(self, day):
        return get_daily_reservations(
            "EMP-001",
            day,
            PLANNING_PERIOD,
        )

    @patch(f"{MODULE}.preflight_dated_plan")
    def test_approved_plan_reserves_capacity(
        self, preflight
    ):
        preflight.return_value = make_preflight()

        result = apply_approved_dated_plan(
            "PLAN-801"
        )

        self.assertEqual(
            result["status"],
            "reservations_applied",
        )
        self.assertTrue(
            result["reservations_committed"]
        )
        self.assertTrue(
            result["application_record_created"]
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

        self.assertIsNone(
            read_dated_application_record("PLAN-801")
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

    @patch(f"{MODULE}.preflight_dated_plan")
    def test_application_registry_record_created(
        self, preflight
    ):
        preflight.return_value = make_preflight()

        result = apply_approved_dated_plan("PLAN-801")

        record = read_dated_application_record(
            "PLAN-801"
        )

        self.assertIsNotNone(record)
        self.assertEqual(
            record["approval_fingerprint"],
            result["approval_fingerprint"],
        )
        self.assertEqual(
            record["reservation_count"],
            2,
        )

    @patch(f"{MODULE}.preflight_dated_plan")
    def test_same_plan_new_reservation_ids_rejected(
        self, preflight
    ):
        preflight.return_value = make_preflight()

        apply_approved_dated_plan("PLAN-801")

        changed = make_preflight()

        changed["reservations"][0][
            "reservation_id"
        ] = "OTHER-001"

        changed["reservations"][1][
            "reservation_id"
        ] = "OTHER-002"

        preflight.return_value = changed

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

    @patch(f"{MODULE}.preflight_dated_plan")
    def test_mismatched_registry_fingerprint_rejected(
        self, preflight
    ):
        invalid = make_preflight()
        invalid["approval_fingerprint"] = "b" * 64

        preflight.return_value = invalid

        with self.assertRaises(ValueError):
            apply_approved_dated_plan("PLAN-801")

        self.assertIsNone(
            read_dated_application_record("PLAN-801")
        )

        self.assertEqual(
            self.reservations_for("2026-11-16"),
            [],
        )


if __name__ == "__main__":
    unittest.main()
