
"""Tests for daily reservation schema and reservation lookup behavior."""

import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import PLANNING_PERIOD, connect_db
from dated_capacity import set_daily_capacity

from dated_reservations import (
    initialize_reservation_schema,
    get_daily_reservations,
    reserve_daily_hours,
    reserve_daily_batch,
)

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier


class TestDatedReservations(unittest.TestCase):

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)

        db_patch = patch(
            "database.DB_PATH",
            Path(temp.name) / "reservations.db",
        )
        db_patch.start()
        self.addCleanup(db_patch.stop)

        initialize_reservation_schema()

    def test_schema_is_idempotent(self):
        initialize_reservation_schema()
        initialize_reservation_schema()

        with closing(connect_db()) as connection:
            connection.commit()
            row = connection.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'daily_reservations'
            """).fetchone()

        self.assertIsNotNone(row)

    def test_unknown_daily_capacity_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with closing(connect_db()) as connection:
                connection.execute("""
                    INSERT INTO daily_reservations (
                        reservation_id,
                        plan_id,
                        employee_id,
                        planning_period,
                        capacity_date,
                        reserved_hours
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    "RES-001",
                    "PLAN-001",
                    "EMP-001",
                    PLANNING_PERIOD,
                    "2026-11-16",
                    2,
                ))

    def test_reservation_read(self):
        set_daily_capacity(
            "EMP-001", "2026-11-16", 4
        )

        with closing(connect_db()) as connection:
            connection.execute("""
                INSERT INTO daily_reservations (
                    reservation_id,
                    plan_id,
                    employee_id,
                    planning_period,
                    capacity_date,
                    reserved_hours
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                "RES-001",
                "PLAN-001",
                "EMP-001",
                PLANNING_PERIOD,
                "2026-11-16",
                3,
            ))

        reservations = get_daily_reservations(
            "EMP-001",
            "2026-11-16",
            PLANNING_PERIOD,
        )

        self.assertEqual(len(reservations), 1)
        self.assertEqual(
            reservations[0]["reserved_hours"],
            3,
        )
        self.assertEqual(
            reservations[0]["plan_id"],
            "PLAN-001",
        )


    def test_successful_reservation(self):
        set_daily_capacity("EMP-001", "2026-11-16", 4)

        result = reserve_daily_hours(
            "RES-101", "PLAN-A",
            "EMP-001", "2026-11-16", 3,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["remaining_hours"], 1)

        reservations = get_daily_reservations(
            "EMP-001", "2026-11-16", PLANNING_PERIOD
        )
        self.assertEqual(len(reservations), 1)

    def test_overbooking_rejected(self):
        set_daily_capacity("EMP-001", "2026-11-16", 4)

        reserve_daily_hours(
            "RES-101", "PLAN-A",
            "EMP-001", "2026-11-16", 3,
        )

        with self.assertRaises(ValueError):
            reserve_daily_hours(
                "RES-102", "PLAN-B",
                "EMP-001", "2026-11-16", 2,
            )

        reservations = get_daily_reservations(
            "EMP-001", "2026-11-16", PLANNING_PERIOD
        )
        self.assertEqual(len(reservations), 1)
        self.assertEqual(
            sum(r["reserved_hours"] for r in reservations),
            3,
        )

    def test_duplicate_reservation_rejected(self):
        set_daily_capacity("EMP-001", "2026-11-16", 4)

        reserve_daily_hours(
            "RES-101", "PLAN-A",
            "EMP-001", "2026-11-16", 2,
        )

        with self.assertRaises(ValueError):
            reserve_daily_hours(
                "RES-101", "PLAN-A",
                "EMP-001", "2026-11-16", 2,
            )

        reservations = get_daily_reservations(
            "EMP-001", "2026-11-16", PLANNING_PERIOD
        )
        self.assertEqual(len(reservations), 1)

    def test_missing_daily_capacity_rejected(self):
        with self.assertRaises(ValueError):
            reserve_daily_hours(
                "RES-101", "PLAN-A",
                "EMP-001", "2026-11-18", 2,
            )

        reservations = get_daily_reservations(
            "EMP-001", "2026-11-18", PLANNING_PERIOD
        )
        self.assertEqual(reservations, [])

    def test_invalid_reservation_hours(self):
        for hours in (0, -1, "2", True, 1.5):
            with self.subTest(hours=hours):
                with self.assertRaises(ValueError):
                    reserve_daily_hours(
                        "RES-101", "PLAN-A",
                        "EMP-001", "2026-11-16", hours,
                    )


    def test_concurrent_reservations_cannot_overbook(self):
        """
        Iki ayri plan ayni anda 3'er saat ister.
        Toplam kapasite 4 saat oldugu icin
        yalnizca bir rezervasyon basarili olmalidir.
        """

        employee_id = "EMP-001"
        day = "2026-11-16"

        set_daily_capacity(employee_id, day, 4)

        # Iki thread'in ayni anda baslamasini saglar.
        barrier = Barrier(2)

        def make_reservation(reservation_id, plan_id):
            barrier.wait(timeout=5)

            try:
                reserve_daily_hours(
                    reservation_id,
                    plan_id,
                    employee_id,
                    day,
                    3,
                )
                return "success"

            except ValueError:
                return "rejected"

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(
                make_reservation,
                "RES-A",
                "PLAN-A",
            )

            future_b = executor.submit(
                make_reservation,
                "RES-B",
                "PLAN-B",
            )

            results = [
                future_a.result(),
                future_b.result(),
            ]

        # Tam olarak bir rezervasyon basarili olmali.
        self.assertEqual(results.count("success"), 1)
        self.assertEqual(results.count("rejected"), 1)

        # Veritabaninda sadece bir kayit bulunmali.
        reservations = get_daily_reservations(
            employee_id,
            day,
            PLANNING_PERIOD,
        )

        self.assertEqual(len(reservations), 1)

        total_reserved = sum(
            reservation["reserved_hours"]
            for reservation in reservations
        )

        self.assertEqual(total_reserved, 3)

        # Kapasite asilmamis olmali.
        self.assertLessEqual(total_reserved, 4)


    def test_batch_reservation_success(self):
        set_daily_capacity("EMP-001", "2026-11-16", 4)
        set_daily_capacity("EMP-002", "2026-11-17", 3)

        result = reserve_daily_batch(
            plan_id="PLAN-BATCH-1",
            reservations=[
                {
                    "reservation_id": "BATCH-001",
                    "employee_id": "EMP-001",
                    "capacity_date": "2026-11-16",
                    "reserved_hours": 3,
                },
                {
                    "reservation_id": "BATCH-002",
                    "employee_id": "EMP-002",
                    "capacity_date": "2026-11-17",
                    "reserved_hours": 2,
                },
            ],
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["reservation_count"], 2)
        self.assertEqual(result["total_reserved_hours"], 5)

        for employee_id, day in [
            ("EMP-001", "2026-11-16"),
            ("EMP-002", "2026-11-17"),
        ]:
            rows = get_daily_reservations(
                employee_id, day, PLANNING_PERIOD
            )
            self.assertEqual(len(rows), 1)

    def test_batch_failure_rolls_back(self):
        set_daily_capacity("EMP-001", "2026-11-16", 4)
        set_daily_capacity("EMP-002", "2026-11-17", 1)

        with self.assertRaises(ValueError):
            reserve_daily_batch(
                plan_id="PLAN-BATCH-2",
                reservations=[
                    {
                        "reservation_id": "BATCH-003",
                        "employee_id": "EMP-001",
                        "capacity_date": "2026-11-16",
                        "reserved_hours": 3,
                    },
                    {
                        "reservation_id": "BATCH-004",
                        "employee_id": "EMP-002",
                        "capacity_date": "2026-11-17",
                        "reserved_hours": 2,
                    },
                ],
            )

        rows = get_daily_reservations(
            "EMP-001", "2026-11-16", PLANNING_PERIOD
        )
        self.assertEqual(rows, [])

        rows = get_daily_reservations(
            "EMP-002", "2026-11-17", PLANNING_PERIOD
        )
        self.assertEqual(rows, [])

    def test_batch_aggregates_same_day_requests(self):
        set_daily_capacity("EMP-001", "2026-11-16", 4)

        with self.assertRaises(ValueError):
            reserve_daily_batch(
                plan_id="PLAN-BATCH-3",
                reservations=[
                    {
                        "reservation_id": "BATCH-005",
                        "employee_id": "EMP-001",
                        "capacity_date": "2026-11-16",
                        "reserved_hours": 3,
                    },
                    {
                        "reservation_id": "BATCH-006",
                        "employee_id": "EMP-001",
                        "capacity_date": "2026-11-16",
                        "reserved_hours": 2,
                    },
                ],
            )

        rows = get_daily_reservations(
            "EMP-001", "2026-11-16", PLANNING_PERIOD
        )
        self.assertEqual(rows, [])

    def test_batch_duplicate_id_rejected(self):
        set_daily_capacity("EMP-001", "2026-11-16", 4)

        with self.assertRaises(ValueError):
            reserve_daily_batch(
                plan_id="PLAN-BATCH-4",
                reservations=[
                    {
                        "reservation_id": "BATCH-007",
                        "employee_id": "EMP-001",
                        "capacity_date": "2026-11-16",
                        "reserved_hours": 1,
                    },
                    {
                        "reservation_id": "BATCH-007",
                        "employee_id": "EMP-001",
                        "capacity_date": "2026-11-16",
                        "reserved_hours": 1,
                    },
                ],
            )

        rows = get_daily_reservations(
            "EMP-001", "2026-11-16", PLANNING_PERIOD
        )
        self.assertEqual(rows, [])


    def test_batch_insert_failure_rolls_back_all(self):
        """
        Ilk INSERT basarili, ikinci INSERT hatali.
        Transaction tum kayitlari geri almali.
        """

        set_daily_capacity("EMP-001", "2026-11-16", 4)
        set_daily_capacity("EMP-002", "2026-11-17", 4)

        # Ikinci INSERT'i bilerek basarisiz yapacak
        # gecici bir SQLite trigger olusturuyoruz.
        with closing(connect_db()) as connection:
            connection.execute("""
                CREATE TRIGGER fail_second_reservation
                BEFORE INSERT ON daily_reservations
                WHEN NEW.reservation_id = 'BATCH-FAIL-002'
                BEGIN
                    SELECT RAISE(
                        ABORT,
                        'simulated insert failure'
                    );
                END
            """)

        with self.assertRaises(sqlite3.IntegrityError):
            reserve_daily_batch(
                plan_id="PLAN-BATCH-FAIL",
                reservations=[
                    {
                        "reservation_id": "BATCH-FAIL-001",
                        "employee_id": "EMP-001",
                        "capacity_date": "2026-11-16",
                        "reserved_hours": 3,
                    },
                    {
                        "reservation_id": "BATCH-FAIL-002",
                        "employee_id": "EMP-002",
                        "capacity_date": "2026-11-17",
                        "reserved_hours": 2,
                    },
                ],
            )

        # Ilk INSERT de rollback ile silinmis olmali.
        ada_rows = get_daily_reservations(
            "EMP-001",
            "2026-11-16",
            PLANNING_PERIOD,
        )

        bora_rows = get_daily_reservations(
            "EMP-002",
            "2026-11-17",
            PLANNING_PERIOD,
        )

        self.assertEqual(ada_rows, [])
        self.assertEqual(bora_rows, [])

        # Transaction basarisiz olsa da baslangic
        # kapasite kayitlari korunmali.
        with closing(connect_db()) as connection:
            rows = connection.execute("""
                SELECT employee_id, available_hours
                FROM employee_daily_capacity
                WHERE planning_period = ?
                  AND capacity_date IN (?, ?)
                ORDER BY employee_id
            """, (
                PLANNING_PERIOD,
                "2026-11-16",
                "2026-11-17",
            )).fetchall()

        self.assertEqual(
            [(row["employee_id"], row["available_hours"])
             for row in rows],
            [("EMP-001", 4), ("EMP-002", 4)],
        )




if __name__ == "__main__":
    unittest.main()
