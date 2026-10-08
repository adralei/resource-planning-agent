import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from apply_plan import apply_approved_plan
from database import (
    connect_db,
    initialize_database,
    read_employee_capacities,
    PLANNING_PERIOD,
)
from plan_store import create_plan_draft
from resource_proposal import OTHER_TEAM_EMPLOYEES, propose_resources


class TestApplyPlanRollback(unittest.TestCase):
    def test_failure_after_capacity_updates_rolls_back_everything(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            test_db = Path(temporary_directory) / "test.db"

            # Bütün bağlantıları geçici veritabanına yönlendir.
            with patch("database.DB_PATH", test_db):
                initialize_database()

                proposal = propose_resources(
                    employees=OTHER_TEAM_EMPLOYEES,
                    required_skill="backend",
                    shortage=10,
                    excluded_names=["Ada", "Bora"],
                )

                plan = create_plan_draft("DEMO-PROJECT-001", proposal)

                # Yalnızca test verisini onaylı duruma hazırlıyoruz.
                plan["status"] = "approved"
                for approval in plan["required_approvals"]:
                    approval["status"] = "approved"

                before = read_employee_capacities(PLANNING_PERIOD)

                with closing(connect_db()) as connection:
                    connection.execute("""
                        CREATE TABLE applied_plans (
                            plan_id TEXT PRIMARY KEY,
                            applied_at TEXT NOT NULL,
                            plan_snapshot TEXT NOT NULL
                        )
                    """)

                    connection.execute("""
                        CREATE TRIGGER fail_application_record
                        BEFORE INSERT ON applied_plans
                        BEGIN
                            SELECT CASE
                                WHEN (
                                    SELECT COUNT(*)
                                    FROM employee_capacity
                                    WHERE employee_id IN (
                                        'EMP-004', 'EMP-005'
                                    )
                                    AND planning_period =
                                        'prototype_fixed_period'
                                    AND available_hours = 0
                                ) = 2
                                THEN RAISE(
                                    ABORT,
                                    'injected_after_capacity_updates'
                                )
                                ELSE RAISE(
                                    ABORT,
                                    'capacity_updates_not_observed'
                                )
                            END;
                        END
                    """)

                # Gerçek JSON dosyasını okumak yerine test planını ver.
                with patch("apply_plan.load_plan", return_value=plan):
                    with self.assertRaisesRegex(
                        sqlite3.IntegrityError,
                        "injected_after_capacity_updates",
                    ):
                        apply_approved_plan(plan["plan_id"])

                # Yeni bağlantıdan okuyarak kalıcı durumu kontrol et.
                after = read_employee_capacities(PLANNING_PERIOD)
                self.assertEqual(before, after)

                with closing(connect_db()) as connection:
                    application_count = connection.execute(
                        "SELECT COUNT(*) FROM applied_plans"
                    ).fetchone()[0]

                self.assertEqual(application_count, 0)


if __name__ == "__main__":
    unittest.main()