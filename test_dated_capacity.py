"""Yeni gunluk kapasite katmani icin regresyon testleri.

Her test gecici SQLite kullanir. Gercek proje verileri degismez.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import PLANNING_PERIOD, PRIMARY_TEAM, read_employee_capacities
from dated_capacity import (
    check_dated_capacity,
    initialize_daily_capacity_schema,
    set_daily_capacity,
)

from dated_reservations import (
    initialize_reservation_schema,
    reserve_daily_hours,
)


class TestDatedCapacity(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        db_patch = patch("database.DB_PATH", Path(temp.name) / "dates.db")
        db_patch.start()
        self.addCleanup(db_patch.stop)
        initialize_daily_capacity_schema()

    def seed_two_days(self):
        for employee_id, day, hours in (
            ("EMP-001", "2026-11-16", 4),
            ("EMP-001", "2026-11-17", 4),
            ("EMP-002", "2026-11-16", 2),
            ("EMP-002", "2026-11-17", 2),
        ):
            set_daily_capacity(employee_id, day, hours)

    def test_two_day_capacity_and_shortage(self):
        self.seed_two_days()
        result = check_dated_capacity("backend", 14, "2026-11-16", "2026-11-17")
        self.assertTrue(result["data_complete"])
        self.assertEqual(result["total_capacity"], 12)
        self.assertEqual(result["shortage"], 2)
        self.assertFalse(result["is_sufficient"])
        self.assertEqual(result["candidates"], ["Ada", "Bora"])

    def test_exact_capacity_is_sufficient(self):
        self.seed_two_days()
        result = check_dated_capacity("backend", 12, "2026-11-16", "2026-11-17")
        self.assertEqual(result["shortage"], 0)
        self.assertTrue(result["is_sufficient"])

    def test_missing_day_is_unknown_not_zero(self):
        self.seed_two_days()
        result = check_dated_capacity("backend", 14, "2026-11-16", "2026-11-18")
        self.assertFalse(result["data_complete"])
        self.assertEqual(result["known_available_hours"], 12)
        self.assertIsNone(result["total_capacity"])
        self.assertIsNone(result["shortage"])
        self.assertIsNone(result["is_sufficient"])
        self.assertCountEqual(result["missing_availability"], [
            {"employee_id": "EMP-001", "date": "2026-11-18"},
            {"employee_id": "EMP-002", "date": "2026-11-18"},
        ])

    def test_zero_hour_records_are_real_zero(self):
        for employee_id in ("EMP-001", "EMP-002"):
            set_daily_capacity(employee_id, "2026-11-16", 0)
        result = check_dated_capacity("backend", 3, "2026-11-16", "2026-11-16")
        self.assertTrue(result["data_complete"])
        self.assertEqual(result["total_capacity"], 0)
        self.assertEqual(result["shortage"], 3)

    def test_date_and_hours_validation(self):
        invalid_ranges = [
            ("2026-11-17", "2026-11-16"),
            ("2026-02-30", "2026-03-01"),
            ("2026-11-1", "2026-11-17"),
            ("2026-11-01", "2026-12-02"),  # 32 gun
        ]
        for start, end in invalid_ranges:
            with self.subTest(start=start, end=end):
                with self.assertRaises(ValueError):
                    check_dated_capacity("backend", 10, start, end)

        for invalid_hours in (True, 1.5, "8", -1, 25):
            with self.subTest(hours=invalid_hours):
                with self.assertRaises(ValueError):
                    set_daily_capacity("EMP-001", "2026-11-16", invalid_hours)

        for invalid_request in (False, "10", 0, -2):
            with self.subTest(request=invalid_request):
                with self.assertRaises(ValueError):
                    check_dated_capacity("backend", invalid_request,
                                         "2026-11-16", "2026-11-17")

    def test_unknown_employee_is_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            set_daily_capacity("EMP-DOES-NOT-EXIST", "2026-11-16", 6)

    def test_updated_daily_record_does_not_change_fixed_capacity(self):
        fixed_before = read_employee_capacities(PLANNING_PERIOD, PRIMARY_TEAM)
        set_daily_capacity("EMP-001", "2026-11-16", 3)
        set_daily_capacity("EMP-001", "2026-11-16", 5)
        set_daily_capacity("EMP-002", "2026-11-16", 2)
        result = check_dated_capacity("backend", 7, "2026-11-16", "2026-11-16")
        self.assertEqual(result["total_capacity"], 7)
        self.assertEqual(read_employee_capacities(PLANNING_PERIOD, PRIMARY_TEAM),
                         fixed_before)

    def test_team_filter_and_no_skill_match(self):
        self.seed_two_days()
        set_daily_capacity("EMP-004", "2026-11-16", 8)  # Platform ekibi
        result = check_dated_capacity("backend", 15, "2026-11-16", "2026-11-17")
        self.assertEqual(result["total_capacity"], 12)  # Dis ekip eklenmez.
        self.assertEqual(result["candidates"], ["Ada", "Bora"])

        result = check_dated_capacity("frontend", 5, "2026-11-16", "2026-11-16")
        self.assertTrue(result["data_complete"])
        self.assertEqual(result["total_capacity"], 0)
        self.assertEqual(result["shortage"], 5)
        self.assertEqual(result["candidates"], [])


    def test_reservations_reduce_available_capacity(self):
        self.seed_two_days()
        initialize_reservation_schema()

        reserve_daily_hours(
            reservation_id="RES-201",
            plan_id="PLAN-A",
            employee_id="EMP-001",
            capacity_date="2026-11-16",
            reserved_hours=3,
        )

        result = check_dated_capacity(
            "backend",
            14,
            "2026-11-16",
            "2026-11-17",
        )

        self.assertTrue(result["data_complete"])
        self.assertEqual(result["total_capacity"], 9)
        self.assertEqual(result["known_available_hours"], 9)
        self.assertEqual(result["shortage"], 5)
        self.assertFalse(result["is_sufficient"])

    def test_missing_data_remains_unknown_with_reservations(self):
        self.seed_two_days()
        initialize_reservation_schema()

        reserve_daily_hours(
            reservation_id="RES-202",
            plan_id="PLAN-B",
            employee_id="EMP-001",
            capacity_date="2026-11-16",
            reserved_hours=3,
        )

        result = check_dated_capacity(
            "backend",
            14,
            "2026-11-16",
            "2026-11-18",
        )

        self.assertFalse(result["data_complete"])
        self.assertEqual(result["known_available_hours"], 9)
        self.assertIsNone(result["total_capacity"])
        self.assertIsNone(result["shortage"])
        self.assertIsNone(result["is_sufficient"])



if __name__ == "__main__":
    unittest.main()
