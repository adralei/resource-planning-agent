import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from threading import Barrier
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


class TestConcurrentAssignment(unittest.TestCase):
    def test_two_plans_cannot_consume_the_same_capacity(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            test_db = Path(temporary_directory) / "concurrency.db"

            with patch("database.DB_PATH", test_db):
                initialize_database()

                proposal = propose_resources(
                    employees=OTHER_TEAM_EMPLOYEES,
                    required_skill="backend",
                    shortage=10,
                    excluded_names=["Ada", "Bora"],
                )

                plans = {}

                for project_id in ["DEMO-PROJECT-A", "DEMO-PROJECT-B"]:
                    plan = create_plan_draft(project_id, proposal)
                    plan["status"] = "approved"

                    for approval in plan["required_approvals"]:
                        approval["status"] = "approved"

                    plans[plan["plan_id"]] = plan

                # İki işçi de hazır olmadan uygulamaya başlamasın.
                start_barrier = Barrier(2)

                def attempt_assignment(plan_id):
                    start_barrier.wait(timeout=5)

                    try:
                        result = apply_approved_plan(plan_id)
                        return {
                            "plan_id": plan_id,
                            "status": result["status"],
                        }
                    except ValueError as error:
                        return {
                            "plan_id": plan_id,
                            "status": "rejected",
                            "reason": str(error),
                        }

                with patch(
                    "apply_plan.load_plan",
                    side_effect=lambda plan_id: plans[plan_id],
                ):
                    with ThreadPoolExecutor(max_workers=2) as executor:
                        futures = [
                            executor.submit(attempt_assignment, plan_id)
                            for plan_id in plans
                        ]
                        results = [
                            future.result(timeout=15)
                            for future in futures
                        ]

                self.assertCountEqual(
                    [result["status"] for result in results],
                    ["applied", "rejected"],
                )

                rejected = next(
                    result
                    for result in results
                    if result["status"] == "rejected"
                )
                self.assertIn("güncel boş kapasite 0 saat", rejected["reason"])

                employees = read_employee_capacities(PLANNING_PERIOD)
                capacities = {
                    employee["employee_id"]: employee["available_hours"]
                    for employee in employees
                }

                self.assertEqual(capacities["EMP-004"], 0)
                self.assertEqual(capacities["EMP-005"], 0)
                self.assertTrue(
                    all(hours >= 0 for hours in capacities.values())
                )

                with closing(connect_db()) as connection:
                    rows = connection.execute(
                        "SELECT plan_id FROM applied_plans"
                    ).fetchall()

                winner = next(
                    result["plan_id"]
                    for result in results
                    if result["status"] == "applied"
                )
                self.assertEqual(
                    [row["plan_id"] for row in rows],
                    [winner],
                )


if __name__ == "__main__":
    unittest.main()