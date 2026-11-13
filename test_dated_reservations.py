
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
)


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


if __name__ == "__main__":
    unittest.main()
