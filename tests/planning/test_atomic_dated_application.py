
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
    read_dated_application_record,
)

from resource_planning_agent.planning.dated_capacity import (
    set_daily_capacity,
)

from resource_planning_agent.planning.dated_reservations import (
    initialize_reservation_schema,
    get_daily_reservations,
    reserve_daily_batch,
)


FINGERPRINT = "a" * 64
MODULE = (
    "resource_planning_agent.planning."
    "dated_reservations"
)


def make_reservations(prefix="RES", second_hours=2):
    return [
        {
            "reservation_id": f"{prefix}-001",
            "employee_id": "EMP-001",
            "capacity_date": "2026-11-16",
            "reserved_hours": 3,
        },
        {
            "reservation_id": f"{prefix}-002",
            "employee_id": "EMP-001",
            "capacity_date": "2026-11-17",
            "reserved_hours": second_hours,
        },
    ]


class TestAtomicDatedApplication(unittest.TestCase):

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        db_patch = patch(
            "resource_planning_agent.storage.database.DB_PATH",
            Path(temporary.name) / "atomic_application.db",
        )

        db_patch.start()
        self.addCleanup(db_patch.stop)

        initialize_reservation_schema()
        initialize_approval_registry()
        initialize_dated_application_registry()

        set_daily_capacity(
            "EMP-001", "2026-11-16", 4
        )
        set_daily_capacity(
            "EMP-001", "2026-11-17", 4
        )

        # Test fixture: bagimsiz onay kaydini hazirliyoruz.
        # Bu kayit gercek bir yonetici onayi degildir.
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

    def apply_batch(
        self,
        reservations=None,
        fingerprint=FINGERPRINT,
    ):
        if reservations is None:
            reservations = make_reservations()

        return reserve_daily_batch(
            plan_id="PLAN-801",
            reservations=reservations,
            planning_period=PLANNING_PERIOD,
            approval_fingerprint=fingerprint,
        )

    def reservations_for(self, day):
        return get_daily_reservations(
            "EMP-001",
            day,
            PLANNING_PERIOD,
        )

    def test_reservations_and_application_commit(self):
        result = self.apply_batch()

        self.assertTrue(result["success"])

        record = read_dated_application_record(
            "PLAN-801"
        )

        self.assertIsNotNone(record)
        self.assertEqual(
            record["approval_fingerprint"],
            FINGERPRINT,
        )
        self.assertEqual(
            record["reservation_count"],
            2,
        )

        self.assertEqual(
            len(self.reservations_for("2026-11-16")),
            1,
        )
        self.assertEqual(
            len(self.reservations_for("2026-11-17")),
            1,
        )

    def test_insufficient_capacity_rolls_back_all(self):
        reservations = make_reservations(
            second_hours=5
        )

        with self.assertRaises(ValueError):
            self.apply_batch(reservations)

        self.assertIsNone(
            read_dated_application_record("PLAN-801")
        )
        self.assertEqual(
            self.reservations_for("2026-11-16"),
            [],
        )
        self.assertEqual(
            self.reservations_for("2026-11-17"),
            [],
        )

    def test_wrong_approval_fingerprint_rejected(self):
        with self.assertRaises(ValueError):
            self.apply_batch(
                fingerprint="b" * 64
            )

        self.assertIsNone(
            read_dated_application_record("PLAN-801")
        )
        self.assertEqual(
            self.reservations_for("2026-11-16"),
            [],
        )

    def test_same_plan_new_reservation_ids_rejected(self):
        self.apply_batch()

        with self.assertRaises(ValueError):
            self.apply_batch(
                make_reservations(prefix="OTHER")
            )

        record = read_dated_application_record(
            "PLAN-801"
        )

        self.assertIsNotNone(record)

        self.assertEqual(
            len(self.reservations_for("2026-11-16")),
            1,
        )
        self.assertEqual(
            len(self.reservations_for("2026-11-17")),
            1,
        )

    @patch(
        f"{MODULE}.insert_dated_application_record"
    )
    def test_registry_insert_failure_rolls_back(
        self, insert_record
    ):
        insert_record.side_effect = RuntimeError(
            "Simulated application registry failure"
        )

        with self.assertRaises(RuntimeError):
            self.apply_batch()

        self.assertIsNone(
            read_dated_application_record("PLAN-801")
        )
        self.assertEqual(
            self.reservations_for("2026-11-16"),
            [],
        )
        self.assertEqual(
            self.reservations_for("2026-11-17"),
            [],
        )


if __name__ == "__main__":
    unittest.main()
